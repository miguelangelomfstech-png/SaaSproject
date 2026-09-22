"""
key_service.py
--------------
Handles secure API key generation, database persistence, and lifecycle
management (create, deactivate, upgrade).
"""

import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import APIKey

# ---------------------------------------------------------------------------
# Plan configuration — single source of truth
# ---------------------------------------------------------------------------
PLAN_LIMITS: dict[str, int] = {
    "starter": 100,
    "pro": 1_000,
    "agency": 10_000,
}

PLAN_FEATURES: dict[str, list[str]] = {
    "starter": ["keyword analysis", "basic SERP"],
    "pro": ["keyword analysis", "SERP", "competitor gap", "AI summaries"],
    "agency": ["keyword analysis", "SERP", "competitor gap", "AI summaries", "bulk (20 keywords)"],
}


def generate_api_key() -> str:
    """Generate a cryptographically secure API key prefixed with 'rl_'."""
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(40))
    return f"rl_{random_part}"


# ---------------------------------------------------------------------------
# CRUD helpers (use own session so they can be called from webhook handlers)
# ---------------------------------------------------------------------------

async def create_api_key(
    email: str,
    plan: str,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> APIKey:
    """
    Create a new API key for the given email/plan.
    If an active key already exists for this email + plan, return it (idempotent).
    """
    plan = plan.lower()
    if plan not in PLAN_LIMITS:
        plan = "starter"

    async with AsyncSessionLocal() as db:
        # Idempotency check: return existing active key for same email+plan
        result = await db.execute(
            select(APIKey).where(
                APIKey.email == email,
                APIKey.plan == plan,
                APIKey.is_active == True,  # noqa: E712
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        key_obj = APIKey(
            key=generate_api_key(),
            email=email,
            plan=plan,
            daily_limit=PLAN_LIMITS[plan],
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )
        db.add(key_obj)
        await db.commit()
        await db.refresh(key_obj)
        return key_obj


async def get_key_by_value(key: str, db: AsyncSession) -> APIKey | None:
    result = await db.execute(
        select(APIKey).where(APIKey.key == key, APIKey.is_active == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def deactivate_key_by_subscription(subscription_id: str) -> bool:
    """Deactivate key when Stripe subscription is cancelled."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(APIKey).where(APIKey.stripe_subscription_id == subscription_id)
        )
        key_obj = result.scalar_one_or_none()
        if key_obj:
            key_obj.is_active = False
            await db.commit()
            return True
        return False


async def upgrade_key_plan(subscription_id: str, new_plan: str) -> bool:
    """Update plan + daily_limit when a subscription is upgraded/downgraded."""
    new_plan = new_plan.lower()
    if new_plan not in PLAN_LIMITS:
        return False

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(APIKey).where(APIKey.stripe_subscription_id == subscription_id)
        )
        key_obj = result.scalar_one_or_none()
        if key_obj:
            key_obj.plan = new_plan
            key_obj.daily_limit = PLAN_LIMITS[new_plan]
            key_obj.is_active = True  # reactivate in case of lapse
            await db.commit()
            return True
        return False
