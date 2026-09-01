from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.config import Settings
from app.db import Base, SessionLocal, engine
from app.models.work import Task, Work, WorkMetadata
from app.providers.base import ProviderError
from app.services.metadata_pipeline import process_task, provider_status
from app.services.image_proxy import fetch_remote_image
from app.services.transcript_pipeline import prepare_transcript, process_transcript, transcript_json, transcript_state
from app.services.link_validation import LinkError, validate_link
from app.services.link_resolution import resolve_and_check

settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
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
    return provider_status(settings)

@app.post("/api/v1/tasks/{task_id}/run", tags=["tasks"])
def run_task(task_id: str):
    try:
        return process_task(task_id, settings)
    except ProviderError as error:
        status = 409 if error.code == "provider_not_configured" else 404 if error.code == "task_not_found" else 502
        return JSONResponse(status_code=status, content={"code": error.code, "message": str(error), "retryable": error.retryable})
