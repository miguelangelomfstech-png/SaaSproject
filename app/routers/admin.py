"""
admin.py
--------
Internal admin endpoints, protected by X-Admin-Key header.
Used for manual key management, support, and debugging.
NEVER expose these routes publicly — put them behind a VPN or IP allowlist
in production.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import verify_admin
from app.models import APIKey, UsageLog
from app.schemas import CreateKeyRequest, KeyInfo, MessageResponse
from app.services.key_service import PLAN_LIMITS, create_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

@router.post(
    "/keys",
    response_model=KeyInfo,
    summary="Create API Key",
    description="Manually issue an API key for a customer (e.g., after a Gumroad sale).",
)
async def admin_create_key(
    body: CreateKeyRequest,
    _: bool = Depends(verify_admin),
) -> APIKey:
    if body.plan not in PLAN_LIMITS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan '{body.plan}'. Valid options: {list(PLAN_LIMITS.keys())}",
        )
    key_obj = await create_api_key(email=body.email, plan=body.plan)
    logger.info("Admin created key for %s  plan=%s", body.email, body.plan)
    return key_obj


@router.get(
    "/keys",
    response_model=list[KeyInfo],
    summary="List All API Keys",
    description="Return all issued API keys ordered by creation date (newest first).",
)
async def admin_list_keys(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin),
) -> list[APIKey]:
    result = await db.execute(
        select(APIKey).order_by(APIKey.created_at.desc()).limit(500)
    )
    return list(result.scalars().all())


@router.delete(
    "/keys/{key_id}",
    response_model=MessageResponse,
    summary="Revoke API Key",
    description="Deactivate an API key by its UUID. The key remains in the DB for audit purposes.",
)
async def admin_revoke_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin),
) -> dict:
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key_obj = result.scalar_one_or_none()
    if not key_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No key found with id={key_id}",
        )
    key_obj.is_active = False
    await db.commit()
    logger.info("Admin revoked key id=%s email=%s", key_id, key_obj.email)
    return {"status": "ok", "message": f"Key {key_id} has been deactivated."}


# ---------------------------------------------------------------------------
# Stats & monitoring
# ---------------------------------------------------------------------------

@router.get(
    "/stats",
    summary="Platform Statistics",
    description="High-level stats: total keys, active keys, today's requests.",
)
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin),
) -> dict:
    today = date.today()

    total_keys = (await db.execute(select(func.count(APIKey.id)))).scalar_one()
    active_keys = (
        await db.execute(
            select(func.count(APIKey.id)).where(APIKey.is_active == True)  # noqa: E712
        )
    ).scalar_one()
    requests_today = (
        await db.execute(
            select(func.count(UsageLog.id)).where(
                func.date(UsageLog.timestamp) == today
            )
        )
    ).scalar_one()

    plan_breakdown: dict[str, int] = {}
    plan_results = await db.execute(
        select(APIKey.plan, func.count(APIKey.id))
        .where(APIKey.is_active == True)  # noqa: E712
        .group_by(APIKey.plan)
    )
    for plan, count in plan_results:
        plan_breakdown[plan] = count

    return {
        "total_keys": total_keys,
        "active_keys": active_keys,
        "requests_today": requests_today,
        "active_by_plan": plan_breakdown,
    }
