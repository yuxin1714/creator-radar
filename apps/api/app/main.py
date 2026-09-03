from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.config import Settings
from app.db import Base, SessionLocal, engine
from app.models.work import Analysis, CreationBrief, CreationProject, PlaybookSource, Task, Transcript, Work, WorkMetadata
from app.providers.base import ProviderError
from app.services.metadata_pipeline import process_task, provider_status
from app.services.image_proxy import fetch_remote_image
from app.services.transcript_pipeline import prepare_transcript, process_transcript, transcript_json, transcript_state
from app.services.link_validation import LinkError, validate_link
from app.services.link_resolution import resolve_and_check
from app.services.llm_analysis import configured as analysis_configured, process_analysis

settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
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
    title: str = Field(default="未命名创作", min_length=1, max_length=200)
    idea: str | None = Field(default=None, max_length=10000)
    body: str | None = Field(default=None, max_length=50000)
    platform: str = Field(default="tiktok", max_length=30)
    content_type: str = Field(default="knowledge", max_length=50)
    direction: str = Field(default="structure_borrowing", max_length=50)
    style: str = Field(default="professional", max_length=50)
    playbook_id: str = Field(default="structure-borrowing-v1", max_length=80)
    output_language: str = Field(default="zh-CN", max_length=20)

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
    return {"id": item.id, "title": item.title, "idea": item.idea, "output_language": item.output_language, "status": item.status, "body": item.body, "updated_at": item.updated_at.isoformat(), "brief": None if not brief else {"platform": brief.platform, "content_type": brief.content_type, "direction": brief.direction, "style": brief.style, "playbook_id": brief.playbook_id}}

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
        transcript = db.scalar(select(Transcript).where(Transcript.work_id == work_id, Transcript.owner_id == "local-user", Transcript.kind == "SOURCE"))
        if not transcript or transcript.status != "COMPLETED":
            return JSONResponse(status_code=409, content={"code": "transcript_required", "message": "请先完成原文逐字稿。"})
        item = db.scalar(select(Analysis).where(Analysis.work_id == work_id, Analysis.owner_id == "local-user")) or Analysis(work_id=work_id)
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
    with SessionLocal() as db:
        rows = db.execute(select(Task, Work).join(Work, Work.id == Task.work_id).where(Task.owner_id == "local-user").order_by(Task.created_at.desc())).all()
        return [{"id": task.id, "work_id": work.id, "platform": work.platform, "external_id": work.external_id,
                 "stage": task.stage, "status": task.status, "error_summary": task.error_summary,
                 "created_at": task.created_at.isoformat()} for task, work in rows]

@app.get("/api/v1/providers/status", tags=["providers"])
def get_provider_status():
    status = provider_status(settings)
    status["analysis"] = {"configured": bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model),
                           "model": settings.llm_model or None}
    return status

@app.get("/api/v1/playbooks", tags=["creation"])
def list_playbooks():
    with SessionLocal() as db:
        rows = db.scalars(select(PlaybookSource).where(PlaybookSource.status == "ACTIVE").order_by(PlaybookSource.name)).all()
        return [{"id": x.id, "name": x.name, "source_type": x.source_type, "repository_url": x.repository_url, "revision": x.revision, "synced_at": x.synced_at.isoformat()} for x in rows]

@app.get("/api/v1/creation-projects", tags=["creation"])
def list_creation_projects():
    with SessionLocal() as db:
        rows = db.scalars(select(CreationProject).where(CreationProject.owner_id == "local-user").order_by(CreationProject.updated_at.desc())).all()
        return [{"id": x.id, "title": x.title, "idea": x.idea, "output_language": x.output_language, "status": x.status, "updated_at": x.updated_at.isoformat()} for x in rows]

@app.post("/api/v1/creation-projects", status_code=201, tags=["creation"])
def create_creation_project(body: CreationInput):
    with SessionLocal() as db:
        item = CreationProject(title=body.title, idea=body.idea, body=body.body, output_language=body.output_language)
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
        item = db.scalar(select(CreationProject).where(CreationProject.id == project_id, CreationProject.owner_id == "local-user"))
        if not item:
            return JSONResponse(status_code=404, content={"code": "project_not_found", "message": "创作项目不存在。"})
        item.title, item.idea, item.body, item.output_language = body.title, body.idea, body.body, body.output_language
        brief = db.get(CreationBrief, item.id) or CreationBrief(project_id=item.id)
        brief.platform, brief.content_type, brief.direction, brief.style, brief.playbook_id = body.platform, body.content_type, body.direction, body.style, body.playbook_id
        db.add(brief)
        db.commit(); db.refresh(item)
        return creation_json(item, db.get(CreationBrief, item.id))

@app.post("/api/v1/tasks/{task_id}/run", tags=["tasks"])
def run_task(task_id: str):
    try:
        return process_task(task_id, settings)
    except ProviderError as error:
        status = 409 if error.code == "provider_not_configured" else 404 if error.code == "task_not_found" else 502
        return JSONResponse(status_code=status, content={"code": error.code, "message": str(error), "retryable": error.retryable})

@app.post("/api/v1/tasks/{task_id}/retry", tags=["tasks"])
def retry_task(task_id: str):
    with SessionLocal() as db:
        task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == "local-user"))
        if not task:
            return JSONResponse(status_code=404, content={"code": "task_not_found", "message": "任务不存在。"})
        if task.status != "FAILED":
            return JSONResponse(status_code=409, content={"code": "task_not_retryable", "message": "只有失败任务可以重试。"})
        task.status, task.error_summary = "PENDING", None
        db.commit()
    return run_task(task_id)
