"""Tests for the SEO API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import APIKey
from app.services.key_service import generate_api_key


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_analyze_no_key_returns_422(client):
    """Missing X-API-Key header → 422 (validation error)."""
    resp = client.get("/api/v1/analyze", params={"keyword": "test"})
    assert resp.status_code == 422


def test_analyze_bad_key_returns_401(client):
    """Invalid API key → 401."""
    resp = client.get(
        "/api/v1/analyze",
        params={"keyword": "test"},
        headers={"X-API-Key": "rl_totally_invalid_key"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Admin endpoint — bad key
# ---------------------------------------------------------------------------

def test_admin_bad_key_returns_403(client):
    resp = client.get(
        "/admin/keys",
        headers={"X-Admin-Key": "wrong-secret"},
    )
    assert resp.status_code == 403


def test_admin_stats_bad_key_returns_403(client):
    resp = client.get(
        "/admin/stats",
        headers={"X-Admin-Key": "wrong-secret"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Plan-gating
# ---------------------------------------------------------------------------

def test_competitor_gap_starter_returns_403(client):
    """Starter plan cannot access /competitor-gap."""
    from app.main import app
    from app.dependencies import get_api_key

    async def fake_starter_key():
        return APIKey(
            id="test-id",
            key="rl_testkey",
            email="test@example.com",
            plan="starter",
            daily_limit=100,
            is_active=True,
        )

    app.dependency_overrides[get_api_key] = fake_starter_key
    try:
        resp = client.get(
            "/api/v1/competitor-gap",
            params={"your_domain": "a.com", "competitor_domain": "b.com"},
            headers={"X-API-Key": "rl_testkey"},
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_api_key, None)


def test_bulk_non_agency_returns_403(client):
    """Pro plan cannot access /bulk."""
    from app.main import app
    from app.dependencies import get_api_key

    async def fake_pro_key():
        return APIKey(
            id="test-id",
            key="rl_testkey",
            email="test@example.com",
            plan="pro",
            daily_limit=1000,
            is_active=True,
        )

    app.dependency_overrides[get_api_key] = fake_pro_key
    try:
        resp = client.post(
            "/api/v1/bulk",
            json={"keywords": ["seo", "content"]},
            headers={"X-API-Key": "rl_testkey"},
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_api_key, None)


# ---------------------------------------------------------------------------
# Key generation utility
# ---------------------------------------------------------------------------

def test_generate_api_key_format():
    key = generate_api_key()
    assert key.startswith("rl_")
    assert len(key) == 43  # "rl_" + 40 chars


def test_generate_api_key_uniqueness():
    keys = {generate_api_key() for _ in range(1000)}
    assert len(keys) == 1000  # no collisions in 1,000 generations
