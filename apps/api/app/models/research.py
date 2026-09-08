import uuid
from datetime import datetime
from sqlalchemy import DateTime,ForeignKey,Integer,JSON,String,Text
from sqlalchemy.orm import Mapped,mapped_column
from app.db import Base
from app.models.work import utcnow


class ResearchRun(Base):
    __tablename__='research_runs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=lambda:str(uuid.uuid4()))
    owner_id:Mapped[str]=mapped_column(String(36),default='local-user',index=True)
    work_id:Mapped[str]=mapped_column(ForeignKey('works.id',ondelete='CASCADE'),index=True)
    kind:Mapped[str]=mapped_column(String(20))
    language:Mapped[str]=mapped_column(String(20))
    status:Mapped[str]=mapped_column(String(20),default='PENDING')
    source_text:Mapped[str]=mapped_column(Text)
    source_hash:Mapped[str]=mapped_column(String(64))
    model:Mapped[str]=mapped_column(String(100))
    result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    completed_units:Mapped[int]=mapped_column(Integer,default=0)
    total_units:Mapped[int]=mapped_column(Integer,default=1)
    error_summary:Mapped[str|None]=mapped_column(String(500),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,onupdate=utcnow)
