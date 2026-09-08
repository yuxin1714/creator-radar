from datetime import timedelta
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from app.core.config import Settings
from app.db import SessionLocal
from app.models.creator import Creator, CreatorWork
from app.models.work import Work, WorkMetadata, Transcript, Analysis, utcnow
from app.services.creator_monitor import add_creator, check_creator
from app.services.link_validation import LinkError
from app.providers.base import ProviderError

router=APIRouter(prefix='/api/v1',tags=['creators'])


def creator_json(item):
    return {key:getattr(item,key) for key in ('id','name','platform','source_url','daily','status','error_summary','last_checked_at','next_check_at','last_new_count')}


class CreatorInput(BaseModel):
    text:str=Field(min_length=1,max_length=4000)
    daily:bool=True


class CreatorPreference(BaseModel):
    daily:bool


@router.get('/creators')
def list_creators():
    with SessionLocal() as db:
        return [creator_json(item) for item in db.scalars(select(Creator).where(Creator.owner_id=='local-user').order_by(Creator.created_at.desc()))]


@router.post('/creators')
def create_creator(body:CreatorInput,background_tasks:BackgroundTasks):
    try:creator_id,created=add_creator(body.text,body.daily,Settings())
    except (ProviderError,LinkError) as error:return JSONResponse(status_code=409,content={'message':str(error)})
    except (OSError,ValueError):return JSONResponse(status_code=502,content={'message':'无法验证创作者主页，请稍后重试。'})
    if created:background_tasks.add_task(check_creator,creator_id,Settings())
    return {'id':creator_id,'created':created,'message':'主页已添加，正在读取近期作品。' if created else '该主页已经添加。'}


@router.get('/creators/{creator_id}')
def get_creator(creator_id:str):
    with SessionLocal() as db:
        item=db.scalar(select(Creator).where(Creator.id==creator_id,Creator.owner_id=='local-user'))
        if not item:return JSONResponse(status_code=404,content={'message':'创作者不存在。'})
        work_ids=select(CreatorWork.work_id).join(Work,Work.id==CreatorWork.work_id).where(CreatorWork.creator_id==creator_id,Work.owner_id=='local-user')
        count=db.scalar(select(func.count()).select_from(Work).where(Work.id.in_(work_ids)))
        transcripts=db.scalar(select(func.count()).select_from(Transcript).where(Transcript.work_id.in_(work_ids),Transcript.owner_id=='local-user',Transcript.kind=='SOURCE',Transcript.status=='COMPLETED'))
        analyses=db.scalar(select(func.count()).select_from(Analysis).where(Analysis.work_id.in_(work_ids),Analysis.owner_id=='local-user',Analysis.status=='COMPLETED'))
        return {'creator':creator_json(item),'stats':{'works':count,'transcripts':transcripts,'analyses':analyses}}


@router.patch('/creators/{creator_id}')
def update_creator(creator_id:str,body:CreatorPreference):
    with SessionLocal() as db:
        item=db.scalar(select(Creator).where(Creator.id==creator_id,Creator.owner_id=='local-user').with_for_update())
        if not item:return JSONResponse(status_code=404,content={'message':'创作者不存在。'})
        item.daily=body.daily;db.commit()
        return creator_json(item)


@router.post('/creators/{creator_id}/check',status_code=202)
def start_creator_check(creator_id:str,background_tasks:BackgroundTasks):
    with SessionLocal() as db:
        item=db.scalar(select(Creator).where(Creator.id==creator_id,Creator.owner_id=='local-user'))
        if not item:return JSONResponse(status_code=404,content={'message':'创作者不存在。'})
        if item.status=='PROCESSING':return JSONResponse(status_code=409,content={'message':'正在检查，请稍候。'})
    background_tasks.add_task(check_creator,creator_id,Settings())
    return {'message':'更新检查已提交。'}


@router.get('/feed')
def list_feed(creator_id:str|None=None,today:bool=False):
    with SessionLocal() as db:
        query=select(CreatorWork,Creator,Work,WorkMetadata).join(Creator,Creator.id==CreatorWork.creator_id).join(Work,Work.id==CreatorWork.work_id).outerjoin(WorkMetadata,WorkMetadata.work_id==Work.id).where(Creator.owner_id=='local-user',Work.owner_id=='local-user')
        if creator_id:query=query.where(Creator.id==creator_id)
        if today:query=query.where(CreatorWork.discovered_at>=utcnow()-timedelta(days=1))
        rows=db.execute(query.order_by(CreatorWork.discovered_at.desc(),Work.id).limit(200)).all()
        return [{'id':work.id,'title':work.title or work.external_id,'creator_id':creator.id,'creator_name':creator.name,
                 'discovered_at':link.discovered_at,'published_at':metadata.published_at if metadata else None,
                 'source_url':work.source_url} for link,creator,work,metadata in rows]
