# ===========================================================================
# Dockerfile — RankLens API
# Single-stage build — simple, reliable, works on all free hosting platforms
# ===========================================================================

FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install all dependencies system-wide (no --user flag = no PATH issues)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Data directory for SQLite
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Use "python -m uvicorn" — always works regardless of PATH configuration
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

