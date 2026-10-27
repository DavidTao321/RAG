"""用户反馈接口（P1）：对单条 assistant 回答点赞/点踩，重复反馈覆盖。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import bad_request, forbidden, not_found
from ..database import get_db
from ..models import Feedback, Message, User
from .deps import get_current_user

router = APIRouter(prefix="/api/messages", tags=["feedback"])


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(default=None, max_length=500)


@router.put("/{message_id}/feedback")
async def submit_feedback(
    message_id: int,
    body: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.rating == 0:
        raise bad_request("rating 只能为 1（赞）或 -1（踩）")
    message = await db.get(Message, message_id)
    if message is None:
        raise not_found("消息不存在")
    if message.user_id != user.id:
        raise forbidden("无权操作该消息")
    if message.role != "assistant":
        raise bad_request("只能对回答消息反馈")

    feedback = await db.scalar(select(Feedback).where(Feedback.message_id == message_id))
    if feedback is None:
        feedback = Feedback(message_id=message_id, user_id=user.id, rating=body.rating, comment=body.comment)
        db.add(feedback)
    else:
        feedback.rating = body.rating
        feedback.comment = body.comment
    await db.commit()
    return {"detail": "反馈已记录"}
