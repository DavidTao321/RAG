"""文档入库管线：解析 → 分块 → 批量向量化 → 双写（Chroma + chunks 表）。

上传接口只做落盘与建行，随后 create_task 调用本模块的后台任务。
解析（pandas/pdf）为同步阻塞操作，统一放入线程池。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import tenacity
from sqlalchemy import delete, select

from ..config import settings
from ..database import async_session
from ..models import Chunk, Document
from .kb_version import bump_kb_version
from .parsers import parse_file
from .rag import bm25
from .rag.llm_factory import get_embeddings
from .rag.vector_store import add_chunks
from .splitter import split_text

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 25
# 同时入库的文档数上限：避免 DashScope QPS 配额击穿与 Chroma 写竞争
MAX_CONCURRENT_DOCS = 3
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOCS)

# 持有后台任务强引用，防止被 GC 取消
_background_tasks: set[asyncio.Task] = set()


def schedule_ingestion(document_id: int) -> None:
    task = asyncio.get_event_loop().create_task(process_document(document_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _embed_with_retry(batch: list[str]) -> list[list[float]]:
    """批量向量化 + 指数退避重试（DashScope 有 QPS 配额）。"""
    retryer = tenacity.Retrying(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=15),
        reraise=True,
    )

    def _call():
        return get_embeddings().embed_documents(batch)

    return retryer(_call)


async def process_document(document_id: int) -> None:
    """后台任务：状态机 pending → processing → done/failed。"""
    async with _semaphore:
        await _process_document_impl(document_id)


async def _process_document_impl(document_id: int) -> None:
    async with async_session() as db:
        doc = await db.get(Document, document_id)
        if doc is None or doc.status in ("done", "processing"):
            return
        doc.status = "processing"
        doc.error_msg = None
        await db.commit()

    path = settings.upload_dir / doc.stored_name
    try:
        # 1. 解析 + 分块（同步阻塞 → 线程池）
        text = await asyncio.to_thread(parse_file, str(path), doc.file_type)
        chunks_text = await asyncio.to_thread(split_text, text, doc.file_type)
        if not chunks_text:
            raise ValueError("文档解析后没有有效内容")

        # 2. 批量向量化（25 条/批，减少 API 调用次数）
        embeddings: list[list[float]] = []
        for i in range(0, len(chunks_text), EMBED_BATCH_SIZE):
            batch = chunks_text[i : i + EMBED_BATCH_SIZE]
            embeddings.extend(await asyncio.to_thread(_embed_with_retry, batch))

        # 3. 写 chunks 表（事实源）
        async with async_session() as db:
            db.add_all(
                [
                    Chunk(
                        document_id=doc.id,
                        chunk_index=i,
                        content=c,
                        char_count=len(c),
                    )
                    for i, c in enumerate(chunks_text)
                ]
            )
            await db.commit()

        # 4. 写 Chroma（索引副本）
        await asyncio.to_thread(add_chunks, doc.id, doc.filename, chunks_text, embeddings)

        # 5. 完成：状态 + 知识库版本号 + 重建 BM25
        async with async_session() as db:
            doc = await db.get(Document, document_id)
            doc.status = "done"
            doc.chunk_count = len(chunks_text)
            await db.commit()
            await bump_kb_version(db)
            await db.commit()
            await bm25.rebuild_global_index(db)
        logger.info("文档入库完成 id=%s chunks=%d", document_id, len(chunks_text))
    except Exception as e:  # noqa: BLE001
        logger.exception("文档入库失败 id=%s", document_id)
        async with async_session() as db:
            doc = await db.get(Document, document_id)
            if doc is not None:
                doc.status = "failed"
                doc.error_msg = str(e)[:1000]
                await db.commit()


async def remove_document_data(doc_id: int) -> None:
    """清理某文档的全部数据：chunks 表 + Chroma 向量。"""
    async with async_session() as db:
        await db.execute(delete(Chunk).where(Chunk.document_id == doc_id))
        await db.commit()
    from .rag.vector_store import delete_by_document

    await asyncio.to_thread(delete_by_document, doc_id)
