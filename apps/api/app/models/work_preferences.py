from sqlalchemy import ForeignKey, Boolean, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class WorkPreferences(Base):
    __tablename__ = "work_preferences"
    work_id: Mapped[str] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=0)
