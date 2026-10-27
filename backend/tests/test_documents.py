"""文档入库管线：上传 → 状态流转 → chunks 落库 → 删除清空；权限隔离；hash 去重。"""
import io

import openpyxl
import pytest
from sqlalchemy import func, select

from app.models import Chunk, Document
from app.services.ingestion import process_document
from tests.conftest import auth_headers


def _make_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["参数项", "参数值"])
    for i in range(30):
        ws.append([f"参数{i}", f"值{i}"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_requires_admin(client, normal_user):
    res = await client.post(
        "/api/documents/upload",
        files={"file": ("a.xlsx", _make_xlsx_bytes(), "application/octet-stream")},
        headers=auth_headers(normal_user),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_upload_unsupported_type(client, admin_user):
    res = await client.post(
        "/api/documents/upload",
        files={"file": ("a.exe", b"MZ", "application/octet-stream")},
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_full_ingestion_flow(client, db_session, admin_user):
    """上传 → 手动跑入库任务（测试内直接 await，避免后台任务竞态）→ done + chunks 落库。"""
    res = await client.post(
        "/api/documents/upload",
        files={"file": ("商品参数.xlsx", _make_xlsx_bytes(), "application/octet-stream")},
        headers=auth_headers(admin_user),
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]
    assert res.json()["status"] == "pending"

    await process_document(doc_id)

    doc = await db_session.get(Document, doc_id)
    assert doc.status == "done"
    assert doc.chunk_count > 0

    chunk_count = await db_session.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id == doc_id))
    assert chunk_count == doc.chunk_count


@pytest.mark.asyncio
async def test_duplicate_upload_conflict(client, db_session, admin_user):
    for _ in range(2):
        res = await client.post(
            "/api/documents/upload",
            files={"file": ("商品.xlsx", _make_xlsx_bytes(), "application/octet-stream")},
            headers=auth_headers(admin_user),
        )
    assert res.status_code == 409  # 同内容文件重复上传被拒


@pytest.mark.asyncio
async def test_delete_document_cleans_chunks(client, db_session, admin_user):
    res = await client.post(
        "/api/documents/upload",
        files={"file": ("商品.xlsx", _make_xlsx_bytes(), "application/octet-stream")},
        headers=auth_headers(admin_user),
    )
    doc_id = res.json()["id"]
    await process_document(doc_id)

    del_res = await client.delete(f"/api/documents/{doc_id}", headers=auth_headers(admin_user))
    assert del_res.status_code == 200

    remaining = await db_session.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id == doc_id))
    assert remaining == 0
    doc = await db_session.get(Document, doc_id)
    assert doc is None
