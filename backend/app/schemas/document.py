"""知识库文档相关模型。"""
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    error_msg: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkOut(BaseModel):
    id: int
    chunk_index: int
    content: str
    char_count: int

    model_config = {"from_attributes": True}
