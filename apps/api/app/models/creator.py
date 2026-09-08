import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.db import Base
from app.models.work import utcnow


class Creator(Base):
    __tablename__ = "creators"
    __table_args__ = (UniqueConstraint("owner_id", "platform", "external_id", name="uq_creator_owner_platform_external"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), default="local-user", index=True)
    platform: Mapped[str] = mapped_column(String(20), default="douyin")
    external_id: Mapped[str] = mapped_column(String(150))
    name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(500))
    daily: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_new_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CreatorWork(Base):
    __tablename__ = "creator_works"
    creator_id: Mapped[str] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"), primary_key=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
