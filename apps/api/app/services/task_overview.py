from sqlalchemy import select
from app.models.work import Task, Work, Transcript, Analysis, CreationProject, CreationGeneration, GenerationInput


def task_overview(db):
    from app.models.creator import Creator
    from app.models.research import ResearchRun
    items = []
    research_work_ids=set(db.scalars(select(ResearchRun.work_id).where(ResearchRun.owner_id=='local-user',ResearchRun.kind=='analysis')))
    for creator in db.scalars(select(Creator).where(Creator.owner_id=='local-user').order_by(Creator.created_at.desc()).limit(200)):
        items.append({'id':creator.id,'kind':'monitor','title':creator.name,'stage':'monitor','status':creator.status,
                      'error_summary':creator.error_summary,'created_at':(creator.last_checked_at or creator.created_at).isoformat(),'href':'/creators/'+creator.id})
    for model, kind, tab in [(Task, "metadata", None), (Transcript, "transcript", "transcript"), (Analysis, "analysis", "analysis")]:
        rows = db.execute(select(model, Work).join(Work, model.work_id == Work.id).where(model.owner_id == "local-user", Work.owner_id == "local-user").order_by(model.created_at.desc()).limit(200)).all()
        for task, work in rows:
            if kind=='analysis' and work.id in research_work_ids:continue
            items.append({"id": task.id, "kind": kind, "title": work.title or work.external_id,
                          "work_id": work.id, "platform": work.platform, "external_id": work.external_id,
                          "stage": task.stage if kind == "metadata" else kind,
                          "status": "PROCESSING" if task.status == "RUNNING" else task.status, "error_summary": task.error_summary,
                          "created_at": task.created_at.isoformat(),
                          "href": f"/works/{work.id}" + (f"?tab={tab}" if tab else "")})
    rows = db.execute(select(CreationGeneration, CreationProject, GenerationInput.mode).join(CreationProject, CreationGeneration.project_id == CreationProject.id).outerjoin(GenerationInput, GenerationInput.generation_id == CreationGeneration.id).where(CreationProject.owner_id == "local-user").order_by(CreationGeneration.created_at.desc()).limit(200)).all()
    for task, project, mode in rows:
        items.append({"id": task.id, "kind": "creation", "title": project.title,
                      "stage": mode or "draft", "status": task.status,
                      "error_summary": task.error_summary, "created_at": task.created_at.isoformat(),
                      "href": f"/creation/{project.id}?generation={task.id}"})
    for run,work in db.execute(select(ResearchRun,Work).join(Work,Work.id==ResearchRun.work_id).where(ResearchRun.owner_id=='local-user',Work.owner_id=='local-user').order_by(ResearchRun.created_at.desc()).limit(200)):
        items.append({'id':run.id,'kind':'research','title':work.title or work.external_id,'stage':run.kind+'_'+run.language,'status':run.status,'error_summary':run.error_summary,'created_at':run.created_at.isoformat(),'href':f'/works/{work.id}?tab='+('translation' if run.kind=='translation' else 'analysis')+'&language='+run.language+'&research='+run.id})
    return sorted(items, key=lambda item: item["created_at"], reverse=True)[:200]
