"""文本工具：清洗、会话标题截断、摘要等。"""
import hashlib
import re


def clean_text(text: str) -> str:
    """压缩多余空白，保留换行结构。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def make_title(text: str, max_len: int = 30) -> str:
    """由首条用户消息生成会话标题。"""
    one_line = re.sub(r"\s+", " ", text).strip()
    return one_line[:max_len] + ("…" if len(one_line) > max_len else "")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()
