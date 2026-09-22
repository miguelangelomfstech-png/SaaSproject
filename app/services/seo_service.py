"""
seo_service.py
--------------
Core RankLens intelligence engine.

Data sources (all free, no API key required by default):
  - DuckDuckGo HTML search for SERP results
  - DuckDuckGo autocomplete for related keywords
  - Gemini 1.5 Flash for AI analysis (15 RPM free tier)

Difficulty scoring: heuristic based on authority of ranking domains.
Volume estimation: heuristic based on keyword length/modifiers.
"""

import logging
import re

import httpx

from app.config import settings
from app.schemas import SERPResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

# Domains known to hold top rankings → high difficulty signal
_AUTHORITY_DOMAINS = {
    "wikipedia.org", "amazon.com", "youtube.com", "reddit.com",
    "forbes.com", "nytimes.com", "quora.com", "medium.com",
    "github.com", "stackoverflow.com", "linkedin.com", "shopify.com",
    "hubspot.com", "semrush.com", "ahrefs.com", "moz.com",
    "healthline.com", "webmd.com", "nhs.uk",
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def analyze_keyword(keyword: str) -> dict:
    """Full keyword analysis: SERP + difficulty + volume + AI summary."""
    top_results = await _fetch_serp(keyword)
    difficulty = _score_difficulty(top_results)
    volume = _estimate_volume(keyword)
    related = await _fetch_related_keywords(keyword)
    ai_summary = await _gemini_summary(keyword, top_results, difficulty)

    return {
        "keyword": keyword,
        "search_volume_estimate": volume,
        "difficulty_score": difficulty,
        "top_results": top_results[:5],
        "ai_summary": ai_summary,
        "related_keywords": related,
    }


async def competitor_gap_analysis(your_domain: str, competitor_domain: str) -> dict:
    """Find pages a competitor ranks for that you don't."""
    your_pages = await _fetch_serp(f"site:{your_domain}")
    comp_pages = await _fetch_serp(f"site:{competitor_domain}")

    your_urls = {r["url"] for r in your_pages}
    comp_urls = {r["url"] for r in comp_pages}

    gap_urls = list(comp_urls - your_urls)
    gap_pages = [{"url": u, "opportunity": "high"} for u in gap_urls[:15]]
    opportunity_score = min(len(gap_urls) * 8, 100)

    ai_recs = await _gemini_gap_recommendations(
        your_domain, competitor_domain, len(gap_urls)
    )

    return {
        "your_domain": your_domain,
        "competitor_domain": competitor_domain,
        "gap_pages": gap_pages,
        "opportunity_score": opportunity_score,
        "ai_recommendations": ai_recs,
    }


# ---------------------------------------------------------------------------
# SERP scraping
# ---------------------------------------------------------------------------

async def _fetch_serp(query: str) -> list[dict]:
    """Scrape DuckDuckGo HTML results page (no API key required)."""
    results: list[dict] = []
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True, timeout=12
        ) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            resp.raise_for_status()
            html = resp.text

            # Extract result blocks
            titles = re.findall(
                r'class="result__title"[^>]*>.*?<a[^>]*>(.*?)</a>',
                html,
                re.DOTALL,
            )
            urls = re.findall(
                r'class="result__url"[^>]*>(.*?)</(?:span|a)>',
                html,
                re.DOTALL,
            )
            snippets = re.findall(
                r'class="result__snippet"[^>]*>(.*?)</(?:a|span)>',
                html,
                re.DOTALL,
            )

            for i, (title, url, snippet) in enumerate(
                zip(titles, urls, snippets)
            ):
                results.append(
                    {
                        "position": i + 1,
                        "title": _strip_tags(title),
                        "url": url.strip(),
                        "snippet": _strip_tags(snippet),
                    }
                )
                if i >= 9:
                    break
    except Exception as exc:
        logger.warning("SERP scrape failed for '%s': %s", query, exc)
    return results


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


# ---------------------------------------------------------------------------
# Difficulty scoring
# ---------------------------------------------------------------------------

def _score_difficulty(results: list[dict]) -> int:
    """
    Returns 0–100.
    Each top-10 result from a high-authority domain adds 10 points.
    """
    if not results:
        return 40  # unknown — assume moderate
    score = 0
    for result in results[:10]:
        url = result.get("url", "")
        for domain in _AUTHORITY_DOMAINS:
            if domain in url:
                score += 10
                break
    return min(score, 100)


# ---------------------------------------------------------------------------
# Volume estimation (heuristic — free alternative to Google Ads API)
# ---------------------------------------------------------------------------

def _estimate_volume(keyword: str) -> str:
    words = keyword.split()
    kw_lower = keyword.lower()

    # Brand / navigational queries tend to be high volume
    high_vol_signals = ["amazon", "youtube", "google", "facebook", "netflix"]
    if any(s in kw_lower for s in high_vol_signals):
        return "1M+/mo (estimated)"

    if len(words) == 1:
        return "10K–100K/mo (estimated)"
    elif len(words) == 2:
        return "1K–10K/mo (estimated)"
    elif len(words) <= 4:
        return "500–5K/mo (estimated)"
    else:
        return "100–1K/mo long-tail (estimated)"


# ---------------------------------------------------------------------------
# Related keywords via DuckDuckGo autocomplete
# ---------------------------------------------------------------------------

async def _fetch_related_keywords(keyword: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            resp = await client.get(
                "https://duckduckgo.com/ac/",
                params={"q": keyword, "type": "list"},
            )
            data = resp.json()
            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                return [str(k) for k in data[1][:8]]
    except Exception as exc:
        logger.warning("Autocomplete failed for '%s': %s", keyword, exc)
    return []


# ---------------------------------------------------------------------------
# Gemini Flash AI analysis
# ---------------------------------------------------------------------------

def _get_gemini_model():
    if not settings.GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=settings.GEMINI_API_KEY)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception as exc:
        logger.warning("Gemini init failed: %s", exc)
        return None


async def _gemini_summary(
    keyword: str, results: list[dict], difficulty: int
) -> str:
    model = _get_gemini_model()
    if not model:
        return (
            f"AI summary unavailable (GEMINI_API_KEY not set). "
            f"Difficulty score: {difficulty}/100."
        )

    top_titles = [r.get("title", "") for r in results[:5]]
    prompt = (
        f'You are an expert SEO strategist. Analyze the keyword "{keyword}".\n'
        f"Difficulty score: {difficulty}/100\n"
        f"Top 5 ranking page titles: {top_titles}\n\n"
        "Provide a concise 3-sentence SEO insight:\n"
        "1. Content opportunity assessment\n"
        "2. Why this difficulty score makes sense\n"
        "3. One specific, actionable ranking recommendation"
    )

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        logger.warning("Gemini summary failed: %s", exc)
        return f"AI analysis temporarily unavailable. Difficulty: {difficulty}/100."


async def _gemini_gap_recommendations(
    your_domain: str, competitor_domain: str, gap_count: int
) -> str:
    model = _get_gemini_model()
    if not model:
        return (
            f"Found {gap_count} content gap pages. "
            "Set GEMINI_API_KEY for AI-powered recommendations."
        )

    prompt = (
        f"SEO competitor gap analysis: {your_domain} vs {competitor_domain}.\n"
        f"Found {gap_count} pages the competitor ranks for that {your_domain} does not.\n\n"
        "Give 3 specific, actionable content strategies to close these gaps. "
        "Format as a numbered list. Be concise and practical."
    )

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        logger.warning("Gemini gap recommendations failed: %s", exc)
        return f"AI recommendations temporarily unavailable. Gap count: {gap_count}."
