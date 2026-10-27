"""问答编排（系统核心）：SSE 异步生成器，串联 缓存 → 混合检索 → 重排 → 生成 → 落库。

事件协议：meta → delta* → references → done；任一阶段异常发 error 帧。
性能统计（分段耗时/token/缓存命中）落 messages 与 query_stats 两张表（论文数据来源）。
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime
from typing import AsyncGenerator

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.exceptions import BusinessError, forbidden, not_found
from ..models import Conversation, Message, User
from ..schemas.chat import ChatRequest
from ..utils.sse import sse_error_frame, sse_frame
from ..utils.text import make_title
from .cache import get_cache
from .cache.base import CachedAnswer
from .kb_version import get_kb_version
from .rag.bm25 import get_global_index
from .rag.citations import build_references, extract_cited_indices, renumber_citations
from .rag.hybrid_retriever import HybridRetriever
from .rag.llm_factory import get_embeddings, get_llm
from .rag.prompt_builder import build_messages
from .rag.reranker import DashScopeReranker
from .stats_service import record_query

logger = logging.getLogger(__name__)

CITATION_STRIP_RE = re.compile(r"\[(\d+(?:[,\s]\d+)*)\]")
FALLBACK_ANSWER = "抱歉，知识库中未包含与该问题相关的信息，建议联系人工客服进一步咨询。"
REPLAY_CHUNK_SIZE = 20  # 缓存回放分片字符数


async def _get_or_create_conversation(db: AsyncSession, user: User, conversation_id: int | None) -> Conversation:
    if conversation_id is None:
        conv = Conversation(user_id=user.id)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv
    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise not_found("会话不存在")
    if conv.user_id != user.id:
        raise forbidden("无权访问该会话")
    return conv


async def _load_history(db: AsyncSession, conversation_id: int, rounds: int) -> list[tuple[str, str]]:
    """加载最近 N 轮对话（不含刚发送的当前问题），剥离历史答案中的引用编号。"""
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(rounds * 2)
        )
    ).scalars().all()
    rows.reverse()
    history: list[tuple[str, str]] = []
    for m in rows:
        content = m.content
        if m.role == "assistant":
            content = CITATION_STRIP_RE.sub("", content)
        history.append((m.role, content[:1500]))
    return history


def _build_retrieval_query(question: str, history: list[tuple[str, str]]) -> str:
    """短问题（如"它支持快充吗"）拼接上一轮用户消息，解决多轮指代问题。"""
    if len(question) <= 20:
        for role, content in reversed(history):
            if role == "user":
                return f"{content} {question}"
    return question


async def _embed_query(text: str) -> np.ndarray:
    vec = await get_embeddings().aembed_query(text)
    return np.asarray(vec, dtype="float32")


async def stream_chat(user: User, body: ChatRequest, db: AsyncSession) -> AsyncGenerator[str, None]:
    """SSE 流式问答主链路。"""
    t0 = time.perf_counter()
    question = body.question.strip()
    model = settings.llm_model
    retrieval_ms = rerank_ms = llm_ms = 0
    prompt_tokens = completion_tokens = 0

    try:
        # ---- 会话与历史 ----
        conversation = await _get_or_create_conversation(db, user, body.conversation_id)
        history = await _load_history(db, conversation.id, settings.context_history_rounds)

        # ---- 保存用户消息 + 更新会话标题 ----
        user_msg = Message(
            conversation_id=conversation.id, user_id=user.id, role="user", content=question
        )
        db.add(user_msg)
        if conversation.title == "新会话":
            conversation.title = make_title(question)
        conversation.updated_at = datetime.now()
        await db.commit()

        kb_version = await get_kb_version(db)
        retrieval_query = _build_retrieval_query(question, history)

        # ---- 语义缓存（相似问题命中直接回放，跳过检索与生成）----
        # 注意：缓存匹配用原始问题的向量；检索用的拼接 query 会包含上文，
        # 若用于缓存会把追问（"它支持快充吗"）误判为上一问的相似问题
        cache = get_cache()
        q_embedding = await _embed_query(question)
        cached = await cache.lookup(question, q_embedding, kb_version)

        if cached is not None:
            total_ms = int((time.perf_counter() - t0) * 1000)
            yield sse_frame("meta", {"conversation_id": conversation.id, "message_id": None, "model": cached.model or model, "cache_hit": True})
            # 按分片模拟流式回放，用户体验一致
            for i in range(0, len(cached.answer), REPLAY_CHUNK_SIZE):
                yield sse_frame("delta", {"content": cached.answer[i : i + REPLAY_CHUNK_SIZE]})
            assistant = Message(
                conversation_id=conversation.id,
                user_id=user.id,
                role="assistant",
                content=cached.answer,
                references_json=cached.references,
                model=cached.model or model,
                cache_hit=True,
                total_ms=total_ms,
            )
            db.add(assistant)
            await db.commit()
            await db.refresh(assistant)
            await record_query(
                db, user_id=user.id, conversation_id=conversation.id, message_id=assistant.id,
                question=question, total_ms=total_ms, cache_hit=True, model=model,
            )
            await db.commit()
            yield sse_frame("references", cached.references)
            yield sse_frame("done", {
                "message_id": assistant.id, "total_ms": total_ms, "retrieval_ms": 0,
                "rerank_ms": 0, "llm_ms": 0, "prompt_tokens": 0, "completion_tokens": 0,
                "cache_hit": True,
            })
            return

        yield sse_frame("meta", {"conversation_id": conversation.id, "message_id": None, "model": model, "cache_hit": False})

        # ---- 混合检索（向量 + BM25，并行，RRF 融合）----
        t_ret = time.perf_counter()
        retriever = HybridRetriever(
            bm25_index=get_global_index(),
            top_k=settings.retrieval_top_k,
            rrf_k=settings.rrf_k,
            fusion_top_n=max(settings.rerank_top_n * 2, 8),
        )
        docs = await retriever.ainvoke(retrieval_query)
        retrieval_ms = int((time.perf_counter() - t_ret) * 1000)

        # ---- 重排（qwen3-rerank 精排 + 阈值过滤）----
        t_rer = time.perf_counter()
        reranker = DashScopeReranker(top_n=settings.rerank_top_n, threshold=settings.rerank_score_threshold)
        docs = await asyncio.to_thread(reranker.compress_documents, docs, retrieval_query)
        rerank_ms = int((time.perf_counter() - t_rer) * 1000)

        refs = build_references(docs)

        # ---- 无相关内容：兜底话术，不调用 LLM、不编造 ----
        if not refs:
            answer = FALLBACK_ANSWER
            assistant = Message(
                conversation_id=conversation.id, user_id=user.id, role="assistant",
                content=answer, references_json=[], model=model, cache_hit=False,
                retrieval_ms=retrieval_ms, rerank_ms=rerank_ms, llm_ms=0,
                total_ms=int((time.perf_counter() - t0) * 1000),
            )
            db.add(assistant)
            await db.commit()
            await db.refresh(assistant)
            await record_query(
                db, user_id=user.id, conversation_id=conversation.id, message_id=assistant.id,
                question=question, retrieval_ms=retrieval_ms, rerank_ms=rerank_ms,
                total_ms=assistant.total_ms, model=model,
            )
            await db.commit()
            yield sse_frame("delta", {"content": answer})
            yield sse_frame("references", [])
            yield sse_frame("done", {
                "message_id": assistant.id, "total_ms": assistant.total_ms,
                "retrieval_ms": retrieval_ms, "rerank_ms": rerank_ms, "llm_ms": 0,
                "prompt_tokens": 0, "completion_tokens": 0, "cache_hit": False,
            })
            return

        # ---- LLM 流式生成 ----
        messages = build_messages(question, refs, history)
        llm = get_llm()
        t_llm = time.perf_counter()
        answer_parts: list[str] = []
        usage = None
        async for chunk in llm.astream(messages):
            delta = chunk.content
            if delta:
                answer_parts.append(delta)
                yield sse_frame("delta", {"content": delta})
            um = getattr(chunk, "usage_metadata", None)
            if um:
                usage = um
        answer = "".join(answer_parts)
        llm_ms = int((time.perf_counter() - t_llm) * 1000)
        if usage:
            # usage_metadata 是 dict（langchain-openai 流式聚合）
            prompt_tokens = int(usage.get("input_tokens", 0) or 0)
            completion_tokens = int(usage.get("output_tokens", 0) or 0)

        # ---- 只保留回答中实际引用的片段，并把编号重排为 [1][2]… ----
        cited = extract_cited_indices(answer, len(refs))
        final_refs = [r for r in refs if r["index"] in cited]
        if cited:
            answer = renumber_citations(answer, cited)
            for new_index, ref in enumerate(final_refs, start=1):
                ref["index"] = new_index
        total_ms = int((time.perf_counter() - t0) * 1000)

        # ---- 落库 assistant 消息 + 统计 ----
        assistant = Message(
            conversation_id=conversation.id, user_id=user.id, role="assistant",
            content=answer, references_json=final_refs, model=model, cache_hit=False,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            retrieval_ms=retrieval_ms, rerank_ms=rerank_ms, llm_ms=llm_ms, total_ms=total_ms,
        )
        db.add(assistant)
        conversation.updated_at = datetime.now()
        await db.commit()
        await db.refresh(assistant)
        await record_query(
            db, user_id=user.id, conversation_id=conversation.id, message_id=assistant.id,
            question=question, retrieval_ms=retrieval_ms, rerank_ms=rerank_ms,
            llm_ms=llm_ms, total_ms=total_ms, prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens, model=model,
        )
        await db.commit()

        yield sse_frame("references", final_refs)
        yield sse_frame("done", {
            "message_id": assistant.id, "total_ms": total_ms, "retrieval_ms": retrieval_ms,
            "rerank_ms": rerank_ms, "llm_ms": llm_ms, "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens, "cache_hit": False,
        })

        # ---- 回写语义缓存（不阻塞响应）----
        try:
            await cache.store(
                question, q_embedding, kb_version,
                CachedAnswer(answer=answer, references=final_refs, model=model),
            )
        except Exception:  # noqa: BLE001
            logger.exception("缓存回写失败（不影响主流程）")
    except BusinessError as e:
        yield sse_error_frame(e.detail)
    except Exception as e:  # noqa: BLE001
        logger.exception("问答链路异常")
        yield sse_error_frame(f"服务异常: {e.__class__.__name__}")
