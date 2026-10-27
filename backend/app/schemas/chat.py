"""问答请求与 SSE 事件数据模型。"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    question: str = Field(min_length=1, max_length=2000)


class ChatMeta(BaseModel):
    """SSE meta 帧。"""
    conversation_id: int
    message_id: int | None = None
    model: str
    cache_hit: bool = False


class ChatDone(BaseModel):
    """SSE done 帧：性能统计（论文数据来源）。"""
    message_id: int
    total_ms: int
    retrieval_ms: int = 0
    rerank_ms: int = 0
    llm_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_hit: bool = False
