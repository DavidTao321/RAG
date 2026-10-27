"""引用机制：检索片段编号 → 从回答中提取实际引用编号 → 生成 references 数组。"""
import re

CITATION_RE = re.compile(r"\[(\d+(?:[,\s]\d+)*)\]")


def build_references(documents) -> list[dict]:
    """将重排后的 Document 列表转为编号引用数组。

    返回: [{"index":1,"doc_id":3,"doc_name":"x.xlsx","content":"片段原文","score":0.87}, ...]
    """
    refs = []
    for i, doc in enumerate(documents, start=1):
        meta = doc.metadata
        refs.append(
            {
                "index": i,
                "doc_id": meta.get("document_id"),
                "doc_name": meta.get("doc_name", ""),
                "content": doc.page_content,
                "score": meta.get("score"),
            }
        )
    return refs


def extract_cited_indices(answer: str, max_index: int) -> list[int]:
    """提取回答中出现的 [n]、[1,3] 编号，过滤越界，返回升序列表。"""
    indices: set[int] = set()
    for m in CITATION_RE.finditer(answer):
        for part in m.group(1).replace(",", " ").split():
            n = int(part)
            if 1 <= n <= max_index:
                indices.add(n)
    return sorted(indices)


def renumber_citations(answer: str, cited_indices: list[int]) -> str:
    """把回答中的引用编号按升序重新映射为 [1][2]…，消除编号空洞。

    例：cited_indices=[2,4]，"[2] 与 [4]" → "[1] 与 [2]"。
    只重写纯数字方括号引用，不动 Markdown 链接等其它方括号内容。
    """
    mapping = {old: new for new, old in enumerate(cited_indices, start=1)}

    def repl(m: re.Match) -> str:
        new_nums = []
        for part in m.group(1).replace(",", " ").split():
            n = mapping.get(int(part))
            if n is not None:
                new_nums.append(str(n))
        return f"[{','.join(new_nums)}]" if new_nums else m.group(0)

    return CITATION_RE.sub(repl, answer)
