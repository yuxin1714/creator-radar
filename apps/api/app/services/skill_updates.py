import asyncio
import logging
from datetime import datetime,timedelta
from sqlalchemy import Boolean,DateTime,ForeignKey,Integer,String,select
from sqlalchemy.orm import Mapped,mapped_column
from app.db import Base,SessionLocal
from app.models.work import PlaybookSource,utcnow
from app.services.remote_playbooks import sync_playbook
from app.providers.base import ProviderError


class SkillUpdatePolicy(Base):
    __tablename__='skill_update_policies'
    source_id:Mapped[str]=mapped_column(ForeignKey('playbook_sources.id',ondelete='CASCADE'),primary_key=True)
    enabled:Mapped[bool]=mapped_column(Boolean,default=False)
    revision:Mapped[int]=mapped_column(Integer,default=0)
    next_check_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    last_checked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    status:Mapped[str]=mapped_column(String(20),default='IDLE')
    error_summary:Mapped[str|None]=mapped_column(String(500),nullable=True)


def policy_json(item):
    if not item:return {'enabled':False,'revision':0,'status':'IDLE','last_checked_at':None,'next_check_at':None,'error_summary':None}
    return {key:getattr(item,key) for key in ('enabled','revision','status','last_checked_at','next_check_at','error_summary')}


def check_skill(source_id):
    with SessionLocal() as db:
        policy=db.scalar(select(SkillUpdatePolicy).where(SkillUpdatePolicy.source_id==source_id,SkillUpdatePolicy.enabled.is_(True),SkillUpdatePolicy.next_check_at<=utcnow(),SkillUpdatePolicy.status.notin_(['PROCESSING','BLOCKED'])).with_for_update())
        source=db.get(PlaybookSource,source_id)
        if not policy or not source or source.source_type!='remote' or source.status!='ACTIVE':return
        policy.status='PROCESSING';policy.error_summary=None;policy.next_check_at=utcnow()+timedelta(days=1);db.commit()
    try:
        result=sync_playbook(source_id)
        with SessionLocal() as db:
            policy=db.get(SkillUpdatePolicy,source_id);policy.status='UPDATED' if result['updated'] else 'CURRENT';policy.last_checked_at=utcnow();db.commit()
    except Exception as error:
        with SessionLocal() as db:
            policy=db.get(SkillUpdatePolicy,source_id)
            policy.status='BLOCKED' if isinstance(error,ProviderError) and error.code=='invalid_playbook' else 'FAILED'
            policy.error_summary=str(error)[:500] if isinstance(error,ProviderError) else '远程更新检查失败，当前版本保留。'
            policy.last_checked_at=utcnow();db.commit()


def check_due_skills():
    with SessionLocal() as db:
        ids=list(db.scalars(select(SkillUpdatePolicy.source_id).join(PlaybookSource,PlaybookSource.id==SkillUpdatePolicy.source_id).where(SkillUpdatePolicy.enabled.is_(True),SkillUpdatePolicy.next_check_at<=utcnow(),SkillUpdatePolicy.status.notin_(['PROCESSING','BLOCKED']),PlaybookSource.status=='ACTIVE',PlaybookSource.source_type=='remote')))
    for source_id in ids:check_skill(source_id)


async def skill_update_loop():
    while True:
        try:
            check=asyncio.create_task(asyncio.to_thread(check_due_skills))
            try:await asyncio.shield(check)
            except asyncio.CancelledError:
                try:await check
                except Exception:pass
                raise
        except Exception:logging.getLogger(__name__).warning('Skill update check failed; retry on next tick')
        await asyncio.sleep(60)
