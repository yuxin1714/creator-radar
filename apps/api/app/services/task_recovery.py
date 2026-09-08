from contextlib import contextmanager
from sqlalchemy import select, text
from app.models.work import Task, Transcript, Analysis, CreationGeneration, CreationProject


@contextmanager
def local_worker_guard(engine):
    """Only one local API process may own in-process background jobs."""
    with engine.connect() as connection:
        locked = False
        try:
            if engine.dialect.name == "postgresql":
                locked = connection.scalar(text("SELECT pg_try_advisory_lock(724192601)"))
                if not locked:
                    raise RuntimeError("当前数据库已有工作台进程运行；请使用单个 API worker。")
                connection.commit()
            yield
        finally:
            if locked:
                connection.execute(text("SELECT pg_advisory_unlock(724192601)"))
                connection.commit()


def recover_interrupted(db):
    from app.models.creator import Creator
    message = "服务重启，上一轮任务已中断。请查看详情后重新发起，原有正文和结果已保留。"
    count = 0
    for creator in db.scalars(select(Creator).where(Creator.owner_id=='local-user',Creator.status=='PROCESSING')):
        creator.status='FAILED';creator.error_summary=message
        from app.models.work import utcnow
        creator.next_check_at=utcnow()
        count+=1
    for model in (Task, Transcript, Analysis, CreationGeneration):
        states = ["RUNNING", "PROCESSING"] if model is Task else ["PENDING", "PROCESSING"]
        query = select(model).where(model.status.in_(states))
        if model is CreationGeneration:
            query = query.join(CreationProject, model.project_id == CreationProject.id).where(CreationProject.owner_id == "local-user")
        else:
            query = query.where(model.owner_id == "local-user")
        for item in db.scalars(query):
            item.status, item.error_summary = "FAILED", message
            count += 1
    db.commit()
    return count
