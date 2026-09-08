from contextlib import contextmanager
from sqlalchemy import select, text
from app.models.work import Task, Transcript, Analysis, CreationGeneration, CreationProject


@contextmanager
def local_worker_guard(engine, lock_id=724192601):
    """Only one local API process may own in-process background jobs."""
    with engine.connect() as connection:
        locked = False
        try:
            if engine.dialect.name == "postgresql":
                locked = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_id})
                if not locked:
                    raise RuntimeError("当前数据库已有工作台进程运行；请使用单个 API worker。")
                connection.commit()
            yield
        finally:
            if locked:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                connection.commit()


def recover_interrupted(db, recover_jobs=True, recover_monitors=True, preserve_pending=False):
    from app.models.creator import Creator
    from app.models.research import ResearchRun
    from app.services.skill_updates import SkillUpdatePolicy
    message = "服务重启，上一轮任务已中断。请查看详情后重新发起，原有正文和结果已保留。"
    count = 0
    for policy in (db.scalars(select(SkillUpdatePolicy).where(SkillUpdatePolicy.status=='PROCESSING')) if recover_monitors else []):
        from app.models.work import utcnow
        policy.status='FAILED';policy.error_summary='服务重启，自动更新中断；旧版本保留。';policy.next_check_at=utcnow();count+=1
    for creator in (db.scalars(select(Creator).where(Creator.owner_id=='local-user',Creator.status=='PROCESSING')) if recover_monitors else []):
        creator.status='FAILED';creator.error_summary=message
        from app.models.work import utcnow
        creator.next_check_at=utcnow()
        count+=1
    for model in ((Task, Transcript, Analysis, CreationGeneration, ResearchRun) if recover_jobs else ()):
        states = ["RUNNING", "PROCESSING"] if model is Task else ["PENDING", "PROCESSING"]
        if preserve_pending: states = ["RUNNING", "PROCESSING"]
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
