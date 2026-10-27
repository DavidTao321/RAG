"""工具函数测试：文本清洗、会话标题截断、哈希已知向量、SSE 帧格式。"""
from app.utils.sse import sse_error_frame, sse_frame
from app.utils.text import clean_text, make_title, md5_hex, sha256_hex


def test_clean_text_normalizes_whitespace():
    """换行统一为 \\n、连续空白压缩为单空格、连续空行压缩为单个空行。"""
    assert clean_text("a\r\nb\rc\n\n\n\n d  e") == "a\nb\nc\n\n d e"


def test_clean_text_strips_edges():
    assert clean_text("  内容  \n") == "内容"


def test_make_title_truncates_with_ellipsis():
    """超长标题按 max_len 截断并加省略号。"""
    assert make_title("这是" * 20) == "这是" * 15 + "…"


def test_make_title_short_unchanged():
    assert make_title("短标题", 10) == "短标题"


def test_make_title_collapses_whitespace():
    assert make_title("  多   空格  标题  ") == "多 空格 标题"


def test_hash_known_vectors():
    """md5/sha256 与标准已知向量一致。"""
    assert md5_hex("abc") == "900150983cd24fb0d6963f7d28e17f72"
    assert sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sse_frame_format():
    """帧格式：event 行 + data 行（JSON，中文不转义）+ 空行结尾。"""
    assert sse_frame("meta", {"id": 1, "text": "中文"}) == 'event: meta\ndata: {"id": 1, "text": "中文"}\n\n'


def test_sse_error_frame():
    assert sse_error_frame("出错了") == 'event: error\ndata: {"detail": "出错了"}\n\n'
