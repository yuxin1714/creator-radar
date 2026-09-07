from sqlalchemy import select
from app.models.work import CreationVersion


def record_version(db, project, brief):
    snapshot = {key: getattr(project, key) for key in ("title", "idea", "body", "output_language")}
    snapshot["brief"] = None if brief is None else {
        key: getattr(brief, key) for key in ("platform", "content_type", "direction", "style", "playbook_id")
    }
    latest = db.scalar(select(CreationVersion).where(CreationVersion.project_id == project.id).order_by(CreationVersion.version_number.desc()))
    if latest and latest.snapshot == snapshot:
        return
    db.add(CreationVersion(project_id=project.id, version_number=latest.version_number + 1 if latest else 1, snapshot=snapshot))
    db.flush()
