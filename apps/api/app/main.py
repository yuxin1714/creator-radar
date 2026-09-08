from contextlib import asynccontextmanager
import json
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.config import Settings
from app.db import Base, SessionLocal, engine
from app.models.work import Analysis, CreationBrief, CreationGeneration, CreationProject, PlaybookRevision, PlaybookSource, Task, Transcript, Work, WorkMetadata
from app.providers.base import ProviderError
from app.services.metadata_pipeline import process_task, provider_status
from app.services.image_proxy import fetch_remote_image
from app.services.transcript_pipeline import prepare_transcript, process_transcript, transcript_json, transcript_state
from app.services.link_validation import LinkError, validate_link
from app.services.link_resolution import resolve_and_check
from app.services.llm_analysis import configured as analysis_configured, process_analysis
from app.services.remote_playbooks import sync_playbook
from app.services.creation_generation import generate as generate_creation
from app.services.creation_playbooks import resolve_playbook
from app.services.generation_workflow import GenerationOptions, prepare_generation
from app.models.work import GenerationInput
from app.services.creation_versions import record_version
from app.models.work import CreationVersion

settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    from app.services.task_recovery import local_worker_guard, recover_interrupted
    with local_worker_guard(engine):
        with SessionLocal() as db:
            recover_interrupted(db)
        with SessionLocal() as db:
            if not db.get(PlaybookSource, "tki-content-creation"):
                db.add(PlaybookSource(id="tki-content-creation", name="TKI 创作 Skill：故事化产品内容", repository_url="https://github.com/yuxin1714/-.git", skill_path="tki-content-creation/SKILL.md", revision="d2c8a809b6c89d7ac4da179c904f85f5524cd1a8"))
                db.commit()
        yield

app = FastAPI(title=settings.app_name, version="0.6.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

class LinkInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
class ImportInput(BaseModel):
    platform: str
    external_id: str = Field(min_length=1, max_length=64)
    normalized_url: str = Field(min_length=10, max_length=2000)
    availability_checked: bool
class CreationInput(BaseModel):
    work_id: str | None = Field(default=None, max_length=36)
    output_language: str = Field(default="zh-CN", max_length=20)
    title: str = Field(default="未命名创作", min_length=1, max_length=200)
    idea: str | None = Field(default=None, max_length=10000)
    body: str | None = Field(default=None, max_length=50000)
    platform: str = Field(default="tiktok", max_length=30)
    content_type: str = Field(default="knowledge", max_length=50)
    direction: str = Field(default="structure_borrowing", max_length=50)
    style: str = Field(default="professional", max_length=50)
    playbook_id: str = Field(default="structure-borrowing-v1", max_length=80)
class PlaybookInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    rules: list[str] = Field(default_factory=list, max_length=20)

class PlaybookEditInput(PlaybookInput):
    expected_revision: str = Field(min_length=1, max_length=80)

@app.get("/api/v1/playbooks/{playbook_id}", tags=["creation"])
def get_custom_playbook(playbook_id: str):
    with SessionLocal() as db:
        source = db.get(PlaybookSource, playbook_id)
        if not source or source.source_type != "custom":
            return JSONResponse(status_code=404, content={"message": "自定义 Skill 不存在。"})
        saved = db.get(PlaybookRevision, f"{playbook_id}:{source.revision}")
        if not saved:
            return JSONResponse(status_code=409, content={"message": "Skill 内容版本缺失。"})
        return {"id": source.id, "revision": source.revision, **json.loads(saved.content)}

@app.patch("/api/v1/playbooks/{playbook_id}", tags=["creation"])
def edit_custom_playbook(playbook_id: str, body: PlaybookEditInput):
    from app.models.work import utcnow
    with SessionLocal() as db:
        source = db.scalar(select(PlaybookSource).where(PlaybookSource.id == playbook_id).with_for_update())
        if not source or source.source_type != "custom":
            return JSONResponse(status_code=404, content={"message": "自定义 Skill 不存在。"})
        if source.revision != body.expected_revision:
            return JSONResponse(status_code=409, content={"message": "Skill 已在其他页面更新，请重新打开后编辑。"})
        saved = db.get(PlaybookRevision, f"{playbook_id}:{source.revision}")
        if not saved:
            return JSONResponse(status_code=409, content={"message": "Skill 内容版本缺失。"})
        previous = json.loads(saved.content)
        content = {"name": body.name, "description": body.description, "rules": body.rules}
        if all(previous.get(key) == value for key, value in content.items()):
            return {"id": source.id, "revision": source.revision, "updated": False}
        revision = f"1.{int(source.revision.split('.')[1]) + 1}"
        content["version"] = revision
        db.add(PlaybookRevision(id=f"{playbook_id}:{revision}", source_id=playbook_id, revision=revision, content=json.dumps(content, ensure_ascii=False)))
        source.name, source.revision, source.synced_at = body.name, revision, utcnow()
        db.commit()
        return {"id": source.id, "revision": revision, "updated": True}

def link_error(error: LinkError):
    return JSONResponse(status_code=422, content={"code": error.code, "message": str(error)})

def work_json(work: Work):
    return {"id": work.id, "platform": work.platform, "external_id": work.external_id,
            "source_url": work.source_url, "title": work.title, "status": work.status,
            "created_at": work.created_at.isoformat()}

def metadata_json(item: WorkMetadata | None):
    if not item: return None
    return {"provider": item.provider, "title": item.title, "author_id": item.author_id,
            "author_name": item.author_name, "cover_url": item.cover_url,
            "duration_seconds": item.duration_seconds,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "metrics": item.metrics, "fetched_at": item.fetched_at.isoformat()}

def creation_json(item: CreationProject, brief: CreationBrief | None):
    with SessionLocal() as db:
        generation = db.scalar(select(CreationGeneration).where(CreationGeneration.project_id == item.id).order_by(CreationGeneration.created_at.desc()))
        generation_input = db.get(GenerationInput, generation.id) if generation else None
    return {"id": item.id, "work_id": item.work_id, "context_type": item.context_type, "title": item.title, "idea": item.idea, "output_language": item.output_language, "status": item.status, "body": item.body, "updated_at": item.updated_at.isoformat(), "brief": None if not brief else {"platform": brief.platform, "content_type": brief.content_type, "direction": brief.direction, "style": brief.style, "playbook_id": brief.playbook_id}, "latest_generation": None if not generation else {"id": generation.id, "status": generation.status, "content": generation.content, "error_summary": generation.error_summary, "playbook_id": generation.playbook_id, "playbook_revision": generation.playbook_revision, "mode": generation_input.mode if generation_input else "draft"}}

@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "creator-radar-api"}

@app.post("/api/v1/links/validate", tags=["links"])
def check_link(body: LinkInput):
    try:
        parsed = validate_link(body.text)
        return resolve_and_check(parsed)
    except LinkError as error:
        return link_error(error)

@app.post("/api/v1/imports", status_code=201, tags=["imports"])
def import_work(body: ImportInput):
    try:
        canonical = validate_link(body.normalized_url)
        verified = resolve_and_check(canonical)
    except LinkError as error:
        return link_error(error)
    if not body.availability_checked:
        return JSONResponse(status_code=409, content={"code": "verification_required", "message": "请先完成平台响应验证。"})
    if (verified["platform"] != body.platform
            or verified["external_id"] != body.external_id
            or verified["normalized_url"] != canonical["normalized_url"]):
        return JSONResponse(status_code=409, content={"code": "verification_mismatch", "message": "链接验证结果不一致，请重新验证。"})
    with SessionLocal() as db:
        existing = db.scalar(select(Work).where(Work.owner_id == "local-user", Work.platform == body.platform, Work.external_id == body.external_id))
        if existing:
            task = db.scalar(select(Task).where(Task.work_id == existing.id).order_by(Task.created_at.desc()))
            return JSONResponse(status_code=200, content={"created": False, "work": work_json(existing), "task_id": task.id if task else None, "message": "该作品已在作品库中，没有重复创建。"})
        work = Work(platform=body.platform, external_id=body.external_id, source_url=canonical["normalized_url"])
        db.add(work)
        db.flush()
        task = Task(work_id=work.id)
        db.add(task)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(Work).where(Work.owner_id == "local-user", Work.platform == body.platform, Work.external_id == body.external_id))
            return JSONResponse(status_code=200, content={"created": False, "work": work_json(existing), "task_id": None, "message": "该作品已在作品库中。"})
        return {"created": True, "work": work_json(work), "task_id": task.id, "message": "作品已保存，并创建等待处理任务。"}

@app.get("/api/v1/works", tags=["works"])
def list_works():
    with SessionLocal() as db:
        works = db.scalars(select(Work).where(Work.owner_id == "local-user").order_by(Work.created_at.desc())).all()
        return [{**work_json(item), "metadata": metadata_json(db.get(WorkMetadata, item.id))} for item in works]

@app.get("/api/v1/works/{work_id}", tags=["works"])
def get_work(work_id: str):
    with SessionLocal() as db:
        work = db.scalar(select(Work).where(Work.id == work_id, Work.owner_id == "local-user"))
        if not work:
            return JSONResponse(status_code=404, content={"code": "work_not_found", "message": "作品不存在或已不可访问。"})
        task = db.scalar(select(Task).where(Task.work_id == work.id, Task.owner_id == "local-user").order_by(Task.created_at.desc()))
        task_data = None if not task else {"id": task.id, "stage": task.stage, "status": task.status,
            "error_summary": task.error_summary, "created_at": task.created_at.isoformat()}
        return {**work_json(work), "metadata": metadata_json(db.get(WorkMetadata, work.id)), "latest_task": task_data}

@app.get("/api/v1/works/{work_id}/cover", tags=["works"])
def get_work_cover(work_id: str):
    with SessionLocal() as db:
        work = db.scalar(select(Work).where(Work.id == work_id, Work.owner_id == "local-user"))
        metadata = db.get(WorkMetadata, work.id) if work else None
        if not metadata or not metadata.cover_url:
            return JSONResponse(status_code=404, content={"code": "cover_not_found", "message": "该作品没有可用封面。"})
        cover_url = metadata.cover_url
    try: data, content_type = fetch_remote_image(cover_url)
    except ProviderError as error:
        return JSONResponse(status_code=502, content={"code": error.code, "message": str(error)})
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})

@app.get("/api/v1/works/{work_id}/transcript", tags=["transcripts"])
def get_work_transcript(work_id: str):
    with SessionLocal() as db:
        work = db.scalar(select(Work).where(Work.id == work_id, Work.owner_id == "local-user"))
        if not work:
            return JSONResponse(status_code=404, content={"code": "work_not_found", "message": "作品不存在或已不可访问。"})
        db.expunge(work)
    return transcript_state(work, settings)

@app.get("/api/v1/works/{work_id}/analysis", tags=["analysis"])
def get_work_analysis(work_id: str):
    with SessionLocal() as db:
        work = db.scalar(select(Work).where(Work.id == work_id, Work.owner_id == "local-user"))
        if not work:
            return JSONResponse(status_code=404, content={"code": "work_not_found", "message": "作品不存在或已不可访问。"})
        analysis = db.scalar(select(Analysis).where(Analysis.work_id == work.id, Analysis.owner_id == "local-user"))
        transcript = db.scalar(select(Transcript).where(Transcript.work_id == work.id, Transcript.owner_id == "local-user", Transcript.kind == "SOURCE"))
        if analysis:
            return {"availability": "READY" if analysis.status == "COMPLETED" else analysis.status, "analysis": {
                "id": analysis.id, "status": analysis.status, "analysis_language": analysis.analysis_language,
                "schema_version": analysis.schema_version, "result": analysis.result,
                "error_summary": analysis.error_summary, "created_at": analysis.created_at.isoformat(),
                "updated_at": analysis.updated_at.isoformat()}}
        if not transcript or transcript.status != "COMPLETED":
            return {"availability": "NEEDS_TRANSCRIPT", "analysis": None, "message": "请先完成原文逐字稿，再进行内容分析。"}
        return {"availability": "READY_TO_ANALYZE" if analysis_configured(settings) else "LLM_REQUIRED", "analysis": None, "message": "逐字稿已就绪；可以开始生成内容拆解。" if analysis_configured(settings) else "逐字稿已就绪；配置分析模型后即可生成内容拆解。"}

@app.post("/api/v1/works/{work_id}/analysis", status_code=202, tags=["analysis"])
def start_work_analysis(work_id: str, background_tasks: BackgroundTasks):
    if not analysis_configured(settings):
        return JSONResponse(status_code=409, content={"code": "llm_not_configured", "message": "分析模型尚未配置。"})
    with SessionLocal() as db:
        work = db.scalar(select(Work).where(Work.id == work_id, Work.owner_id == "local-user").with_for_update())
        if not work:
            return JSONResponse(status_code=404, content={"message": "作品不存在。"})
        transcript = db.scalar(select(Transcript).where(Transcript.work_id == work_id, Transcript.owner_id == "local-user", Transcript.kind == "SOURCE"))
        if not transcript or transcript.status != "COMPLETED":
            return JSONResponse(status_code=409, content={"code": "transcript_required", "message": "请先完成原文逐字稿。"})
        item = db.scalar(select(Analysis).where(Analysis.work_id == work_id, Analysis.owner_id == "local-user")) or Analysis(work_id=work_id)
        if item.status in ("PENDING", "PROCESSING"):
            return JSONResponse(status_code=409, content={"message": "分析任务正在运行，请等待完成。"})
        item.status, item.error_summary = "PENDING", None; db.add(item); db.commit()
    background_tasks.add_task(process_analysis, work_id, settings)
    return {"message": "内容分析已开始。"}

@app.post("/api/v1/works/{work_id}/transcript", status_code=202, tags=["transcripts"])
def start_work_transcript(work_id: str, background_tasks: BackgroundTasks):
    with SessionLocal() as db:
        work = db.scalar(select(Work).where(Work.id == work_id, Work.owner_id == "local-user"))
        if not work: return JSONResponse(status_code=404, content={"code": "work_not_found", "message": "作品不存在或已不可访问。"})
        db.expunge(work)
    try: transcript = prepare_transcript(work, settings)
    except ProviderError as error: return JSONResponse(status_code=409, content={"code": error.code, "message": str(error)})
    if transcript.status != "COMPLETED": background_tasks.add_task(process_transcript, work.id, settings)
    return {"message": "本地转写已开始。", "transcript": transcript_json(transcript)}

@app.get("/api/v1/tasks", tags=["tasks"])
def list_tasks():
    from app.services.task_overview import task_overview
    with SessionLocal() as db:
        return task_overview(db)

@app.get("/api/v1/providers/status", tags=["providers"])
def get_provider_status():
    status = provider_status(settings)
    status["analysis"] = {"configured": bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model),
                           "model": settings.llm_model or None}
    return status

@app.get("/api/v1/playbooks", tags=["creation"])
def list_playbooks(include_inactive: bool = False):
    with SessionLocal() as db:
        query = select(PlaybookSource).order_by(PlaybookSource.name)
        if not include_inactive:
            query = query.where(PlaybookSource.status == "ACTIVE")
        rows = db.scalars(query).all()
        return [{"id": x.id, "name": x.name, "status": x.status, "source_type": x.source_type, "repository_url": x.repository_url, "revision": x.revision, "synced_at": x.synced_at.isoformat()} for x in rows]

class PlaybookStatusInput(BaseModel):
    enabled: bool

@app.patch("/api/v1/playbooks/{playbook_id}/status", tags=["creation"])
def set_playbook_status(playbook_id: str, body: PlaybookStatusInput):
    with SessionLocal() as db:
        source = db.scalar(select(PlaybookSource).where(PlaybookSource.id == playbook_id).with_for_update())
        if not source:
            return JSONResponse(status_code=404, content={"message": "Skill 不存在。"})
        source.status = "ACTIVE" if body.enabled else "DISABLED"
        db.commit()
        return {"id": source.id, "status": source.status}

@app.post("/api/v1/playbooks", status_code=201, tags=["creation"])
def create_playbook(body: PlaybookInput):
    import uuid
    from app.services.creation_playbooks import PLAYBOOKS
    playbook_id = "custom-" + uuid.uuid4().hex[:12]
    content = {"name": body.name, "version": "1.0", "rules": body.rules, "description": body.description}
    with SessionLocal() as db:
        item = PlaybookSource(id=playbook_id, name=body.name, source_type="custom", skill_path=None, revision="1.0")
        db.add(item); db.flush(); db.add(PlaybookRevision(id=f"{playbook_id}:1.0", source_id=playbook_id, revision="1.0", content=json.dumps(content, ensure_ascii=False))); db.commit(); db.refresh(item)
        return {"id": item.id, "name": item.name, "source_type": item.source_type, "repository_url": item.repository_url, "revision": item.revision, "synced_at": item.synced_at.isoformat()}

@app.post("/api/v1/playbooks/{playbook_id}/sync", tags=["creation"])
def sync_remote_playbook(playbook_id: str):
    try: return sync_playbook(playbook_id)
    except ProviderError as error: return JSONResponse(status_code=502, content={"code": error.code, "message": str(error)})

@app.get("/api/v1/creation-projects", tags=["creation"])
def list_creation_projects():
    with SessionLocal() as db:
        rows = db.scalars(select(CreationProject).where(CreationProject.owner_id == "local-user").order_by(CreationProject.updated_at.desc())).all()
        return [{"id": x.id, "title": x.title, "idea": x.idea, "output_language": x.output_language, "status": x.status, "updated_at": x.updated_at.isoformat()} for x in rows]

@app.post("/api/v1/creation-projects", status_code=201, tags=["creation"])
def create_creation_project(body: CreationInput):
    with SessionLocal() as db:
        if body.work_id and not db.scalar(select(Work).where(Work.id == body.work_id, Work.owner_id == "local-user")):
            return JSONResponse(status_code=404, content={"code": "work_not_found", "message": "参考作品不存在或不可访问。"})
        item = CreationProject(title=body.title, idea=body.idea, body=body.body, output_language=body.output_language, work_id=body.work_id, context_type="work" if body.work_id else "idea")
        db.add(item); db.flush(); db.add(CreationBrief(project_id=item.id, platform=body.platform, content_type=body.content_type, direction=body.direction, style=body.style, playbook_id=body.playbook_id)); db.commit(); db.refresh(item)
        return creation_json(item, db.get(CreationBrief, item.id))

@app.get("/api/v1/creation-projects/{project_id}", tags=["creation"])
def get_creation_project(project_id: str):
    with SessionLocal() as db:
        item = db.scalar(select(CreationProject).where(CreationProject.id == project_id, CreationProject.owner_id == "local-user"))
        if not item:
            return JSONResponse(status_code=404, content={"code": "project_not_found", "message": "创作项目不存在。"})
        return creation_json(item, db.get(CreationBrief, item.id))

@app.patch("/api/v1/creation-projects/{project_id}", tags=["creation"])
def update_creation_project(project_id: str, body: CreationInput):
    with SessionLocal() as db:
        item = db.scalar(select(CreationProject).where(CreationProject.id == project_id, CreationProject.owner_id == "local-user").with_for_update())
        if not item:
            return JSONResponse(status_code=404, content={"code": "project_not_found", "message": "创作项目不存在。"})
        record_version(db, item, db.get(CreationBrief, item.id))
        item.title, item.idea, item.body, item.output_language = body.title, body.idea, body.body, body.output_language
        brief = db.get(CreationBrief, item.id) or CreationBrief(project_id=item.id)
        brief.platform, brief.content_type, brief.direction, brief.style, brief.playbook_id = body.platform, body.content_type, body.direction, body.style, body.playbook_id
        db.add(brief)
        db.flush()
        record_version(db, item, brief)
        db.commit(); db.refresh(item)
        return creation_json(item, db.get(CreationBrief, item.id))

@app.get("/api/v1/creation-projects/{project_id}/versions", tags=["creation"])
def list_creation_versions(project_id: str):
    with SessionLocal() as db:
        project = db.scalar(select(CreationProject).where(CreationProject.id == project_id, CreationProject.owner_id == "local-user"))
        if not project:
            return JSONResponse(status_code=404, content={"message": "创作项目不存在。"})
        rows = db.scalars(select(CreationVersion).where(CreationVersion.project_id == project_id).order_by(CreationVersion.version_number.desc()).limit(50)).all()
        return [{"id": row.id, "version_number": row.version_number, "snapshot": row.snapshot, "created_at": row.created_at.isoformat()} for row in rows]

@app.post("/api/v1/creation-projects/{project_id}/generations", status_code=202, tags=["creation"])
def start_creation_generation(project_id: str, background_tasks: BackgroundTasks, options: GenerationOptions | None = None):
    if not analysis_configured(settings):
        return JSONResponse(status_code=409, content={"code": "llm_not_configured", "message": "生成模型尚未配置。"})
    with SessionLocal() as db:
        try:
            item = prepare_generation(db, project_id, options or GenerationOptions(), settings)
        except ProviderError as error:
            return JSONResponse(status_code=404 if error.code == "project_not_found" else 409, content={"code": error.code, "message": str(error)})
        db.commit(); db.refresh(item)
        generation_id = item.id
    background_tasks.add_task(generate_creation, project_id, generation_id, settings)
    return {"message": "创作任务已开始。", "generation_id": generation_id}

@app.post("/api/v1/tasks/{task_id}/run", tags=["tasks"])
def run_task(task_id: str):
    try:
        return process_task(task_id, settings)
    except ProviderError as error:
        status = 409 if error.code in ("provider_not_configured", "task_running") else 404 if error.code == "task_not_found" else 502
        return JSONResponse(status_code=status, content={"code": error.code, "message": str(error), "retryable": error.retryable})

@app.post("/api/v1/tasks/{task_id}/retry", tags=["tasks"])
def retry_task(task_id: str):
    with SessionLocal() as db:
        task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == "local-user").with_for_update())
        if not task:
            return JSONResponse(status_code=404, content={"code": "task_not_found", "message": "任务不存在。"})
        if task.status != "FAILED":
            return JSONResponse(status_code=409, content={"code": "task_not_retryable", "message": "只有失败任务可以重试。"})
        task.status, task.error_summary = "PENDING", None
        db.commit()
    return run_task(task_id)
