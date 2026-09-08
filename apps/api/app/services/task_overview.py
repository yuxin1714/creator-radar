from sqlalchemy import select
from app.models.work import Task, Work, Transcript, Analysis, CreationProject, CreationGeneration, GenerationInput


def task_overview(db):
    items = []
    for model, kind, tab in [(Task, "metadata", None), (Transcript, "transcript", "transcript"), (Analysis, "analysis", "analysis")]:
        rows = db.execute(select(model, Work).join(Work, model.work_id == Work.id).where(model.owner_id == "local-user", Work.owner_id == "local-user").order_by(model.created_at.desc()).limit(200)).all()
        for task, work in rows:
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
                      "href": f"/creation/{project.id}"})
    return sorted(items, key=lambda item: item["created_at"], reverse=True)[:200]
