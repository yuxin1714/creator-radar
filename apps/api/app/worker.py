import threading
from celery import Celery
from celery.signals import worker_init, worker_ready, worker_shutdown
from app.core.config import Settings

settings = Settings()
celery_app = Celery("creator_radar", broker=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_pool='solo', worker_concurrency=1, worker_prefetch_multiplier=1,
    task_acks_late=True, task_reject_on_worker_lost=True, task_ignore_result=True,
    broker_connection_retry_on_startup=True, broker_connection_timeout=2,
    broker_transport_options={'socket_connect_timeout': 2, 'socket_timeout': 2},
)

_guard = None
_stop = threading.Event()
_thread = None


@worker_init.connect
def initialize(**kwargs):
    global _guard
    from app.db import Base, engine
    from app.services.task_recovery import local_worker_guard
    import app.main  # Register all tables, including monitor models.
    from app.services.job_queue import recover_worker
    _guard = local_worker_guard(engine, 724192602)
    try:
        _guard.__enter__()
        Base.metadata.create_all(engine)
        recover_worker()
    except Exception:
        raise SystemExit('Worker initialization failed; another worker may already be running.')


@worker_ready.connect
def ready(**kwargs):
    global _thread
    from app.services.job_queue import heartbeat
    def run():
        while not _stop.is_set():
            try: heartbeat()
            except Exception: pass
            _stop.wait(10)
    _thread = threading.Thread(target=run, daemon=True)
    _thread.start()


@worker_shutdown.connect
def shutdown(**kwargs):
    _stop.set()
    if _thread: _thread.join(timeout=5)
    from app.db import SessionLocal
    from app.services.job_queue import WorkerHeartbeat
    try:
        with SessionLocal() as db:
            item = db.get(WorkerHeartbeat, 'local-worker')
            if item: db.delete(item); db.commit()
    finally:
        if _guard: _guard.__exit__(None, None, None)


@celery_app.task(name='creator_radar.execute_job')
def execute_job(job_id, attempt):
    from app.services.job_queue import execute_job as execute
    execute(job_id, attempt)
