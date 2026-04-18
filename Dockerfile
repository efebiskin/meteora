# Meteora weather API — production container
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first for better layer caching
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

# Data volume for the SQLite key store
VOLUME ["/data"]
ENV METEORA_DB=/data/meteora.db

EXPOSE 8787

# Healthcheck — hits /v1/health every 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import httpx; r = httpx.get('http://localhost:8787/v1/health', timeout=3); exit(0 if r.status_code == 200 else 1)"

CMD ["uvicorn", "meteora.main:app", "--host", "0.0.0.0", "--port", "8787"]
