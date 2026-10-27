"""TXT/Markdown 解析：charset-normalizer 探测编码（utf-8/gbk 均可）。"""
from charset_normalizer import from_bytes


def parse_text(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    best = from_bytes(raw).best()
    return str(best) if best else raw.decode("utf-8", errors="ignore")
