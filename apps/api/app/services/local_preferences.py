from typing import Literal
from sqlalchemy import String,JSON,Integer
from sqlalchemy.orm import Mapped,mapped_column
from pydantic import BaseModel,Field
from app.db import Base


class LocalPreference(Base):
    __tablename__='local_preferences'
    owner_id:Mapped[str]=mapped_column(String(36),primary_key=True)
    values:Mapped[dict]=mapped_column(JSON,default=dict)
    revision:Mapped[int]=mapped_column(Integer,default=0)


class LocalPreferenceInput(BaseModel):
    default_output_language:Literal['zh-CN','en','zh-en']='zh-CN'
    default_platform:Literal['tiktok','instagram','x','douyin','xiaohongshu']='tiktok'
    expected_revision:int=Field(default=0,ge=0)


def local_preferences(db):
    saved=db.get(LocalPreference,'local-user')
    return {'default_output_language':'zh-CN','default_platform':'tiktok',**(saved.values if saved else {}),'revision':saved.revision if saved else 0}
