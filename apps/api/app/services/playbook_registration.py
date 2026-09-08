import hashlib
import re
from pathlib import PurePosixPath
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field, field_validator
from app.models.work import PlaybookSource


class RemotePlaybookInput(BaseModel):
    name: str = Field(min_length=1,max_length=200)
    repository_url: str = Field(max_length=500)
    skill_path: str = Field(max_length=500)

    @field_validator('name')
    @classmethod
    def clean_name(cls,value):
        if not value.strip():raise ValueError('名称不能为空')
        return value.strip()

    @field_validator('repository_url')
    @classmethod
    def clean_repository(cls,value):
        value=value.strip().rstrip('/')
        if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',value):raise ValueError('仅支持 GitHub HTTPS 仓库地址')
        return value[:-4] if value.endswith('.git') else value

    @field_validator('skill_path')
    @classmethod
    def clean_path(cls,value):
        value=value.strip();path=PurePosixPath(value)
        if not value or path.is_absolute() or '..' in path.parts or '\\' in value or path.name!='SKILL.md' or str(path)!=value:
            raise ValueError('请输入仓库内 SKILL.md 的相对路径')
        return value


def register_remote(db,body):
    for existing in db.scalars(select(PlaybookSource).where(PlaybookSource.source_type=='remote')):
        old=(existing.repository_url or '').rstrip('/')
        if old.endswith('.git'):old=old[:-4]
        if old.lower()==body.repository_url.lower() and existing.skill_path==body.skill_path:return existing,False
    key=body.repository_url.lower()+'\n'+body.skill_path
    source_id='remote-'+hashlib.sha256(key.encode()).hexdigest()[:24]
    item=PlaybookSource(id=source_id,name=body.name,source_type='remote',repository_url=body.repository_url,skill_path=body.skill_path)
    db.add(item)
    try:db.commit()
    except IntegrityError:
        db.rollback();item=db.get(PlaybookSource,source_id)
        if not item:raise
        return item,False
    return item,True
