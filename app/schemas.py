from datetime import datetime

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# API Key schemas
# ---------------------------------------------------------------------------
class KeyInfo(BaseModel):
    id: str
    key: str
    email: str
    plan: str
    daily_limit: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateKeyRequest(BaseModel):
    email: str
    plan: str = "starter"


# ---------------------------------------------------------------------------
# SEO response schemas
# ---------------------------------------------------------------------------
class SERPResult(BaseModel):
    position: int
    title: str
    url: str
    snippet: str


class SEOAnalysisResponse(BaseModel):
    keyword: str
    search_volume_estimate: str
    difficulty_score: int  # 0–100
    top_results: list[SERPResult]
    ai_summary: str
    related_keywords: list[str]


class CompetitorGapResponse(BaseModel):
    your_domain: str
    competitor_domain: str
    gap_pages: list[dict]
    opportunity_score: int  # 0–100
    ai_recommendations: str


class BulkAnalysisRequest(BaseModel):
    keywords: list[str]


class BulkAnalysisResponse(BaseModel):
    count: int
    results: list[SEOAnalysisResponse]


# ---------------------------------------------------------------------------
# Generic schemas
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    version: str


class UsageResponse(BaseModel):
    plan: str
    daily_limit: int
    used_today: int
    remaining_today: int


class MessageResponse(BaseModel):
    status: str
    message: str = ""
