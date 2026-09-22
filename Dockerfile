# ===========================================================================
# Dockerfile — RankLens API
# Multi-stage build: keeps the final image small and dependency-free of build tools
# ===========================================================================

# ---- Stage 1: dependency builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools for any native extensions
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt


# ---- Stage 2: runtime image ----
FROM python:3.11-slim AS runtime

# Create a non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application source
COPY app/ ./app/

# Data directory for SQLite
RUN mkdir -p /app/data && chown appuser:appgroup /app/data

USER appuser

ENV PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Uvicorn with 2 workers (scale via Render/Docker Compose as needed)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
