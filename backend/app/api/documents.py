"""知识库文档管理接口（仅管理员）。"""
from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import not_found
from ..database import get_db
from ..models import Chunk, Document, User
from ..schemas.common import Page
from ..schemas.document import ChunkOut, DocumentOut
from ..services.document_service import create_document, delete_document, reindex_document
from .deps import get_current_admin

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """上传文档：立即返回 pending，后台异步解析入库，前端轮询状态。"""
    doc = await create_document(db, admin, file)
    return doc


@router.get("", response_model=Page[DocumentOut])
async def list_documents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document)
    if status:
        stmt = stmt.where(Document.status == status)
    total = (await db.scalar(select(func.count()).select_from(stmt.subquery()))) or 0
    rows = (
        await db.execute(stmt.order_by(Document.id.desc()).offset((page - 1) * size).limit(size))
    ).scalars().all()
    return Page(items=rows, total=total, page=page, size=size)


@router.delete("/{document_id}")
async def remove_document(
    document_id: int,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    await delete_document(db, document_id)
    return {"detail": "文档已删除（含向量与分块）"}


@router.post("/{document_id}/reindex", response_model=DocumentOut)
async def reindex(
    document_id: int,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """重建索引：清理旧向量与分块后重新解析入库。"""
    doc = await reindex_document(db, document_id)
    return doc


@router.get("/{document_id}/chunks", response_model=Page[ChunkOut])
async def preview_chunks(
    document_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, document_id)
    if doc is None:
        raise not_found("文档不存在")
    total = (
        await db.scalar(select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id))
    ) or 0
    rows = (
        await db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()
    return Page(items=rows, total=total, page=page, size=size)
