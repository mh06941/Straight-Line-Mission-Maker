FROM node:24-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -f /run/secrets/build_ca ]; then NODE_EXTRA_CA_CERTS=/run/secrets/build_ca npm ci --no-audit --no-fund; else npm ci --no-audit --no-fund; fi
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -f /run/secrets/build_ca ]; then UV_SYSTEM_CERTS=true SSL_CERT_FILE=/run/secrets/build_ca uv sync --frozen --no-dev; else uv sync --frozen --no-dev; fi
COPY --chown=10001:10001 backend/app/ app/
COPY --from=frontend --chown=10001:10001 /build/frontend/dist /app/frontend/dist
RUN groupadd --gid 10001 straightline && useradd --uid 10001 --gid 10001 --no-create-home straightline && mkdir -p data && chown 10001:10001 data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD ["/app/backend/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
CMD ["/app/backend/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
