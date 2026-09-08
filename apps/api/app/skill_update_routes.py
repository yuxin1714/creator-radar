from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db import SessionLocal
from app.models.work import PlaybookSource,utcnow
from app.services.skill_updates import SkillUpdatePolicy,policy_json

router=APIRouter(prefix='/api/v1',tags=['skills'])


class PolicyInput(BaseModel):
    enabled:bool
    expected_revision:int=Field(default=0,ge=0)


@router.get('/playbook-updates/{source_id}')
def get_policy(source_id:str):
    with SessionLocal() as db:
        source=db.get(PlaybookSource,source_id)
        if not source or source.source_type!='remote':return JSONResponse(status_code=404,content={'message':'远程 Skill 不存在。'})
        return policy_json(db.get(SkillUpdatePolicy,source_id))


@router.put('/playbook-updates/{source_id}')
def update_policy(source_id:str,body:PolicyInput):
    with SessionLocal() as db:
        source=db.scalar(select(PlaybookSource).where(PlaybookSource.id==source_id,PlaybookSource.source_type=='remote').with_for_update())
        if not source:return JSONResponse(status_code=404,content={'message':'远程 Skill 不存在。'})
        item=db.get(SkillUpdatePolicy,source_id)
        if (item.revision if item else 0)!=body.expected_revision:return JSONResponse(status_code=409,content={'message':'设置已在其他页面更新，请重新读取。'})
        item=item or SkillUpdatePolicy(source_id=source_id,revision=0)
        if body.enabled and not item.enabled:
            item.next_check_at=utcnow()
            if item.status!='PROCESSING':item.status='IDLE';item.error_summary=None
        item.enabled=body.enabled;item.revision+=1;db.add(item)
        try:db.commit()
        except IntegrityError:db.rollback();return JSONResponse(status_code=409,content={'message':'设置发生冲突，请重新读取。'})
        return policy_json(item)
