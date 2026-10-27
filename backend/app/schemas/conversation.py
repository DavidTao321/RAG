"""会话与消息相关模型。"""
from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=100)


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReferenceOut(BaseModel):
    """单条引用片段。"""
    index: int
    doc_id: int
    doc_name: str
    content: str
    score: float | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    references: list[ReferenceOut] | None = None
    model: str | None = None
    cache_hit: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}
