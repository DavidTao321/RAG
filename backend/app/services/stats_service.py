"""问答统计服务：记录每次问答的性能与用量数据。"""
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import QueryStats


async def record_query(
    db: AsyncSession,
    *,
    user_id: int,
    conversation_id: int | None,
    message_id: int | None,
    question: str,
    retrieval_ms: int = 0,
    rerank_ms: int = 0,
    llm_ms: int = 0,
    total_ms: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cache_hit: bool = False,
    model: str | None = None,
) -> None:
    db.add(
        QueryStats(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            question=question[:2000],
            retrieval_ms=retrieval_ms,
            rerank_ms=rerank_ms,
            llm_ms=llm_ms,
            total_ms=total_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_hit=cache_hit,
            model=model,
        )
    )
