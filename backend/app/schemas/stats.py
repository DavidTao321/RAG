"""数据看板统计模型（P1）。"""
from pydantic import BaseModel


class StatsOverview(BaseModel):
    user_count: int
    document_count: int
    chunk_count: int
    qa_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    feedback_like: int
    feedback_dislike: int


class QaTrendPoint(BaseModel):
    date: str
    count: int
    cache_hit_count: int


class PerformanceStats(BaseModel):
    avg_retrieval_ms: float
    avg_rerank_ms: float
    avg_llm_ms: float
    avg_total_ms: float
    cache_hit_rate: float
    total_qa: int
