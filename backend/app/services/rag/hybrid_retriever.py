"""混合检索器：向量检索 + BM25 关键词检索并行执行，RRF 融合排序。

LangChain 1.x：继承 langchain_core.retrievers.BaseRetriever，
同步实现 _get_relevant_documents，异步实现 _aget_relevant_documents。
"""
from __future__ import annotations

import asyncio

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from .bm25 import BM25Index
from .vector_store import get_vector_store


class HybridRetriever(BaseRetriever):
    """向量 + BM25 双路检索，RRF（Reciprocal Rank Fusion）融合。"""

    bm25_index: BM25Index | None = Field(default=None, exclude=True)
    top_k: int = 10
    rrf_k: int = 60
    fusion_top_n: int = 8

    def _vector_search(self, query: str) -> list[tuple[Document, float]]:
        store = get_vector_store()
        results = store.similarity_search_with_score(query, k=self.top_k)
        # Chroma 余弦空间返回距离（越小越相似），转为相似度
        return [(doc, 1.0 - score) for doc, score in results]

    def _bm25_search(self, query: str) -> list[tuple[Document, float]]:
        if self.bm25_index is None:
            return []
        out = []
        for bm_doc, score in self.bm25_index.search(query, k=self.top_k):
            out.append(
                (
                    Document(
                        page_content=bm_doc.content,
                        metadata={
                            "document_id": bm_doc.doc_id,
                            "chunk_index": bm_doc.chunk_index,
                            "doc_name": bm_doc.doc_name,
                        },
                    ),
                    score,
                )
            )
        return out

    @staticmethod
    def _rrf_fuse(
        ranked_lists: list[list[tuple[Document, float]]], rrf_k: int, top_n: int
    ) -> list[Document]:
        """RRF 融合：score(d) = Σ 1/(k + rank)。按 (document_id, chunk_index) 去重。"""
        fused: dict[tuple, tuple[Document, float]] = {}
        for ranked in ranked_lists:
            for rank, (doc, _score) in enumerate(ranked):
                key = (doc.metadata.get("document_id"), doc.metadata.get("chunk_index"))
                rrf_score = 1.0 / (rrf_k + rank + 1)
                if key in fused:
                    fused[key] = (fused[key][0], fused[key][1] + rrf_score)
                else:
                    fused[key] = (doc, rrf_score)
        merged = sorted(fused.values(), key=lambda x: x[1], reverse=True)
        out = []
        for doc, rrf_score in merged[:top_n]:
            doc.metadata["score"] = round(rrf_score, 6)
            out.append(doc)
        return out

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun | None = None
    ) -> list[Document]:
        vec = self._vector_search(query)
        bm = self._bm25_search(query)
        return self._rrf_fuse([vec, bm], self.rrf_k, self.fusion_top_n)

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun | None = None
    ) -> list[Document]:
        # 两路并行（向量库为同步 API，转线程池执行）
        vec, bm = await asyncio.gather(
            asyncio.to_thread(self._vector_search, query),
            asyncio.to_thread(self._bm25_search, query),
        )
        return self._rrf_fuse([vec, bm], self.rrf_k, self.fusion_top_n)
