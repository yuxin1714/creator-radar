from datetime import timedelta
from sqlalchemy import select, or_
from app.models.work import Work, WorkMetadata, Transcript, Analysis, utcnow
from app.models.work_preferences import WorkPreferences
from app.services.analysis_validation import validate_analysis


def daily_brief(db, now=None):
    now=now or utcnow()
    rows=db.execute(select(Work,WorkMetadata,Transcript,Analysis).outerjoin(WorkMetadata,WorkMetadata.work_id==Work.id).outerjoin(Transcript,(Transcript.work_id==Work.id)&(Transcript.owner_id=='local-user')&(Transcript.kind=='SOURCE')).outerjoin(Analysis,(Analysis.work_id==Work.id)&(Analysis.owner_id=='local-user')).outerjoin(WorkPreferences,WorkPreferences.work_id==Work.id).where(Work.owner_id=='local-user',Work.created_at>=now-timedelta(days=7),or_(WorkPreferences.work_id.is_(None),WorkPreferences.archived.is_(False))).order_by(Work.created_at.desc(),Work.id)).all()
    ready=[];pending=[]
    for work,meta,transcript,analysis in rows:
        base={'id':work.id,'title':work.title or work.external_id,'author':meta.author_name if meta else None,'platform':work.platform,'published_at':meta.published_at if meta else None,'collected_at':work.created_at}
        if analysis and analysis.status=='COMPLETED' and transcript and transcript.status=='COMPLETED':
            try:
                result=validate_analysis(analysis.result,transcript.text or '')
                ready.append({**base,'summary':result['summary'],'reasons':result['score_reasons'][:3],'score':result['content_score'],'evidence':result['evidence'][:1]})
                continue
            except (ValueError,TypeError):pass
        has_transcript=bool(transcript and transcript.status=='COMPLETED')
        pending.append({**base,'reason':'分析引用待核验' if analysis and analysis.status=='COMPLETED' else '可开始内容分析' if has_transcript else '待获取逐字稿','href':f'/works/{work.id}?tab='+('analysis' if has_transcript else 'transcript')})
    ready.sort(key=lambda item:(-item['score'],item['id']))
    pending.sort(key=lambda item:(-(item['published_at'].timestamp() if item['published_at'] else 0),item['id']))
    return {'generated_at':now,'window_days':7,'candidate_count':len(rows),'ready_count':len(ready),'pending_count':len(pending),'picks':ready[:5],'pending':pending[:3]}
