"""
webhook.py
----------
Handles inbound Stripe webhook events. All events are verified with the
Stripe-Signature header before any action is taken.

Supported events:
  - checkout.session.completed      → issue new API key + send email
  - customer.subscription.deleted   → deactivate API key
  - customer.subscription.updated   → upgrade/downgrade plan + limit
  - invoice.payment_failed          → (logged, no action — Stripe retries)
"""

import logging

import stripe
from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings
from app.services.email_service import send_api_key_email
from app.services.key_service import (
    create_api_key,
    deactivate_key_by_subscription,
    upgrade_key_plan,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhooks"])

# Initialise Stripe with the secret key
stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Main webhook endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/stripe",
    summary="Stripe webhook receiver",
    description=(
        "Receives and verifies all Stripe events. "
        "Configure this URL in the Stripe dashboard under Developers → Webhooks."
    ),
    status_code=200,
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
) -> dict:
    payload = await request.body()

    # --- Signature verification (CRITICAL — never skip this) ---------------
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.SignatureVerificationError as exc:
        logger.warning("Stripe signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
    except Exception as exc:
        logger.error("Webhook parse error: %s", exc)
        raise HTTPException(status_code=400, detail="Malformed webhook payload.")

    event_type: str = event["type"]
    logger.info("Stripe event received: %s  id=%s", event_type, event["id"])

    # --- Route events -------------------------------------------------------
    match event_type:
        case "checkout.session.completed":
            await _on_checkout_completed(event["data"]["object"])

        case "customer.subscription.deleted":
            await _on_subscription_deleted(event["data"]["object"])

        case "customer.subscription.updated":
            await _on_subscription_updated(event["data"]["object"])

        case "invoice.payment_failed":
            logger.warning(
                "Payment failed for customer %s",
                event["data"]["object"].get("customer"),
            )

        case _:
            logger.debug("Unhandled Stripe event: %s", event_type)

    return {"status": "ok", "event": event_type}


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

async def _on_checkout_completed(session: dict) -> None:
    """Issue an API key and email it to the customer."""
    # Customer email comes from different places depending on checkout config
    email: str | None = (
        session.get("customer_email")
        or (session.get("customer_details") or {}).get("email")
    )
    if not email:
        logger.error("checkout.session.completed missing email — session_id=%s", session.get("id"))
        return

    # Plan is stored in metadata set on the Payment Link / Checkout Session
    plan: str = (session.get("metadata") or {}).get("plan", "starter")
    customer_id: str | None = session.get("customer")
    subscription_id: str | None = session.get("subscription")

    logger.info(
        "New checkout: email=%s plan=%s subscription=%s", email, plan, subscription_id
    )

    key_obj = await create_api_key(
        email=email,
        plan=plan,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
    )

    # Fire-and-forget email (errors are logged, not re-raised)
    send_api_key_email(to_email=email, api_key=key_obj.key, plan=plan)


async def _on_subscription_deleted(subscription: dict) -> None:
    """Deactivate the API key when a subscription is cancelled."""
    sub_id: str = subscription.get("id", "")
    deactivated = await deactivate_key_by_subscription(sub_id)
    logger.info(
        "Subscription deleted %s — key deactivated: %s", sub_id, deactivated
    )


async def _on_subscription_updated(subscription: dict) -> None:
    """Handle plan upgrades and downgrades."""
    sub_id: str = subscription.get("id", "")
    status: str = subscription.get("status", "")

    if status != "active":
        # Could be 'past_due', 'unpaid', etc. — don't upgrade until payment clears
        return

    # Resolve price → plan using the configured mapping
    items = (subscription.get("items") or {}).get("data", [])
    if not items:
        return

    price_id: str = (items[0].get("price") or {}).get("id", "")
    new_plan = settings.price_to_plan.get(price_id, "starter")

    upgraded = await upgrade_key_plan(sub_id, new_plan)
    logger.info(
        "Subscription updated %s → plan=%s  upgraded=%s", sub_id, new_plan, upgraded
    )
