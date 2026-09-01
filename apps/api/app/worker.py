from celery import Celery
from app.core.config import Settings

settings = Settings()
celery_app = Celery("creator_radar", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="creator_radar.fetch_work_metadata")
def fetch_work_metadata(task_id: str):
    from app.services.metadata_pipeline import process_task
    return process_task(task_id)

@celery_app.task(name="creator_radar.transcribe_work")
def transcribe_work(work_id: str):
    from app.services.transcript_pipeline import process_transcript
    return process_transcript(work_id)
