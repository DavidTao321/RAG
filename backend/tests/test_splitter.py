"""分块器测试：中文递归切分与 Excel 行组切分（重叠行、超长组细分）。"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

import app.services.splitter as splitter
from app.services.splitter import CHINESE_SEPARATORS, _split_excel_lines, split_text


def test_split_text_empty_or_blank():
    """空文本/纯空白返回空列表。"""
    assert split_text("") == []
    assert split_text("   \n  ") == []


def test_split_text_plain_multi_chunk():
    """普通文本按中文标点递归切分为多个非空分块。"""
    text = "。".join(f"第{i}条参数说明内容" for i in range(200))
    chunks = split_text(text, "txt")
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)
    assert all(len(c) <= 620 for c in chunks)  # chunk_size=600 + 分隔符保留余量


def test_split_text_xlsx_routes_to_grouping():
    """xlsx 走行组切分：行数不足一组时输出单个分块。"""
    lines = [f"商品{i}：参数" for i in range(5)]
    chunks = split_text("\n".join(lines), "xlsx")
    assert chunks == ["\n".join(lines)]


def test_split_excel_lines_groups_with_overlap():
    """行组切分：每组 group_size 行，组间重叠 overlap 行，末尾余量行成组。"""
    lines = [f"商品{i}：参数" for i in range(8)]
    chunks = _split_excel_lines("\n".join(lines), group_size=3, overlap=1)
    assert chunks == [
        "\n".join(lines[0:3]),
        "\n".join(lines[2:5]),
        "\n".join(lines[4:7]),
        "\n".join(lines[6:8]),
    ]


def test_split_excel_lines_skips_blank_lines():
    """空白行被过滤后按单组输出。"""
    assert _split_excel_lines("A\n\n   \nB", group_size=3, overlap=1) == ["A\nB"]


def test_split_excel_lines_oversized_group_recursive(monkeypatch):
    """组内文本超过 chunk_size 时递归细分（用小块尺寸验证）。"""
    small = RecursiveCharacterTextSplitter(
        separators=CHINESE_SEPARATORS, chunk_size=20, chunk_overlap=5
    )
    monkeypatch.setattr(splitter, "_splitter", small)
    monkeypatch.setattr(splitter.settings, "chunk_size", 20)
    long_lines = ["参数" + "x" * 30 for _ in range(3)]  # 每组 67 字符 > 20
    chunks = _split_excel_lines("\n".join(long_lines), group_size=2, overlap=1)
    assert len(chunks) >= 4  # 2 个超长组被细分
    assert all(len(c) <= 24 for c in chunks)  # 20 + 分隔符余量
