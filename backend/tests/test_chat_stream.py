"""SSE 问答全链路：事件序列、引用、落库、语义缓存二问命中。"""
import io
import json

import openpyxl
import pytest
from sqlalchemy import select

from app.models import Message
from tests.conftest import FakeLLM, auth_headers


def _make_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["参数项", "参数值"])
    for i in range(20):
        ws.append([f"参数{i}", f"值{i}"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture()
def _fake_rag(monkeypatch):
    """替换 LLM / embedding / rerank，全离线。"""
    import dashscope

    import app.services.chat_service as cs
    from tests.conftest import FakeEmbeddings

    fake_emb = FakeEmbeddings()
    monkeypatch.setattr(cs, "get_embeddings", lambda: fake_emb)
    monkeypatch.setattr(cs, "get_llm", lambda: FakeLLM())

    def fake_rerank(**kwargs):
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
                            {"index": i, "document": {"text": doc}, "relevance_score": 0.9 - i * 0.05}
                            for i, doc in enumerate(kwargs["documents"][:3])
                        ]
                    },
                )(),
            },
        )()

    monkeypatch.setattr(dashscope.TextReRank, "call", fake_rerank)
    yield


async def _parse_sse(response) -> dict:
    """解析 SSE 流为事件序列。"""
    events = {"meta": None, "deltas": [], "references": None, "done": None, "errors": []}
    buffer = ""
    async for chunk in response.aiter_bytes():
        buffer += chunk.decode("utf-8")
        while "\n\n" in buffer:
            frame, buffer = buffer.split("\n\n", 1)
            event = None
            data = None
            for line in frame.split("\n"):
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
            if event == "delta":
                events["deltas"].append(data["content"])
            elif event in events:
                events[event] = data
            elif event == "error":
                events["errors"].append(data)
    return events


@pytest.mark.asyncio
async def test_chat_stream_full_flow(client, db_session, admin_user, _fake_rag):
    # 1. 入库一个文档
    up = await client.post(
        "/api/documents/upload",
        files={"file": ("商品.xlsx", _make_xlsx_bytes(), "application/octet-stream")},
        headers=auth_headers(admin_user),
    )
    from app.services.ingestion import process_document

    await process_document(up.json()["id"])

    # 2. 流式问答
    async with client.stream(
        "POST",
        "/api/chat",
        json={"question": "这个商品的参数是什么？"},
        headers=auth_headers(admin_user),
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = await _parse_sse(resp)

    assert events["meta"]["conversation_id"] > 0
    assert events["meta"]["cache_hit"] is False
    answer = "".join(events["deltas"])
    assert "电池容量" in answer  # FakeLLM 固定输出
    assert "[1]" in answer
    assert events["references"] is not None and len(events["references"]) >= 1
    assert events["references"][0]["doc_name"]
    assert events["done"]["message_id"] > 0
    assert events["done"]["total_ms"] >= 0
    assert not events["errors"]

    # 3. 落库校验：user + assistant 两条消息，引用快照一致
    msgs = (
        (await db_session.execute(select(Message).order_by(Message.id))).scalars().all()
    )
    assert len(msgs) == 2
    assistant = msgs[-1]
    assert assistant.role == "assistant"
    assert assistant.references_json == events["references"]


@pytest.mark.asyncio
async def test_chat_second_question_hits_cache(client, db_session, admin_user, _fake_rag):
    up = await client.post(
        "/api/documents/upload",
        files={"file": ("商品.xlsx", _make_xlsx_bytes(), "application/octet-stream")},
        headers=auth_headers(admin_user),
    )
    from app.services.ingestion import process_document

    await process_document(up.json()["id"])

    question = "这个商品的电池容量是多少？"
    async with client.stream("POST", "/api/chat", json={"question": question}, headers=auth_headers(admin_user)) as resp:
        first = await _parse_sse(resp)
    assert first["done"]["cache_hit"] is False

    # 同问题二问：语义缓存命中，total_ms 应显著更小
    async with client.stream("POST", "/api/chat", json={"question": question}, headers=auth_headers(admin_user)) as resp:
        second = await _parse_sse(resp)
    assert second["done"]["cache_hit"] is True
    assert second["done"]["total_ms"] < first["done"]["total_ms"]
    assert "".join(second["deltas"]) == "".join(first["deltas"])  # 回放内容一致
