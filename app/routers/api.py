"""
api.py
------
Core public API endpoints. All routes require a valid X-API-Key header.

Endpoint matrix by plan:
  GET /api/v1/analyze         — all plans
  GET /api/v1/competitor-gap  — pro, agency
  POST /api/v1/bulk           — agency only
  GET /api/v1/usage           — all plans (no usage cost)
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_api_key, log_usage
from app.models import APIKey, UsageLog
from app.schemas import (
    BulkAnalysisRequest,
    BulkAnalysisResponse,
    CompetitorGapResponse,
    SEOAnalysisResponse,
    UsageResponse,
)
from app.services import seo_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["SEO API"])


# ---------------------------------------------------------------------------
# Keyword analysis  (all plans)
# ---------------------------------------------------------------------------

@router.get(
    "/analyze",
    response_model=SEOAnalysisResponse,
    summary="Keyword Analysis",
    description=(
        "Analyse a keyword: SERP results, difficulty score (0–100), "
        "volume estimate, AI-generated strategy, and related keywords."
    ),
)
async def analyze_keyword(
    keyword: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="The keyword or phrase to analyse.",
        examples=["content marketing strategy"],
    ),
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await log_usage(api_key, "/api/v1/analyze", db)
    logger.info("analyze keyword='%s'  plan=%s", keyword, api_key.plan)
    return await seo_service.analyze_keyword(keyword)


# ---------------------------------------------------------------------------
# Competitor gap  (pro + agency)
# ---------------------------------------------------------------------------

@router.get(
    "/competitor-gap",
    response_model=CompetitorGapResponse,
    summary="Competitor Gap Analysis",
    description=(
        "Identify pages your competitor ranks for that you don't. "
        "Returns gap page list, opportunity score, and AI recommendations. "
        "**Requires Pro or Agency plan.**"
    ),
)
async def competitor_gap(
    your_domain: str = Query(
        ...,
        description="Your domain (no protocol), e.g. myblog.com",
        examples=["myblog.com"],
    ),
    competitor_domain: str = Query(
        ...,
        description="Competitor's domain, e.g. competitor.com",
        examples=["competitor.com"],
    ),
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if api_key.plan not in ("pro", "agency"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Competitor gap analysis requires Pro or Agency plan. "
                   "Upgrade at https://ranklens.dev.",
        )

    await log_usage(api_key, "/api/v1/competitor-gap", db)
    logger.info(
        "competitor-gap your=%s comp=%s plan=%s",
        your_domain,
        competitor_domain,
        api_key.plan,
    )
    return await seo_service.competitor_gap_analysis(your_domain, competitor_domain)


# ---------------------------------------------------------------------------
# Bulk analysis  (agency only)
# ---------------------------------------------------------------------------

@router.post(
    "/bulk",
    response_model=BulkAnalysisResponse,
    summary="Bulk Keyword Analysis",
    description=(
        "Analyse up to 20 keywords in parallel in a single request. "
        "Each keyword counts as one request against your daily limit. "
        "**Requires Agency plan.**"
    ),
)
async def bulk_analyze(
    body: BulkAnalysisRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if api_key.plan != "agency":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bulk analysis requires the Agency plan. "
                   "Upgrade at https://ranklens.dev.",
        )

    if len(body.keywords) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 20 keywords per bulk request.",
        )

    if not body.keywords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one keyword is required.",
        )

    # Log one usage per keyword
    for _ in body.keywords:
        await log_usage(api_key, "/api/v1/bulk", db)

    logger.info(
        "bulk analyze count=%d  plan=%s", len(body.keywords), api_key.plan
    )

    results = await asyncio.gather(
        *[seo_service.analyze_keyword(kw) for kw in body.keywords]
    )

    return {"count": len(results), "results": list(results)}


# ---------------------------------------------------------------------------
# Usage stats  (all plans — does NOT count against daily limit)
# ---------------------------------------------------------------------------

@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="Check Usage",
    description="Return today's usage and remaining quota for your API key.",
)
async def get_usage(
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import date

    today = date.today()
    result = await db.execute(
        select(func.count(UsageLog.id)).where(
            UsageLog.api_key_id == api_key.id,
            func.date(UsageLog.timestamp) == today,
        )
    )
    used_today: int = result.scalar_one() or 0

    return {
        "plan": api_key.plan,
        "daily_limit": api_key.daily_limit,
        "used_today": used_today,
        "remaining_today": max(0, api_key.daily_limit - used_today),
    }
