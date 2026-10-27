"""引用机制：build_references 编号数组生成 + 多编号/越界解析边界。

extract_cited_indices/renumber_citations 主路径已在 test_retrieval.py 覆盖，此处补充 build_references
与多编号组的解析边界。
"""
from langchain_core.documents import Document

from app.services.rag.citations import build_references, extract_cited_indices, renumber_citations


def test_build_references_numbering():
    """重排后的 Document 列表转为从 1 编号的引用数组，元数据字段透传。"""
    docs = [
        Document(page_content="片段A", metadata={"document_id": 3, "doc_name": "a.xlsx", "score": 0.9}),
        Document(page_content="片段B", metadata={"document_id": 7, "doc_name": "b.docx", "score": 0.7}),
    ]
    refs = build_references(docs)
    assert refs[0] == {"index": 1, "doc_id": 3, "doc_name": "a.xlsx", "content": "片段A", "score": 0.9}
    assert refs[1] == {"index": 2, "doc_id": 7, "doc_name": "b.docx", "content": "片段B", "score": 0.7}


def test_build_references_missing_meta_defaults():
    """元数据缺失时 doc_id/score 为 None、doc_name 为空串，不抛异常。"""
    refs = build_references([Document(page_content="内容", metadata={})])
    assert refs[0]["doc_id"] is None and refs[0]["doc_name"] == ""
    assert refs[0]["score"] is None and refs[0]["index"] == 1


def test_extract_cited_indices_multi_and_out_of_range():
    """[1,3] 多编号组解析为升序去重；越界编号与无引用返回空。"""
    assert extract_cited_indices("见[1,3]与[2]和[3]", 3) == [1, 2, 3]
    assert extract_cited_indices("越界[9]", 3) == []
    assert extract_cited_indices("无引用", 3) == []


def test_renumber_citations_multi_group():
    """多编号组整体重映射：[2,4] → [1,2]。"""
    assert renumber_citations("见[2,4]", [2, 4]) == "见[1,2]"
