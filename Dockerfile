# One container: FastAPI serves the API and the built single-page app.

FROM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
# The API types file is generated from the checked-in OpenAPI document.
COPY docs/openapi.json /docs/openapi.json
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /srv/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /srv/frontend/dist

# Run as a non-root user; the SQLite demo database lives in a writable data directory.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /srv/state \
    && chown -R appuser:appuser /srv
USER appuser
ENV SQLITE_PATH=/srv/state/halqa.db

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
