from fastapi import APIRouter,BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy import select
from typing import Literal
from app.db import SessionLocal
from app.core.config import Settings
from app.models.work import Work,Transcript,Analysis
from app.models.research import ResearchRun
from app.services.research import ResearchInput,prepare_research,process_research,text_hash
from app.providers.base import ProviderError
from app.services.analysis_validation import validate_analysis
from app.services.pagination import paginated


def verified(result,text):
    try:validate_analysis(result,text);return True
    except (ValueError,TypeError):return False

router=APIRouter(prefix='/api/v1',tags=['research'])


def run_json(item,current_text):
    return {'id':item.id,'kind':item.kind,'language':item.language,'status':item.status,'result':item.result,'source_text':item.source_text,'source_stale':item.source_hash!=text_hash(current_text),'completed_units':item.completed_units,'total_units':item.total_units,'error_summary':item.error_summary,'created_at':item.created_at,'legacy':item.model=='legacy-unrecorded'}


@router.get('/works/{work_id}/research')
def get_research(work_id:str,kind:Literal['translation','analysis'],language:Literal['zh-CN','en'],run_id:str|None=None,page:int=1,page_size:int=20):
    with SessionLocal() as db:
        work=db.scalar(select(Work).where(Work.id==work_id,Work.owner_id=='local-user'))
        if not work:return JSONResponse(status_code=404,content={'message':'作品不存在。'})
        source=db.scalar(select(Transcript).where(Transcript.work_id==work_id,Transcript.owner_id=='local-user',Transcript.kind=='SOURCE',Transcript.status=='COMPLETED'))
        text=source.text if source else ''
        items=db.scalars(select(ResearchRun).where(ResearchRun.work_id==work_id,ResearchRun.owner_id=='local-user',ResearchRun.kind==kind,ResearchRun.language==language).order_by(ResearchRun.created_at.desc(),ResearchRun.id)).all()
        history=[run_json(item,text or '') for item in items]
        if run_id and not any(item.id==run_id for item in items):
            extra=db.scalar(select(ResearchRun).where(ResearchRun.id==run_id,ResearchRun.work_id==work_id,ResearchRun.owner_id=='local-user',ResearchRun.kind==kind,ResearchRun.language==language))
            if extra:history.append(run_json(extra,text or ''))
        if not history and kind=='analysis':
            legacy=db.scalar(select(Analysis).where(Analysis.work_id==work_id,Analysis.owner_id=='local-user',Analysis.analysis_language==language))
            if legacy:history=[{'id':legacy.id,'kind':kind,'language':language,'status':legacy.status,'result':legacy.result,'source_text':text,'source_stale':False,'legacy':True,'completed_units':0,'total_units':1,'error_summary':legacy.error_summary,'created_at':legacy.created_at}]
        for run in history:run['evidence_verified']=kind=='analysis' and verified(run['result'],run['source_text'] or '') if run['result'] else False
        page_data=paginated(history,page,page_size)
        selected=next((run for run in history if run['id']==run_id),None)
        if selected and not any(run['id']==run_id for run in page_data['items']):page_data['items'].append(selected)
        return {'source_ready':bool(text),'source_language':source.language if source else None,'history':page_data['items'],'paging':{key:value for key,value in page_data.items() if key!='items'}}


@router.post('/works/{work_id}/research',status_code=202)
def start_research(work_id:str,body:ResearchInput,background_tasks:BackgroundTasks):
    settings=Settings()
    with SessionLocal() as db:
        try:item=prepare_research(db,work_id,body,settings)
        except ProviderError as error:return JSONResponse(status_code=404 if error.code=='work_not_found' else 409,content={'message':str(error)})
        db.commit();run_id=item.id
    background_tasks.add_task(process_research,run_id,settings)
    return {'run_id':run_id,'message':'译稿任务已开始。' if body.kind=='translation' else '分析任务已开始。'}
