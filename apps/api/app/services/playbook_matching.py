from typing import Literal
from sqlalchemy import ForeignKey, JSON, select
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel, Field
from app.db import Base
from app.models.work import PlaybookSource, PlaybookRevision
from app.services.creation_playbooks import PLAYBOOKS


class PlaybookRouting(Base):
    __tablename__='playbook_routing'
    source_id:Mapped[str]=mapped_column(ForeignKey('playbook_sources.id',ondelete='CASCADE'),primary_key=True)
    criteria:Mapped[dict]=mapped_column(JSON)


class MatchingInput(BaseModel):
    platforms:list[Literal['tiktok','instagram','x','douyin','xiaohongshu']]=Field(default_factory=list,max_length=5)
    content_types:list[Literal['knowledge','technology','business','commentary','story','tutorial']]=Field(default_factory=list,max_length=6)
    directions:list[Literal['structure_borrowing','opinion_reverse','cross_domain','deep_expand','platform_adapt']]=Field(default_factory=list,max_length=5)
    styles:list[Literal['professional','friendly','sharp','storytelling','concise']]=Field(default_factory=list,max_length=5)


def criteria_for(db,source_id):
    saved=db.get(PlaybookRouting,source_id)
    if saved:return saved.criteria
    if source_id=='tki-content-creation':return MatchingInput(content_types=['story'],styles=['storytelling']).model_dump()
    return MatchingInput().model_dump()


def recommend_playbooks(db,platform,content_type,direction,style):
    selected={'platforms':platform,'content_types':content_type,'directions':direction,'styles':style}
    ranked=[]
    for source in db.scalars(select(PlaybookSource).where(PlaybookSource.status=='ACTIVE')):
        if not source.revision or not db.get(PlaybookRevision,f'{source.id}:{source.revision}'):continue
        criteria=criteria_for(db,source.id)
        constrained=[key for key in selected if criteria.get(key)]
        # Unconfigured skills remain manually selectable; do not guess applicability.
        if not constrained or any(selected[key] not in criteria[key] for key in constrained):continue
        ranked.append({'id':source.id,'name':source.name,'matched_fields':constrained})
    ranked.sort(key=lambda item:(-len(item['matched_fields']),item['id']))
    ranked.append({'id':'structure-borrowing-v1','name':PLAYBOOKS['structure-borrowing-v1']['name'],'matched_fields':[]})
    return ranked
