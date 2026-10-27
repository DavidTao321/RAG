"""SSE 事件帧格式化（规范：帧间空行分隔，data 为 JSON）。"""
import json


def sse_frame(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_error_frame(detail: str) -> str:
    return sse_frame("error", {"detail": detail})
