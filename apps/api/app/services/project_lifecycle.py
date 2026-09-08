from datetime import datetime,timezone
from typing import Literal
from pydantic import BaseModel
from sqlalchemy import select
from app.models.work import CreationProject,CreationGeneration
from app.providers.base import ProviderError


class ProjectStatusInput(BaseModel):
    status:Literal['DRAFT','COMPLETED','ARCHIVED']
    expected_updated_at:datetime


def change_project_status(db,project_id,body):
    project=db.scalar(select(CreationProject).where(CreationProject.id==project_id,CreationProject.owner_id=='local-user').with_for_update())
    if not project:raise ProviderError('project_not_found','创作项目不存在。')
    normalize=lambda date:date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)
    if normalize(project.updated_at)!=normalize(body.expected_updated_at):raise ProviderError('project_conflict','项目已在其他页面更新，请刷新后重试。')
    if db.scalar(select(CreationGeneration.id).where(CreationGeneration.project_id==project_id,CreationGeneration.status.in_(['PENDING','PROCESSING']))):
        raise ProviderError('generation_running','生成任务运行中，完成后再改变项目状态。')
    if project.status=='ARCHIVED' and body.status=='COMPLETED':raise ProviderError('project_archived','请先恢复为草稿。')
    if body.status=='COMPLETED' and not (project.body or '').strip():raise ProviderError('body_required','先保存正文，再标记完成。')
    project.status=body.status;db.commit();db.refresh(project)
    return {'status':project.status,'updated_at':project.updated_at.isoformat()}
