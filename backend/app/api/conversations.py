"""会话与历史消息接口：多用户多会话管理、历史持久化（分页）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import forbidden, not_found
from ..database import get_db
from ..models import Conversation, Message, User
from ..schemas.common import Page
from ..schemas.conversation import (
    ConversationCreate,
    ConversationOut,
    ConversationRename,
    MessageOut,
    ReferenceOut,
)
from .deps import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=Page[ConversationOut])
async def list_conversations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total = (
        await db.scalar(select(func.count()).select_from(Conversation).where(Conversation.user_id == user.id))
    ) or 0
    rows = (
        await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()
    return Page(items=rows, total=total, page=page, size=size)


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = Conversation(user_id=user.id, title=(body.title if body and body.title else "新会话"))
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: int,
    body: ConversationRename,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise not_found("会话不存在")
    if conv.user_id != user.id:
        raise forbidden("无权访问该会话")
    conv.title = body.title
    await db.commit()
    await db.refresh(conv)
    return conv


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise not_found("会话不存在")
    if conv.user_id != user.id:
        raise forbidden("无权访问该会话")
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await db.delete(conv)
    await db.commit()
    return {"detail": "会话已删除"}


@router.get("/{conversation_id}/messages", response_model=Page[MessageOut])
async def list_messages(
    conversation_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(Conversation, conversation_id)
    if conv is None:
        raise not_found("会话不存在")
    if conv.user_id != user.id:
        raise forbidden("无权访问该会话")

    total = (
        await db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id))
    ) or 0
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    items = []
    for m in rows:
        items.append(
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                references=[ReferenceOut(**r) for r in (m.references_json or [])],
                model=m.model,
                cache_hit=m.cache_hit,
                created_at=m.created_at,
            )
        )
    return Page(items=items, total=total, page=page, size=size)
