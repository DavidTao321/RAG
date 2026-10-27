"""Chroma 向量库封装（嵌入式持久化，单例）。

chromadb 1.x：必须显式创建 PersistentClient 再传给 langchain_chroma.Chroma。
chunks 表是事实源，Chroma 是索引副本——本模块提供按 document_id 的增删能力。

并发安全：嵌入式 Chroma 的初始化与写操作用 threading.Lock 串行化，
避免多任务同时首次访问时的 SQLite/tenant 竞争（实测踩坑：并发初始化会
报 "Could not connect to tenant default_tenant" 与 "RustBindingsAPI no attribute bindings"）。
"""
from __future__ import annotations

import threading
import uuid

import chromadb
from langchain_chroma import Chroma

from ...config import settings

_client: chromadb.PersistentClient | None = None
_store: Chroma | None = None
_lock = threading.Lock()

COLLECTION_NAME = "kb_products"  # chromadb 要求 3-512 字符，"kb" 不合法


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return _client


def get_vector_store() -> Chroma:
    global _store
    if _store is None:
        from .llm_factory import get_embeddings

        _store = Chroma(
            client=get_client(),
            collection_name=COLLECTION_NAME,
            embedding_function=get_embeddings(),
            collection_metadata={"hnsw:space": "cosine"},
        )
    return _store


def reset_singletons() -> None:
    """清空单例（测试用）。"""
    global _client, _store
    _client = None
    _store = None


def _collection_exists() -> bool:
    try:
        return COLLECTION_NAME in {c.name for c in get_client().list_collections()}
    except Exception:  # noqa: BLE001 空库/损坏时视为不存在
        return False


def add_chunks(doc_id: int, doc_name: str, contents: list[str], embeddings: list[list[float]]) -> None:
    """将一批分块写入 Chroma。metadata 保存溯源信息。"""
    if not contents:
        return
    with _lock:
        store = get_vector_store()
        ids = [uuid.uuid4().hex for _ in contents]
        metadatas = [
            {"document_id": doc_id, "doc_name": doc_name, "chunk_index": i}
            for i in range(len(contents))
        ]
        store._collection.upsert(  # noqa: SLF001 直接操作底层 collection 以传入预计算向量
            ids=ids,
            embeddings=embeddings,
            documents=contents,
            metadatas=metadatas,
        )


def delete_by_document(doc_id: int) -> None:
    """删除某文档的全部向量（collection 不存在时静默跳过）。"""
    with _lock:
        if not _collection_exists():
            return
        get_client().get_collection(COLLECTION_NAME).delete(where={"document_id": doc_id})


def count_by_document(doc_id: int) -> int:
    """统计某文档的向量条数（验收/调试用）。"""
    with _lock:
        if not _collection_exists():
            return 0
        col = get_client().get_collection(COLLECTION_NAME)
        return len(col.get(where={"document_id": doc_id}, include=[])["ids"])
