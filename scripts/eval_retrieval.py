"""检索质量对比实验（论文素材）：四种检索配置的命中率与耗时对比。

配置对比：
  1. 仅向量检索（Chroma top-10）
  2. 仅关键词检索（BM25 top-10）
  3. 混合检索（向量 + BM25，RRF 融合 top-8）
  4. 混合检索 + Rerank 重排（top-5）

指标：Recall@k（正确答案所在文档是否进入 top-k）、平均检索耗时。

用法：后端与 MySQL 已启动时，在 backend 目录运行：
  venv\\Scripts\\python ..\\scripts\\eval_retrieval.py
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import async_session  # noqa: E402

# dashscope 原生 SDK 从环境变量读 key（与 main.py lifespan 中同样的注入逻辑）
if settings.dashscope_api_key:
    os.environ["DASHSCOPE_API_KEY"] = settings.dashscope_api_key
    import dashscope

    dashscope.api_key = settings.dashscope_api_key
from app.models import Chunk, Document  # noqa: E402
from app.services.rag.bm25 import build_index, get_global_index  # noqa: E402
from app.services.rag.hybrid_retriever import HybridRetriever  # noqa: E402
from app.services.rag.reranker import DashScopeReranker  # noqa: E402
from app.services.rag.vector_store import get_vector_store  # noqa: E402

# 评测集：(问题, 应命中的文档名关键字)
QA_SET = [
    ("星耀X90 Pro的电池容量是多少？", "星耀 X90 Pro"),
    ("X90标准版支持多少瓦快充？", "X90 标准版"),
    ("华光折叠屏手机保修几年？", "P90 折叠屏"),
    ("睿米15 Ultra的屏幕是什么规格？", "睿米 15 Ultra"),
    ("华光青春版手机多少钱？", "青春版"),
    ("云洁洗衣机保修多久？", "滚筒洗衣机"),
    ("空调的制冷量是多少？", "变频空调"),
    ("扫地机器人的吸力有多大？", "扫地机器人"),
    ("净水器的滤芯能用多久？", "净水器"),
    ("降噪耳机的续航时间？", "降噪耳机"),
    ("平板支持手写笔吗？", "TabPad"),
    ("智能手表的防水等级？", "Watch S4"),
    ("坚果礼盒保质期多久？", "每日坚果"),
    ("记忆棉枕头可以退换吗？", "记忆棉"),
    ("精华液适合敏感肌吗？", "精华液"),
    ("羽毛球拍是什么材质？", "羽毛球拍"),
    ("平台支持价保吗？", "售后服务总则"),
    ("T恤是什么面料？", "T恤"),
    ("移动电源可以带上飞机吗？", "移动电源"),
    ("智能音箱能控制家居吗？", "Echo Mini"),
]


def doc_contains(chunks_hit: list, keyword: str) -> bool:
    for doc in chunks_hit:
        name = doc.metadata.get("doc_name", "")
        if keyword in name:
            return True
    return False


async def main() -> None:
    # 从数据库重建 BM25（保证与线上一致）
    async with async_session() as db:
        rows = (await db.execute(select(Chunk, Document.filename).join(Document, Chunk.document_id == Document.id))).all()
    index = build_index([(c.content, c.document_id, c.chunk_index, fn) for c, fn in rows])

    retriever = HybridRetriever(bm25_index=index, top_k=10, rrf_k=60, fusion_top_n=8)
    reranker = DashScopeReranker(top_n=5, threshold=0.0)  # 实验阈值 0，观察原始分数
    store = get_vector_store()

    configs = {
        "仅向量检索": lambda q: _vector_only(store, q),
        "仅BM25关键词": lambda q: _bm25_only(index, q),
        "混合检索(RRF)": lambda q: retriever.ainvoke(q),
        "混合检索+Rerank": lambda q: _hybrid_rerank(retriever, reranker, q),
    }

    print(f"{'配置':<16} {'Recall@3':>8} {'Recall@5':>8} {'Recall@8':>8} {'平均耗时':>10}")
    print("-" * 56)
    for name, fn in configs.items():
        hits = {3: 0, 5: 0, 8: 0}
        total_ms = 0.0
        for question, keyword in QA_SET:
            t0 = time.perf_counter()
            docs = await fn(question)
            total_ms += (time.perf_counter() - t0) * 1000
            for k in (3, 5, 8):
                if doc_contains(docs[:k], keyword):
                    hits[k] += 1
        n = len(QA_SET)
        print(
            f"{name:<16} {hits[3]/n:>7.1%} {hits[5]/n:>7.1%} {hits[8]/n:>7.1%} {total_ms/n:>9.1f}ms"
        )
    from app.database import engine

    await engine.dispose()


async def _vector_only(store, q):
    results = store.similarity_search_with_score(q, k=10)
    return [d for d, _ in results]


async def _bm25_only(index, q):
    from langchain_core.documents import Document

    return [
        Document(
            page_content=bd.content,
            metadata={"document_id": bd.doc_id, "chunk_index": bd.chunk_index, "doc_name": bd.doc_name},
        )
        for bd, _ in index.search(q, k=10)
    ]


async def _hybrid_rerank(retriever, reranker, q):
    docs = await retriever.ainvoke(q)
    return await asyncio.to_thread(reranker.compress_documents, docs, q)


if __name__ == "__main__":
    asyncio.run(main())
