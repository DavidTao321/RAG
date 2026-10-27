"""知识库文档表：上传文件的元数据与处理状态机。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base

# 支持的文件类型
ALLOWED_FILE_TYPES = ("pdf", "docx", "xlsx", "txt", "md")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # 原始文件名（展示用）
    stored_name: Mapped[str] = mapped_column(String(64), nullable=False)  # uuid 存储名（避中文路径）
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)  # pdf/docx/xlsx/txt/md
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # sha256 去重
    # pending → processing → done / failed
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
