"""BM25 关键词检索（jieba 分词 + 自实现 BM25Okapi，约百行，无额外依赖）。

维护一份内存倒排索引，从 chunks 表全量加载；文档增删后由服务层调用 rebuild。
单知识库 2 万 chunk 规模下检索耗时毫秒级。
"""
from __future__ import annotations

import asyncio
import math
from collections import Counter
from dataclasses import dataclass, field

import jieba

# 常见中文停用词（电商场景精简集）
STOPWORDS = frozenset(
    "的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 那 之 与 及 或 被 把 让 给 对 于 吗 呢 啊 吧 么 什么 怎么 为什么 哪个 哪些 多少 可以 是否 请问 你好".split()
)


def tokenize(text: str) -> list[str]:
    """jieba 精确分词 + 停用词过滤 + 单字过滤。"""
    return [w for w in jieba.lcut(text) if w.strip() and w not in STOPWORDS and len(w) > 1]


@dataclass
class Bm25Doc:
    """索引条目：分块内容与溯源元数据。"""
    content: str
    doc_id: int
    chunk_index: int
    doc_name: str
    tokens: list[str] = field(default_factory=list)
    tf: Counter = field(default_factory=Counter)


class BM25Index:
    """标准 BM25Okapi 实现（k1=1.5, b=0.75）。"""

    K1 = 1.5
    B = 0.75

    def __init__(self, docs: list[Bm25Doc]):
        self.docs = docs
        self.doc_len = [len(d.tokens) for d in docs]
        self.avgdl = sum(self.doc_len) / len(docs) if docs else 0.0
        self.df: Counter = Counter()
        for d in docs:
            self.df.update(d.tf.keys())
        self.n = len(docs)

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log((self.n - df + 0.5) / (df + 0.5) + 1)

    def search(self, query: str, k: int = 10) -> list[tuple[Bm25Doc, float]]:
        if not self.docs:
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores: list[tuple[int, float]] = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            dl = self.doc_len[i]
            norm = 1 - self.B + self.B * dl / self.avgdl if self.avgdl else 1.0
            for t in q_tokens:
                f = doc.tf.get(t, 0)
                if f:
                    score += self._idf(t) * f * (self.K1 + 1) / (f + self.K1 * norm)
            if score > 0:
                scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(self.docs[i], s) for i, s in scores[:k]]


def build_index(rows: list[tuple[str, int, int, str]]) -> BM25Index:
    """由 (content, doc_id, chunk_index, doc_name) 行构建索引。"""
    docs = []
    for content, doc_id, chunk_index, doc_name in rows:
        tokens = tokenize(content)
        if tokens:
            docs.append(
                Bm25Doc(
                    content=content,
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                    doc_name=doc_name,
                    tokens=tokens,
                    tf=Counter(tokens),
                )
            )
    return BM25Index(docs)


# ---- 全局索引（启动加载 / 文档变更后重建） ----
_global_index: BM25Index | None = None


def get_global_index() -> BM25Index | None:
    return _global_index


def set_global_index(index: BM25Index | None) -> None:
    global _global_index
    _global_index = index


async def rebuild_global_index(db) -> int:
    """从 chunks 表全量重建全局 BM25 索引，返回条目数。"""
    from sqlalchemy import select

    from ...models import Chunk, Document

    rows = (await db.execute(select(Chunk, Document.filename).join(Document, Chunk.document_id == Document.id))).all()
    payload = [(c.content, c.document_id, c.chunk_index, filename) for c, filename in rows]
    # 全量 jieba 分词是 CPU 密集操作，移到线程池避免阻塞事件循环（删除文档时所有请求会卡顿）
    index = await asyncio.to_thread(build_index, payload)
    set_global_index(index)
    return len(rows)
