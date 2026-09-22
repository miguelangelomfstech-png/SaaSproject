"""Tests for the Stripe webhook handler."""

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _stripe_signature(payload: bytes, secret: str) -> str:
    """Replicate Stripe's Stripe-Signature header generation."""
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode()}"
    signature = hmac.new(
        secret.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


WEBHOOK_SECRET = "whsec_test_secret_for_ci"


@pytest.fixture(autouse=True)
def patch_stripe_secret(monkeypatch):
    """Override the webhook secret so tests don't need a real Stripe key."""
    import app.config as cfg

    monkeypatch.setattr(cfg.settings, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(cfg.settings, "STRIPE_SECRET_KEY", "sk_test_dummy")
    import app.routers.webhook as wh
    import stripe
    stripe.api_key = "sk_test_dummy"


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def test_webhook_rejects_bad_signature():
    payload = json.dumps({"type": "checkout.session.completed"}).encode()
    resp = client.post(
        "/webhook/stripe",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=0,v1=badhash",
        },
    )
    assert resp.status_code == 400


def test_webhook_rejects_missing_signature():
    payload = json.dumps({"type": "checkout.session.completed"}).encode()
    resp = client.post(
        "/webhook/stripe",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    # Missing header → FastAPI returns 422
    assert resp.status_code == 422
