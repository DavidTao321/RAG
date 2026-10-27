"""文档管理服务：上传 / 删除 / 重建索引 编排。"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.exceptions import bad_request, conflict, not_found
from ..models import Chunk, Document, User
from ..models.document import ALLOWED_FILE_TYPES
from ..utils.text import sha256_hex
from .ingestion import process_document, remove_document_data, schedule_ingestion
from .kb_version import bump_kb_version
from .rag import bm25

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


async def create_document(db: AsyncSession, user: User, file: UploadFile) -> Document:
    """上传入口：校验 → 落盘 → 建行(pending) → 触发后台入库任务。"""
    filename = file.filename or "未命名文件"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_FILE_TYPES:
        raise bad_request(f"不支持的文件类型 .{ext}，仅支持 {', '.join(ALLOWED_FILE_TYPES)}")

    # 分块读取：Starlette 对 >1MB 的上传先落临时文件，一次 read() 会把任意大小文件
    # 整体装入内存——分块读并即时超限拒绝，避免超大文件打爆进程内存
    chunks: list[bytes] = []
    total = 0
    while True:
        part = await file.read(1024 * 1024)  # 每次 1MB
        if not part:
            break
        total += len(part)
        if total > MAX_FILE_SIZE:
            raise bad_request("文件超过 20MB 限制")
        chunks.append(part)
    content = b"".join(chunks)
    if not content:
        raise bad_request("文件内容为空")

    file_hash = sha256_hex(content)
    # 同内容且非 failed 状态的文档视为重复（含待处理/处理中，防止并发重复上传）
    existing = await db.scalar(
        select(Document).where(
            Document.file_hash == file_hash,
            Document.status.in_(("pending", "processing", "done")),
        )
    )
    if existing is not None:
        raise conflict(f"该文件内容与已入库文档「{existing.filename}」重复")

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / stored_name).write_bytes(content)

    doc = Document(
        filename=filename,
        stored_name=stored_name,
        file_type=ext,
        file_size=len(content),
        file_hash=file_hash,
        status="pending",
        created_by=user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    schedule_ingestion(doc.id)
    return doc


async def delete_document(db: AsyncSession, doc_id: int) -> None:
    """删除：向量 + chunks + 文档行 + 磁盘文件，随后版本号+1 并重建 BM25。"""
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise not_found("文档不存在")

    await remove_document_data(doc_id)
    await db.delete(doc)
    await db.commit()
    # 磁盘文件删除失败不影响主流程
    try:
        Path(settings.upload_dir / doc.stored_name).unlink(missing_ok=True)
    except OSError:
        pass
    await bump_kb_version(db)
    await db.commit()
    await bm25.rebuild_global_index(db)


async def reindex_document(db: AsyncSession, doc_id: int) -> Document:
    """重建索引：清理旧向量与 chunks，重新走入库管线（Chroma 损坏可从 MySQL 恢复）。"""
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise not_found("文档不存在")
    if doc.status == "processing":
        raise bad_request("文档正在处理中，请稍候")

    await remove_document_data(doc_id)
    doc.status = "pending"
    doc.error_msg = None
    await db.commit()
    await db.refresh(doc)

    schedule_ingestion(doc.id)
    return doc


async def total_chunks(db: AsyncSession) -> int:
    return (await db.scalar(select(func.count()).select_from(Chunk))) or 0
