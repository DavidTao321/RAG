"""管理员数据看板接口（P1）：概览 KPI / 问答趋势 / 性能统计（论文截图来源）。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Chunk, Document, Feedback, QueryStats, User
from ..schemas.stats import PerformanceStats, QaTrendPoint, StatsOverview
from .deps import get_current_admin

router = APIRouter(prefix="/api/admin/stats", tags=["admin-stats"])


@router.get("/overview", response_model=StatsOverview)
async def overview(admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    user_count = (await db.scalar(select(func.count()).select_from(User))) or 0
    document_count = (await db.scalar(select(func.count()).select_from(Document))) or 0
    chunk_count = (await db.scalar(select(func.count()).select_from(Chunk))) or 0
    qa_count = (await db.scalar(select(func.count()).select_from(QueryStats))) or 0
    tokens = (
        await db.execute(
            select(
                func.coalesce(func.sum(QueryStats.prompt_tokens), 0),
                func.coalesce(func.sum(QueryStats.completion_tokens), 0),
            )
        )
    ).one()
    feedback = (
        await db.execute(
            select(
                func.coalesce(func.sum(func.if_(Feedback.rating == 1, 1, 0)), 0),
                func.coalesce(func.sum(func.if_(Feedback.rating == -1, 1, 0)), 0),
            )
        )
    ).one()
    return StatsOverview(
        user_count=user_count,
        document_count=document_count,
        chunk_count=chunk_count,
        qa_count=qa_count,
        total_prompt_tokens=int(tokens[0]),
        total_completion_tokens=int(tokens[1]),
        feedback_like=int(feedback[0]),
        feedback_dislike=int(feedback[1]),
    )


@router.get("/qa-trend", response_model=list[QaTrendPoint])
async def qa_trend(
    days: int = Query(30, ge=1, le=365),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now() - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                func.date(QueryStats.created_at),
                func.count(),
                func.coalesce(func.sum(func.if_(QueryStats.cache_hit, 1, 0)), 0),
            )
            .where(QueryStats.created_at >= since)
            .group_by(func.date(QueryStats.created_at))
            .order_by(func.date(QueryStats.created_at))
        )
    ).all()
    return [
        QaTrendPoint(date=str(day), count=int(cnt), cache_hit_count=int(hit))
        for day, cnt, hit in rows
    ]


@router.get("/performance", response_model=PerformanceStats)
async def performance(admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(
                func.coalesce(func.avg(QueryStats.retrieval_ms), 0),
                func.coalesce(func.avg(QueryStats.rerank_ms), 0),
                func.coalesce(func.avg(QueryStats.llm_ms), 0),
                func.coalesce(func.avg(QueryStats.total_ms), 0),
                func.coalesce(func.sum(func.if_(QueryStats.cache_hit, 1, 0)), 0),
                func.count(),
            )
        )
    ).one()
    total_qa = int(rows[5])
    hit_count = int(rows[4])
    return PerformanceStats(
        avg_retrieval_ms=round(float(rows[0]), 1),
        avg_rerank_ms=round(float(rows[1]), 1),
        avg_llm_ms=round(float(rows[2]), 1),
        avg_total_ms=round(float(rows[3]), 1),
        cache_hit_rate=round(hit_count / total_qa, 4) if total_qa else 0.0,
        total_qa=total_qa,
    )
