import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Work(Base):
    __tablename__ = "works"
    __table_args__ = (UniqueConstraint("owner_id", "platform", "external_id", name="uq_work_owner_platform_external"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), default="local-user", index=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    external_id: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str] = mapped_column(String(2000))
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), default="local-user", index=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), index=True)
    task_type: Mapped[str] = mapped_column(String(40), default="PROCESS_WORK")
    stage: Mapped[str] = mapped_column(String(50), default="WAITING_PROVIDER")
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class WorkMetadata(Base):
    __tablename__ = "work_metadata"
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (UniqueConstraint("owner_id", "work_id", "kind", name="uq_transcript_owner_work_kind"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), default="local-user", index=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="SOURCE")
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    language: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    segments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("owner_id", "work_id", name="uq_analysis_owner_work"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), default="local-user", index=True)
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    analysis_language: Mapped[str] = mapped_column(String(30), default="zh-CN")
    schema_version: Mapped[str] = mapped_column(String(20), default="0.1")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class CreationProject(Base):
    __tablename__ = "creation_projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), default="local-user", index=True)
    title: Mapped[str] = mapped_column(String(200), default="未命名创作")
    context_type: Mapped[str] = mapped_column(String(20), default="idea")
    work_id: Mapped[str | None] = mapped_column(ForeignKey("works.id", ondelete="SET NULL"), nullable=True)
    idea: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_language: Mapped[str] = mapped_column(String(20), default="zh-CN")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class CreationBrief(Base):
    __tablename__ = "creation_briefs"
    project_id: Mapped[str] = mapped_column(ForeignKey("creation_projects.id", ondelete="CASCADE"), primary_key=True)
    platform: Mapped[str] = mapped_column(String(30), default="tiktok")
    content_type: Mapped[str] = mapped_column(String(50), default="knowledge")
    direction: Mapped[str] = mapped_column(String(50), default="structure_borrowing")
    style: Mapped[str] = mapped_column(String(50), default="professional")
    playbook_id: Mapped[str] = mapped_column(String(80), default="structure-borrowing-v1")
