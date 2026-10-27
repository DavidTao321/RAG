"""检索纯函数测试：RRF 融合公式、BM25 精确词命中。"""
from langchain_core.documents import Document

from app.services.rag.bm25 import BM25Index, build_index
from app.services.rag.hybrid_retriever import HybridRetriever


def _doc(doc_id: int, chunk_index: int, text: str) -> Document:
    return Document(
        page_content=text,
        metadata={"document_id": doc_id, "chunk_index": chunk_index, "doc_name": f"d{doc_id}"},
    )


def test_rrf_fusion_order():
    """RRF：两路都命中的文档排最前；单路命中按 1/(k+rank) 计分。"""
    vec = [
        (_doc(1, 0, "A"), 0.9),  # 向量第 1
        (_doc(2, 0, "B"), 0.8),  # 向量第 2
    ]
    bm = [
        (_doc(2, 0, "B"), 5.0),  # BM25 第 1（两路都命中）
        (_doc(3, 0, "C"), 4.0),  # BM25 第 2
    ]
    fused = HybridRetriever._rrf_fuse([vec, bm], rrf_k=60, top_n=3)
    ids = [(d.metadata["document_id"], d.metadata["chunk_index"]) for d in fused]
    assert ids[0] == (2, 0)  # 双路命中排第一
    assert (1, 0) in ids and (3, 0) in ids
    # 分数：doc2 = 1/61 + 1/62，doc1 = 1/61
    assert fused[0].metadata["score"] > fused[1].metadata["score"]


def test_bm25_exact_keyword_hit():
    """精确型号词（如 RTX4060）必须被 BM25 命中——混合检索对电商参数问题的核心收益。"""
    index = build_index(
        [
            ("星耀 X90 搭载天玑 9400+ 处理器，电池 5800mAh", 1, 0, "手机1.xlsx"),
            ("华光笔记本配备 RTX4060 显卡，16GB 内存", 2, 0, "笔记本.xlsx"),
            ("云洁洗衣机 10kg 容量，一级能效", 3, 0, "洗衣机.docx"),
        ]
    )
    results = index.search("RTX4060 显卡配置", k=1)
    assert results, "精确型号词应命中"
    assert results[0][0].doc_id == 2


def test_renumber_citations():
    from app.services.rag.citations import extract_cited_indices, renumber_citations

    answer = "电池容量 5800mAh[2]，首发价 4299 元[4]。详见[2,4]。"
    cited = extract_cited_indices(answer, 5)
    assert cited == [2, 4]
    renamed = renumber_citations(answer, cited)
    assert renamed == "电池容量 5800mAh[1]，首发价 4299 元[2]。详见[1,2]。"
    # Markdown 链接不受影响
    md = "参考[文档](http://a.b)与[1]"
    assert renumber_citations(md, [1]) == "参考[文档](http://a.b)与[1]"
    # 越界编号不重写
    assert renumber_citations("文本[9]与[2]", [2]) == "文本[9]与[1]"
