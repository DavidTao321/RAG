"""系统键值表：存储知识库版本号等全局状态（kb_version 用于语义缓存失效）。"""
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SystemKV(Base):
    __tablename__ = "system_kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
