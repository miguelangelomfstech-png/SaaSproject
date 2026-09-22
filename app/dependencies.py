"""
dependencies.py
---------------
FastAPI dependencies shared across routers:
  - get_api_key   : authenticates X-API-Key header and enforces daily limits
  - log_usage     : writes a UsageLog row
  - verify_admin  : checks X-Admin-Key header
  - limiter       : slowapi Limiter instance (IP-based global rate limit)
"""

import logging
from datetime import date

from fastapi import Depends, Header, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import APIKey, UsageLog
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global IP-level rate limiter (fallback defence, per-minute)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])


# ---------------------------------------------------------------------------
# API Key authentication + daily quota enforcement
# ---------------------------------------------------------------------------

async def get_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """
    1. Validates the key exists and is active.
    2. Checks today's usage against the plan's daily limit.
    Raises 401 for bad keys, 429 when quota is exceeded.
    """
    result = await db.execute(
        select(APIKey).where(
            APIKey.key == x_api_key,
            APIKey.is_active == True,  # noqa: E712
        )
    )
    key_obj = result.scalar_one_or_none()

    if not key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key. "
                   "Purchase a plan at https://ranklens.dev to get a key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # --- Daily usage check ---------------------------------------------------
    today = date.today()
    usage_result = await db.execute(
        select(func.count(UsageLog.id)).where(
            UsageLog.api_key_id == key_obj.id,
            func.date(UsageLog.timestamp) == today,
        )
    )
    used_today: int = usage_result.scalar_one() or 0

    if used_today >= key_obj.daily_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Daily limit of {key_obj.daily_limit:,} requests reached "
                f"(plan: {key_obj.plan}). Resets at midnight UTC or upgrade at "
                "https://ranklens.dev."
            ),
            headers={"X-RateLimit-Limit": str(key_obj.daily_limit)},
        )

    return key_obj


async def log_usage(api_key: APIKey, endpoint: str, db: AsyncSession) -> None:
    """Append a UsageLog row. Call this once per successful API request."""
    log = UsageLog(api_key_id=api_key.id, endpoint=endpoint)
    db.add(log)
    await db.commit()


# ---------------------------------------------------------------------------
# Admin authentication
# ---------------------------------------------------------------------------

def verify_admin(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
) -> bool:
    if x_admin_key != settings.ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key.",
        )
    return True
