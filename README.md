# 🔑 RankLens API

> **AI-Powered SEO Intelligence — fully automated Micro-SaaS**  
> Keyword difficulty scores · SERP analysis · Competitor gap detection · AI strategy  
> Built on 100% free infrastructure. Zero upfront cost.

---

## Table of Contents

1. [Product Overview](#product-overview)
2. [Architecture](#architecture)
3. [Local Development](#local-development)
4. [Environment Variables](#environment-variables)
5. [Stripe Setup (Monetization)](#stripe-setup)
6. [Deploy to Render (Free)](#deploy-to-render)
7. [GitHub Actions CI/CD](#github-actions-cicd)
8. [API Reference](#api-reference)
9. [Upgrade to Postgres (Supabase)](#upgrade-to-postgres)
10. [Monetization Checklist](#monetization-checklist)

---

## Product Overview

RankLens API is a **fully automated B2B API** that lets developers, agencies, and indie hackers access SEO intelligence without paying $99–$449/month for Ahrefs or SEMrush.

| Plan | Price | Req/day | Endpoints |
|------|-------|---------|-----------|
| Starter | $9/mo | 100 | `/analyze` |
| Pro | $29/mo | 1,000 | + `/competitor-gap` |
| Agency | $79/mo | 10,000 | + `/bulk` |

**Revenue at scale:** 100 Starter + 30 Pro + 10 Agency = **$2,570 MRR** (fully automated, zero staff)

---

## Architecture

```
Customer → Stripe Payment Link → checkout.session.completed
                                         ↓
                              POST /webhook/stripe (verified)
                                         ↓
                              Create API Key in SQLite DB
                                         ↓
                              Send key via Resend email (auto)
                                         ↓
Customer uses key → GET /api/v1/analyze?keyword=...
                    Header: X-API-Key: rl_xxxxx
                                         ↓
                    Auth check + daily rate limit check
                                         ↓
                    DuckDuckGo SERP scrape + Gemini AI analysis
                                         ↓
                    JSON response
```

---

## Local Development

### Prerequisites
- Python 3.11+
- pip

### Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/YOUR_USERNAME/SaaSproject.git
cd SaaSproject

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your keys (at minimum set ADMIN_SECRET)

# 5. Run the server
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** — the interactive API explorer is live.

### Using Docker (recommended for parity with production)

```bash
# Build and start
docker compose up --build

# Stop
docker compose down
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in these values:

| Variable | Required | Description |
|----------|----------|-------------|
| `ADMIN_SECRET` | ✅ | Random secret for admin endpoints |
| `STRIPE_SECRET_KEY` | ✅ | From Stripe Dashboard → API Keys |
| `STRIPE_WEBHOOK_SECRET` | ✅ | From Stripe → Webhooks (after creation) |
| `GEMINI_API_KEY` | Optional | AI summaries (free at aistudio.google.com) |
| `RESEND_API_KEY` | Optional | Email delivery (free at resend.com) |
| `APP_BASE_URL` | ✅ | Your public URL (e.g. https://ranklens.onrender.com) |
| `DATABASE_URL` | ✅ | SQLite path or Postgres URL |

Generate a secure `ADMIN_SECRET`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Stripe Setup

### Step 1 — Create Products & Price IDs

1. Go to [dashboard.stripe.com/products](https://dashboard.stripe.com/products)
2. Create three products:

| Name | Price | Billing |
|------|-------|---------|
| RankLens Starter | $9.00 | Monthly recurring |
| RankLens Pro | $29.00 | Monthly recurring |
| RankLens Agency | $79.00 | Monthly recurring |

3. Copy each **Price ID** (looks like `price_1abc...`)

### Step 2 — Create Payment Links

For each product, go to **Payment Links → Create link** and:
- Under **Metadata**, add: `plan` = `starter` (or `pro` / `agency`)
- Enable **Collect customer's email**

This metadata is how the webhook knows which plan the customer bought.

### Step 3 — Create the Webhook

1. Go to **Developers → Webhooks → Add endpoint**
2. **Endpoint URL:** `https://your-app.onrender.com/webhook/stripe`
3. **Events to listen to:**
   - `checkout.session.completed`
   - `customer.subscription.deleted`
   - `customer.subscription.updated`
   - `invoice.payment_failed`
4. Click **Add endpoint** → copy the **Signing secret** (`whsec_...`)
5. Add it to your `.env` as `STRIPE_WEBHOOK_SECRET`

### Step 4 — Add Price Map to .env

```bash
STRIPE_PRICE_MAP=price_STARTER_ID=starter,price_PRO_ID=pro,price_AGENCY_ID=agency
```

### Test the webhook locally with Stripe CLI

```bash
# Install: https://stripe.com/docs/stripe-cli
stripe login
stripe listen --forward-to localhost:8000/webhook/stripe

# In another terminal — simulate a purchase:
stripe trigger checkout.session.completed
```

---

## Deploy to Render (Free)

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "feat: initial RankLens API"
git remote add origin https://github.com/YOUR_USERNAME/SaaSproject.git
git push -u origin main
```

### Step 2 — Create Render Web Service

1. Sign up at [render.com](https://render.com) (free)
2. **New → Web Service → Connect your GitHub repo**
3. Settings:
   - **Runtime:** Docker
   - **Branch:** main
   - **Instance type:** Free
4. Add all environment variables from `.env` in the **Environment** tab
5. Click **Create Web Service**

Render automatically builds and deploys from your `Dockerfile`.

### Step 3 — Get Deploy Hook for CI/CD

In Render: **Settings → Deploy Hook → Copy URL**  
Add it to GitHub: **Settings → Secrets → Actions → `RENDER_DEPLOY_HOOK_URL`**

Now every `git push main` → tests pass → auto-deploys. ✅

---

## GitHub Actions CI/CD

The pipeline at [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml):

1. **On every push/PR:** runs `pytest` with in-memory SQLite (no secrets needed)
2. **On push to `main`:** triggers Render deploy hook

Required GitHub Secret: `RENDER_DEPLOY_HOOK_URL`

---

## API Reference

Base URL: `https://your-app.onrender.com`  
Interactive docs: `https://your-app.onrender.com/docs`

### Authentication

All `/api/v1/*` endpoints require:
```
X-API-Key: rl_your_api_key_here
```

### Endpoints

#### `GET /api/v1/analyze` — Keyword Analysis (all plans)

```bash
curl "https://your-app.onrender.com/api/v1/analyze?keyword=content+marketing" \
  -H "X-API-Key: rl_your_key"
```

Response:
```json
{
  "keyword": "content marketing",
  "search_volume_estimate": "10K–100K/mo (estimated)",
  "difficulty_score": 80,
  "top_results": [...],
  "ai_summary": "Content marketing is highly competitive...",
  "related_keywords": ["content marketing strategy", "content marketing tools", ...]
}
```

#### `GET /api/v1/competitor-gap` — Competitor Gap (Pro+)

```bash
curl "https://your-app.onrender.com/api/v1/competitor-gap?your_domain=myblog.com&competitor_domain=competitor.com" \
  -H "X-API-Key: rl_your_key"
```

#### `POST /api/v1/bulk` — Bulk Analysis (Agency only)

```bash
curl -X POST "https://your-app.onrender.com/api/v1/bulk" \
  -H "X-API-Key: rl_your_key" \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["seo tools", "keyword research", "backlink checker"]}'
```

#### `GET /api/v1/usage` — Check Quota (free, all plans)

```bash
curl "https://your-app.onrender.com/api/v1/usage" \
  -H "X-API-Key: rl_your_key"
```

### Admin Endpoints (X-Admin-Key required)

```bash
# Create a key manually
curl -X POST "https://your-app.onrender.com/admin/keys" \
  -H "X-Admin-Key: your_admin_secret" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "plan": "pro"}'

# List all keys
curl "https://your-app.onrender.com/admin/keys" \
  -H "X-Admin-Key: your_admin_secret"

# Platform stats
curl "https://your-app.onrender.com/admin/stats" \
  -H "X-Admin-Key: your_admin_secret"
```

---

## Upgrade to Postgres (Supabase)

When you outgrow SQLite:

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **Settings → Database → Connection string → URI**
3. Install asyncpg: add `asyncpg==0.29.0` to `requirements.txt`
4. Update `.env`:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:[password]@db.[ref].supabase.co:5432/postgres
```
5. Remove the SQLite-specific `connect_args` from `database.py` (already handled by the `if "sqlite" in ...` check)
6. Redeploy — tables are auto-created on startup. ✅

---

## Monetization Checklist

- [ ] Create Stripe account and products
- [ ] Create 3 Payment Links (Starter/Pro/Agency) with `plan` metadata
- [ ] Configure webhook endpoint in Stripe
- [ ] Set all env vars in Render
- [ ] Push to GitHub → auto-deploy fires
- [ ] Test end-to-end with `stripe trigger checkout.session.completed`
- [ ] Get your Gemini API key (free, no credit card): [aistudio.google.com](https://aistudio.google.com)
- [ ] Get your Resend API key (free): [resend.com](https://resend.com)
- [ ] Share your Payment Links on Twitter/X, Reddit r/entrepreneur, Indie Hackers
- [ ] Submit to SaaS directories: Product Hunt, SaaS Hub, There's An AI For That

**Launch day estimate: ~4 hours from zero to live** 🚀

---

## Free Infrastructure Summary

| Service | Cost | What it handles |
|---------|------|----------------|
| Render.com | $0 | Hosting (750 hrs/month free) |
| SQLite on Render | $0 | Database (persisted volume) |
| Stripe | 2.9%+$0.30/txn | Payments (no monthly fee) |
| Gemini Flash | $0 | AI analysis (15 RPM free) |
| Resend | $0 | 3,000 emails/month |
| GitHub Actions | $0 | CI/CD (2,000 min/month) |

**Total fixed cost: $0/month until you scale.** 💸
