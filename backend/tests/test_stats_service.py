"""问答统计落库：record_query 字段完整写入、超长问题截断、默认值。"""
from sqlalchemy import select

from app.models import QueryStats
from app.services.stats_service import record_query


async def test_record_query_writes_all_fields(db_session):
    """全部字段（含耗时、token、缓存命中、模型名）按传入值落库。"""
    await record_query(
        db_session,
        user_id=1,
        conversation_id=2,
        message_id=3,
        question="电池多大？",
        retrieval_ms=10,
        rerank_ms=20,
        llm_ms=30,
        total_ms=60,
        prompt_tokens=100,
        completion_tokens=50,
        cache_hit=True,
        model="qwen-plus",
    )
    await db_session.commit()
    row = (await db_session.execute(select(QueryStats))).scalars().one()
    assert row.user_id == 1 and row.conversation_id == 2 and row.message_id == 3
    assert row.question == "电池多大？"
    assert (row.retrieval_ms, row.rerank_ms, row.llm_ms, row.total_ms) == (10, 20, 30, 60)
    assert (row.prompt_tokens, row.completion_tokens) == (100, 50)
    assert row.cache_hit is True and row.model == "qwen-plus"


async def test_record_query_truncates_long_question(db_session):
    """超过 2000 字符的问题被截断存储。"""
    await record_query(db_session, user_id=1, conversation_id=None, message_id=None, question="问" * 3000)
    await db_session.commit()
    row = (await db_session.execute(select(QueryStats))).scalars().one()
    assert len(row.question) == 2000


async def test_record_query_defaults(db_session):
    """未传的耗时/token/缓存字段取默认值 0/False/None。"""
    await record_query(db_session, user_id=1, conversation_id=None, message_id=None, question="q")
    await db_session.commit()
    row = (await db_session.execute(select(QueryStats))).scalars().one()
    assert row.retrieval_ms == 0 and row.total_ms == 0
    assert row.cache_hit is False and row.model is None
