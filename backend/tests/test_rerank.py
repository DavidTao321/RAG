"""重排序器：排序、阈值过滤、异常降级。"""
from langchain_core.documents import Document

from app.services.rag.reranker import DashScopeReranker


def _docs():
    return [
        Document(page_content=f"片段{i}", metadata={"document_id": i, "chunk_index": 0, "doc_name": f"d{i}"})
        for i in range(4)
    ]


def test_rerank_order_and_threshold(monkeypatch):
    import dashscope

    def fake_call(**kwargs):
        return type(
            "Resp",
            (),
            {
                "status_code": 200,
                "output": type(
                    "Out",
                    (),
                    {
                        "results": [
                            {"index": 2, "document": {"text": "片段2"}, "relevance_score": 0.95},
                            {"index": 0, "document": {"text": "片段0"}, "relevance_score": 0.60},
                            {"index": 3, "document": {"text": "片段3"}, "relevance_score": 0.05},  # 低于阈值被丢弃
                            {"index": 1, "document": {"text": "片段1"}, "relevance_score": 0.30},
                        ]
                    },
                )(),
            },
        )()

    monkeypatch.setattr(dashscope.TextReRank, "call", fake_call)
    reranker = DashScopeReranker(top_n=3, threshold=0.1)
    out = reranker.compress_documents(_docs(), "query")
    assert [d.metadata["document_id"] for d in out] == [2, 0, 1]  # 按分数降序，0.05 被过滤


def test_rerank_fallback_on_error(monkeypatch):
    import dashscope

    def boom(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(dashscope.TextReRank, "call", boom)
    reranker = DashScopeReranker(top_n=2, threshold=0.1)
    out = reranker.compress_documents(_docs(), "query")
    assert len(out) == 2  # 降级为原顺序前 2 条，不抛异常
