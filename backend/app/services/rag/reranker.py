"""DashScope 重排序器：qwen3-rerank 精排（gte-rerank 已于 2026-05 停服）。

实现 LangChain 的 BaseDocumentCompressor 接口（可直接嵌入 ContextualCompressionRetriever），
也可单独调用 compress_documents。relevance_score 低于阈值的片段被丢弃；
调用失败时降级为原顺序返回，保证问答主链路可用性优先。
"""
from __future__ import annotations

import logging

import dashscope
from langchain_core.callbacks import Callbacks
from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor
from pydantic import Field

from ...config import settings

logger = logging.getLogger(__name__)


class DashScopeReranker(BaseDocumentCompressor):
    """qwen3-rerank 精排压缩器。"""

    top_n: int = Field(default=5, ge=1)
    threshold: float = Field(default=0.1, ge=0.0, le=1.0)

    def compress_documents(
        self,
        documents: list[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> list[Document]:
        """对候选片段调用 qwen3-rerank 精排，按 relevance_score 降序返回。"""
        if not documents:
            return []
        if len(documents) == 1:
            return documents
        try:
            resp = dashscope.TextReRank.call(
                model=settings.rerank_model,
                query=query,
                documents=[d.page_content for d in documents],
                top_n=min(self.top_n, len(documents)),
                return_documents=True,
            )
            if resp.status_code != 200:
                logger.warning(
                    "rerank 调用失败 code=%s msg=%s，降级为原顺序", resp.status_code, getattr(resp, "message", "")
                )
                return documents[: self.top_n]
            out: list[Document] = []
            for r in resp.output.results:
                score = r.get("relevance_score", 0.0)
                if score < self.threshold:
                    continue
                src = documents[r["index"]]
                text = r.get("document", {}).get("text") or src.page_content
                doc = Document(page_content=text, metadata=dict(src.metadata))
                doc.metadata["score"] = round(float(score), 6)
                out.append(doc)
            return out
        except Exception:  # noqa: BLE001 网络/配额异常均降级，不影响主链路
            logger.exception("rerank 异常，降级为原顺序")
            return documents[: self.top_n]
