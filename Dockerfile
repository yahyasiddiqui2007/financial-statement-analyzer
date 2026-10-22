# Builds one container that serves both the API and the website.
#   docker build -t fsa . && docker run -p 8000:8000 -e FSA_SEC_USER_AGENT="Name email" fsa

# ---- Stage 1: build the React frontend into static files -------------------
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the Python server --------------------------------------------
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Dependencies first, so this slow step is reused until uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --no-dev

COPY --from=frontend /app/frontend/dist ./frontend/dist
ENV FSA_FRONTEND_DIST=/app/frontend/dist \
    PORT=8000

# Don't run as root.
RUN useradd --create-home app
USER app

EXPOSE 8000
# Hosting platforms set $PORT. --proxy-headers makes the real visitor IP visible
# behind the platform's proxy, which the per-visitor AI limit relies on.
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn fsa.api.app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
