"""Transactional outbox; Redis transports fixed job references, never executable payloads."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from sqlalchemy import DateTime, Integer, String, UniqueConstraint, select, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base, SessionLocal
from app.models.work import Task, Transcript, Analysis, CreationGeneration, CreationProject, utcnow
from app.models.research import ResearchRun


class QueuedJob(Base):
    __tablename__ = 'queued_jobs'
    __table_args__ = (UniqueConstraint('kind', 'target_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kind: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str] = mapped_column(String(36))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(20), default='QUEUED', index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WorkerHeartbeat(Base):
    __tablename__ = 'worker_heartbeat'
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


KINDS = {'metadata', 'transcript', 'analysis', 'generation', 'research', 'probe'}


class QueueBusy(RuntimeError):
    pass


def enqueue(db, kind, target_id):
    if kind not in KINDS: raise ValueError('Unsupported job kind')
    job = db.scalar(select(QueuedJob).where(QueuedJob.kind == kind, QueuedJob.target_id == target_id).with_for_update())
    if job is None:
        job = QueuedJob(kind=kind, target_id=target_id)
        db.add(job)
    elif job.state == 'RUNNING':
        raise QueueBusy('上一轮任务正在收尾，请稍后重试。')
    elif job.state in ('DONE', 'FAILED'):
        job.attempt += 1
        job.state = 'QUEUED'
    db.flush()
    return job


def target(db, job):
    if job.kind in ('transcript', 'analysis'):
        model = Transcript if job.kind == 'transcript' else Analysis
        query = select(model).where(model.work_id == job.target_id, model.owner_id == 'local-user')
        if model is Transcript: query = query.where(model.kind == 'SOURCE')
        return db.scalar(query)
    model = {'metadata': Task, 'generation': CreationGeneration, 'research': ResearchRun}.get(job.kind)
    if not model: return None
    query = select(model).where(model.id == job.target_id)
    if model is CreationGeneration:
        query = query.join(CreationProject).where(CreationProject.owner_id == 'local-user')
    else: query = query.where(model.owner_id == 'local-user')
    return db.scalar(query)


def invoke(kind, target_id, project_id=None):
    if kind == 'metadata':
        from app.services.metadata_pipeline import process_task
        process_task(target_id)
    elif kind == 'transcript':
        from app.services.transcript_pipeline import process_transcript
        process_transcript(target_id)
    elif kind == 'analysis':
        from app.services.llm_analysis import process_analysis
        process_analysis(target_id)
    elif kind == 'generation':
        from app.services.creation_generation import generate
        generate(project_id, target_id)
    elif kind == 'research':
        from app.services.research import process_research
        process_research(target_id)


def execute_job(job_id, attempt):
    with SessionLocal() as db:
        job = db.scalar(select(QueuedJob).where(QueuedJob.id == job_id).with_for_update())
        if not job or job.attempt != attempt or job.state not in ('QUEUED', 'SENT'): return
        item = target(db, job)
        if job.kind != 'probe' and (item is None or item.status != 'PENDING'):
            job.state = 'DONE' if item and item.status == 'COMPLETED' else 'FAILED'
            db.commit(); return
        project_id = item.project_id if job.kind == 'generation' else None
        job.state = 'RUNNING'; db.commit()
        kind, target_id = job.kind, job.target_id
    try:
        invoke(kind, target_id, project_id)
    except Exception:
        logging.getLogger(__name__).warning('Job failed: %s', job_id)
    finally:
        with SessionLocal() as db:
            job = db.get(QueuedJob, job_id)
            item = target(db, job)
            job.state = 'DONE' if kind == 'probe' or (item and item.status == 'COMPLETED') else 'FAILED'
            if item and item.status in ('PENDING', 'RUNNING', 'PROCESSING'):
                item.status = 'FAILED'
                item.error_summary = '后台任务未能完成，请检查配置后重试。已有结果保留。'
            db.commit()


def publish_pending():
    from app.worker import celery_app
    for _ in range(20):
        with SessionLocal() as db:
            # Redelivery also repairs a lost Redis message; RUNNING is never republished.
            job = db.scalar(select(QueuedJob).where((QueuedJob.state == 'QUEUED') | ((QueuedJob.state == 'SENT') & (QueuedJob.updated_at < utcnow() - timedelta(seconds=60)))).order_by(QueuedJob.updated_at).with_for_update(skip_locked=True).limit(1))
            if not job: return
            celery_app.send_task('creator_radar.execute_job', args=[job.id, job.attempt], task_id=f'{job.id}-{job.attempt}', retry=False)
            job.state = 'SENT'; job.updated_at = utcnow(); db.commit()


async def publisher_loop():
    while True:
        try: await asyncio.to_thread(publish_pending)
        except Exception: logging.getLogger(__name__).warning('Queue broker unavailable; requests retained in database')
        await asyncio.sleep(3)


def recover_worker():
    from app.services.task_recovery import recover_interrupted
    with SessionLocal() as db:
        recover_interrupted(db, recover_monitors=False, preserve_pending=True)
        for job in db.scalars(select(QueuedJob).where(QueuedJob.state.in_(['RUNNING', 'SENT']))):
            if job.state == 'RUNNING':
                item = target(db, job)
                job.state = 'DONE' if item and item.status == 'COMPLETED' else 'FAILED'
                if item and item.status == 'PENDING':
                    item.status = 'FAILED'; item.error_summary = '后台进程中断，请确认后重试。已有结果保留。'
            else: job.state = 'QUEUED'
        for model, kind, field in ((Transcript, 'transcript', 'work_id'), (Analysis, 'analysis', 'work_id'), (ResearchRun, 'research', 'id'), (CreationGeneration, 'generation', 'id')):
            query = select(model).where(model.status == 'PENDING')
            if model is CreationGeneration: query = query.join(CreationProject).where(CreationProject.owner_id == 'local-user')
            else: query = query.where(model.owner_id == 'local-user')
            for item in db.scalars(query): enqueue(db, kind, getattr(item, field))
        db.commit()


def heartbeat():
    with SessionLocal() as db:
        item = db.get(WorkerHeartbeat, 'local-worker') or WorkerHeartbeat(id='local-worker')
        item.updated_at = utcnow(); db.add(item); db.commit()


def queue_status():
    from redis import Redis
    from app.core.config import Settings
    try:
        with Redis.from_url(Settings().redis_url, socket_connect_timeout=1, socket_timeout=1) as client:
            broker_ready = bool(client.ping())
    except Exception: broker_ready = False
    with SessionLocal() as db:
        ready = db.scalar(select(WorkerHeartbeat.id).where(WorkerHeartbeat.updated_at > utcnow() - timedelta(seconds=35))) is not None
        pending = db.scalar(select(func.count()).select_from(QueuedJob).where(QueuedJob.state.in_(['QUEUED', 'SENT'])))
    return {'worker_ready': ready, 'broker_ready': broker_ready, 'pending': pending}
