"""中文分块策略。

两阶段：
1. Excel 等结构化文本：先按行组切（每组 N 行、组间重叠 2 行），保持「一行一条商品」的语义完整；
2. 组内/普通文本：RecursiveCharacterTextSplitter 按中文标点递归切分。
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import settings

CHINESE_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

_splitter = RecursiveCharacterTextSplitter(
    separators=CHINESE_SEPARATORS,
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
)


def split_text(text: str, file_type: str = "txt") -> list[str]:
    """入口：按文件类型选择分块方式，返回分块文本列表。"""
    text = text.strip()
    if not text:
        return []
    if file_type == "xlsx":
        return _split_excel_lines(text)
    return [c for c in _splitter.split_text(text) if c.strip()]


def _split_excel_lines(text: str, group_size: int = 12, overlap: int = 2) -> list[str]:
    """Excel 行组切分：每 group_size 行一组，组间重叠 overlap 行。"""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(lines):
        group = lines[start : start + group_size]
        chunk = "\n".join(group)
        # 组内超长再递归细分
        if len(chunk) > settings.chunk_size:
            chunks.extend(c for c in _splitter.split_text(chunk) if c.strip())
        else:
            chunks.append(chunk)
        if start + group_size >= len(lines):
            break
        start += group_size - overlap
    return chunks
