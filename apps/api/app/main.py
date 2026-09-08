from contextlib import asynccontextmanager
from datetime import datetime,timezone
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
from app.creator_routes import router as creator_router
from app.models.work_preferences import WorkPreferences
from app.services.work_preferences import preferences_json, save_preferences, PreferencesInput
from app.services.playbook_registration import RemotePlaybookInput, register_remote
from app.services.playbook_matching import PlaybookRouting, MatchingInput, criteria_for, recommend_playbooks
from app.services.local_preferences import LocalPreference, LocalPreferenceInput, local_preferences
from app.services.project_lifecycle import ProjectStatusInput,change_project_status
from app.research_routes import router as research_router
from app.models.research import ResearchRun
from app.services.pagination import paginated

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
        import asyncio
        from app.services.creator_monitor import monitor_loop
        monitor=asyncio.create_task(monitor_loop(settings))
        try:
            yield
        finally:
            monitor.cancel()
            try:await monitor
            except asyncio.CancelledError:pass

app = FastAPI(title=settings.app_name, version="0.6.0", lifespan=lifespan)
app.include_router(creator_router)
app.include_router(research_router)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

class LinkInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
class ImportInput(BaseModel):
    platform: str
    external_id: str = Field(min_length=1, max_length=64)
    normalized_url: str = Field(min_length=10, max_length=2000)
    availability_checked: bool
class CreationInput(BaseModel):
    expected_updated_at: datetime | None = None
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

@app.get("/api/v1/settings", tags=["settings"])
def get_local_preferences():
    with SessionLocal() as db:return local_preferences(db)

@app.patch("/api/v1/settings", tags=["settings"])
def update_local_preferences(body:LocalPreferenceInput):
    with SessionLocal() as db:
        item=db.scalar(select(LocalPreference).where(LocalPreference.owner_id=='local-user').with_for_update())
        if (item.revision if item else 0)!=body.expected_revision:return JSONResponse(status_code=409,content={'message':'设置已在其他页面更新，请刷新后重试。'})
        item=item or LocalPreference(owner_id='local-user',revision=0)
        item.values=body.model_dump(exclude={'expected_revision'});item.revision+=1
        db.add(item)
        try:db.commit()
        except IntegrityError:
            db.rollback();return JSONResponse(status_code=409,content={'message':'设置已被另一页面初始化，请刷新后重试。'})
        return local_preferences(db)

@app.get("/api/v1/today", tags=["insights"])
def get_today():
    from app.services.daily_brief import daily_brief
    with SessionLocal() as db:return daily_brief(db)

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
def list_works(page:int|None=None,page_size:int=20,q:str='',platform:str='',scope:str='all',tag:str=''):
    with SessionLocal() as db:
        works = db.scalars(select(Work).where(Work.owner_id == "local-user").order_by(Work.created_at.desc())).all()
        preferences={item.work_id:item for item in db.scalars(select(WorkPreferences).join(Work,Work.id==WorkPreferences.work_id).where(Work.owner_id=='local-user'))}
        transcripts={item.work_id:item.status for item in db.scalars(select(Transcript).where(Transcript.owner_id=='local-user',Transcript.kind=='SOURCE'))}
        analyses={item.work_id:item.status for item in db.scalars(select(Analysis).where(Analysis.owner_id=='local-user'))}
        metadata={item.work_id:item for item in db.scalars(select(WorkMetadata).join(Work,Work.id==WorkMetadata.work_id).where(Work.owner_id=='local-user'))}
        items=[{**work_json(item), "metadata": metadata_json(metadata.get(item.id)), "preferences": preferences_json(preferences.get(item.id)), "transcript_status":transcripts.get(item.id,'NOT_STARTED'),"analysis_status":analyses.get(item.id,'NOT_STARTED')} for item in works]
        tags=sorted({tag for item in items for tag in item['preferences']['tags']})
        filtered=[item for item in items if (not platform or platform=='all' or item['platform']==platform) and (scope=='all' or scope=='active' and not item['preferences']['archived'] or scope=='favorites' and item['preferences']['favorite'] and not item['preferences']['archived'] or scope=='archived' and item['preferences']['archived']) and (not tag or tag in item['preferences']['tags']) and q.strip().lower() in ' '.join([item['title'] or '',item['external_id'],(item['metadata'] or {}).get('author_name') or '',*item['preferences']['tags']]).lower()]
        return paginated(filtered,page,page_size,tags=tags)

@app.get("/api/v1/works/{work_id}", tags=["works"])
def get_work(work_id: str):
    with SessionLocal() as db:
        work = db.scalar(select(Work).where(Work.id == work_id, Work.owner_id == "local-user"))
        if not work:
            return JSONResponse(status_code=404, content={"code": "work_not_found", "message": "作品不存在或已不可访问。"})
        task = db.scalar(select(Task).where(Task.work_id == work.id, Task.owner_id == "local-user").order_by(Task.created_at.desc()))
        task_data = None if not task else {"id": task.id, "stage": task.stage, "status": task.status,
            "error_summary": task.error_summary, "created_at": task.created_at.isoformat()}
        return {**work_json(work), "metadata": metadata_json(db.get(WorkMetadata, work.id)), "latest_task": task_data, "preferences": preferences_json(db.get(WorkPreferences,work.id))}

@app.patch("/api/v1/works/{work_id}/preferences", tags=["works"])
def update_work_preferences(work_id:str,body:PreferencesInput):
    with SessionLocal() as db:
        try:return save_preferences(db,work_id,body)
        except ProviderError as error:return JSONResponse(status_code=404 if error.code=='work_not_found' else 409,content={'message':str(error)})

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
            from app.services.analysis_validation import validate_analysis
            evidence_verified = False
            if analysis.result and transcript and transcript.status == "COMPLETED":
                try:
                    validate_analysis(analysis.result, transcript.text or "")
                    evidence_verified = True
                except (ValueError, TypeError):
                    pass
            return {"availability": "READY" if analysis.status == "COMPLETED" else analysis.status, "analysis": {
                "id": analysis.id, "status": analysis.status, "analysis_language": analysis.analysis_language,
                "schema_version": analysis.schema_version, "result": analysis.result, "evidence_verified": evidence_verified,
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
        if db.scalar(select(ResearchRun.id).where(ResearchRun.work_id==work_id,ResearchRun.owner_id=='local-user',ResearchRun.status.in_(['PENDING','PROCESSING']))):return JSONResponse(status_code=409,content={'message':'此作品已有研究任务，请等待完成。'})
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
def list_tasks(page:int|None=None,page_size:int=20,status:str='all'):
    from app.services.task_overview import task_overview
    with SessionLocal() as db:
        items=task_overview(db)
        items=[item for item in items if status=='all' or status=='active' and item['status'] in ('PENDING','PROCESSING') or status=='FAILED' and item['status'] in ('FAILED','BLOCKED') or status==item['status']]
        return paginated(items,page,page_size) if page is not None else items[:200]

@app.get("/api/v1/providers/status", tags=["providers"])
def get_provider_status():
    status = provider_status(settings)
    status["analysis"] = {"configured": bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model),
                           "model": settings.llm_model or None}
    return status

@app.get("/api/v1/playbook-matching", tags=["creation"])
def get_playbook_matches(platform:str,content_type:str,direction:str,style:str):
    with SessionLocal() as db:return recommend_playbooks(db,platform,content_type,direction,style)

@app.get("/api/v1/playbook-routing/{source_id}", tags=["creation"])
def get_playbook_routing(source_id:str):
    with SessionLocal() as db:
        if not db.get(PlaybookSource,source_id):return JSONResponse(status_code=404,content={'message':'Skill 不存在。'})
        return criteria_for(db,source_id)

@app.put("/api/v1/playbook-routing/{source_id}", tags=["creation"])
def save_playbook_routing(source_id:str,body:MatchingInput):
    with SessionLocal() as db:
        source=db.scalar(select(PlaybookSource).where(PlaybookSource.id==source_id).with_for_update())
        if not source:return JSONResponse(status_code=404,content={'message':'Skill 不存在。'})
        item=db.get(PlaybookRouting,source_id) or PlaybookRouting(source_id=source_id)
        item.criteria=body.model_dump();db.add(item);db.commit();return item.criteria

@app.post("/api/v1/playbook-sources/remote", tags=["creation"])
def register_remote_playbook(body:RemotePlaybookInput):
    with SessionLocal() as db:
        item,created=register_remote(db,body)
        return {'id':item.id,'created':created,'message':'远程 Skill 已注册，请在列表中同步后使用。' if created else '这个仓库与路径已注册，可在列表中同步。'}

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
def list_creation_projects(page:int|None=None,page_size:int=20,q:str='',language:str='all',status:str='all'):
    with SessionLocal() as db:
        rows = db.scalars(select(CreationProject).where(CreationProject.owner_id == "local-user").order_by(CreationProject.updated_at.desc())).all()
        items=[{"id": x.id, "title": x.title, "idea": x.idea, "output_language": x.output_language, "status": x.status, "updated_at": x.updated_at.isoformat()} for x in rows]
        items=[item for item in items if (language=='all' or item['output_language']==language) and (status=='all' or status=='active' and item['status']!='ARCHIVED' or item['status']==status) and q.strip().lower() in (item['title']+' '+(item['idea'] or '')).lower()]
        return paginated(items,page,page_size)

@app.post("/api/v1/creation-projects", status_code=201, tags=["creation"])
def create_creation_project(body: CreationInput):
    with SessionLocal() as db:
        defaults=local_preferences(db)
        if 'output_language' not in body.model_fields_set:body.output_language=defaults['default_output_language']
        if 'platform' not in body.model_fields_set:body.platform=defaults['default_platform']
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

@app.patch("/api/v1/creation-projects/{project_id}/status", tags=["creation"])
def update_project_status(project_id:str,body:ProjectStatusInput):
    with SessionLocal() as db:
        try:return change_project_status(db,project_id,body)
        except ProviderError as error:return JSONResponse(status_code=404 if error.code=='project_not_found' else 409,content={'message':str(error)})

@app.patch("/api/v1/creation-projects/{project_id}", tags=["creation"])
def update_creation_project(project_id: str, body: CreationInput):
    with SessionLocal() as db:
        item = db.scalar(select(CreationProject).where(CreationProject.id == project_id, CreationProject.owner_id == "local-user").with_for_update())
        if not item:
            return JSONResponse(status_code=404, content={"code": "project_not_found", "message": "创作项目不存在。"})
        if item.status=='ARCHIVED':return JSONResponse(status_code=409,content={'message':'项目已归档，请先恢复为草稿再编辑。'})
        if body.expected_updated_at is not None:
            normalize=lambda date:date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)
            if normalize(body.expected_updated_at)!=normalize(item.updated_at):
                return JSONResponse(status_code=409,content={'message':'草稿已在其他页面更新，当前修改未覆盖服务器版本。请先导出或复制当前正文，再刷新合并。'})
        saved_brief=db.get(CreationBrief,item.id)
        content_changed=any(getattr(item,key)!=getattr(body,key) for key in ('title','idea','body','output_language'))
        options_changed=not saved_brief or any(getattr(saved_brief,key)!=getattr(body,key) for key in ('platform','content_type','direction','style','playbook_id'))
        if item.status=='COMPLETED' and (content_changed or options_changed):item.status='DRAFT'
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
def list_creation_versions(project_id: str,page:int|None=None,page_size:int=20):
    with SessionLocal() as db:
        project = db.scalar(select(CreationProject).where(CreationProject.id == project_id, CreationProject.owner_id == "local-user"))
        if not project:
            return JSONResponse(status_code=404, content={"message": "创作项目不存在。"})
        rows = db.scalars(select(CreationVersion).where(CreationVersion.project_id == project_id).order_by(CreationVersion.version_number.desc())).all()
        items=[{"id": row.id, "version_number": row.version_number, "snapshot": row.snapshot, "created_at": row.created_at.isoformat()} for row in rows]
        return paginated(items,page,page_size) if page is not None else items[:50]

@app.get("/api/v1/creation-projects/{project_id}/generations", tags=["creation"])
def list_creation_generations(project_id: str, generation_id: str | None = None,page:int|None=None,page_size:int=20):
    with SessionLocal() as db:
        project = db.scalar(select(CreationProject).where(CreationProject.id == project_id, CreationProject.owner_id == "local-user"))
        if not project:
            return JSONResponse(status_code=404, content={"message": "创作项目不存在。"})
        query = select(CreationGeneration, GenerationInput.mode).outerjoin(GenerationInput, GenerationInput.generation_id == CreationGeneration.id).where(CreationGeneration.project_id == project_id)
        if generation_id:
            query = query.where(CreationGeneration.id == generation_id)
        items=[{"id": gen.id, "mode": mode or "draft", "status": gen.status,
                 "content": gen.content, "error_summary": gen.error_summary, "created_at": gen.created_at.isoformat(),
                 "playbook_id": gen.playbook_id, "playbook_revision": gen.playbook_revision}
                for gen, mode in db.execute(query.order_by(CreationGeneration.created_at.desc(),CreationGeneration.id))]
        return paginated(items,page,page_size) if page is not None else items[:50]

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
