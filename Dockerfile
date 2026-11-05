FROM node:22-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim-bookworm AS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends g++ libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN pip wheel --wheel-dir /wheels -r /tmp/requirements.lock

FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/* && useradd -m -u 1000 app
COPY --from=dependencies /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
WORKDIR /app
COPY backend /app/backend
COPY docs/DATA.md LICENSE /app/notices/
COPY --from=frontend /web/dist /app/frontend/dist
COPY --chown=app:app release/bundle /app/artifacts/fiqa-ltr
COPY --chown=app:app release/reports /app/reports
ENV PYTHONPATH=/app/backend RANKFORGE_BUNDLE=/app/artifacts/fiqa-ltr OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 PORT=7860
USER app
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://localhost:'+os.getenv('PORT','7860')+'/health/ready')"
CMD ["sh", "-c", "exec uvicorn rankforge.api:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
