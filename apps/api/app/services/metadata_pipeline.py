from sqlalchemy import select
from app.core.config import Settings
from app.db import SessionLocal
from app.models.work import Task, Work, WorkMetadata
from app.providers.base import ProviderError
from app.providers.tikhub import TikHubProvider

def provider_status(settings: Settings | None = None):
    settings = settings or Settings()
    return {"provider": settings.metadata_provider, "configured": bool(settings.tikhub_api_key),
            "supported_platforms": ["douyin", "tiktok", "youtube"]}

def process_task(task_id: str, settings: Settings | None = None):
    settings = settings or Settings()
    provider = TikHubProvider(settings.tikhub_api_key, settings.tikhub_base_url)
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        if not task: raise ProviderError("task_not_found", "任务不存在。")
        work = db.get(Work, task.work_id)
        if not provider.configured:
            task.stage, task.status, task.error_summary = "WAITING_PROVIDER", "PENDING", "尚未配置 TikHub API Key。"
            db.commit()
            raise ProviderError("provider_not_configured", task.error_summary)
        task.stage, task.status, task.error_summary = "FETCHING_METADATA", "RUNNING", None
        db.commit()
        try:
            result = provider.fetch_work(work.platform, work.external_id)
        except ProviderError as error:
            task = db.get(Task, task_id)
            task.stage, task.status, task.error_summary = "FETCHING_METADATA", "FAILED", str(error)
            work = db.get(Work, task.work_id); work.status = "FAILED"
            db.commit()
            raise
        metadata = db.get(WorkMetadata, work.id) or WorkMetadata(work_id=work.id, provider=provider.name)
        metadata.provider = provider.name
        for field in ("title", "author_id", "author_name", "cover_url", "duration_seconds", "published_at", "metrics"):
            setattr(metadata, field, getattr(result, field))
        db.add(metadata)
        work.title, work.status = result.title, "READY"
        task.stage, task.status, task.error_summary = "METADATA_READY", "COMPLETED", None
        db.commit()
        return {"task_id": task.id, "work_id": work.id, "status": task.status}
