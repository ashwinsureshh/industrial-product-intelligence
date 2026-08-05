# Single-image build: the submission requires one live link, so the UI and the
# API ship as one service. The frontend is built in a Node stage and the built
# assets are copied into the Python runtime, which serves them alongside /api.

# ---------------------------------------------------------------- frontend
FROM node:22-slim AS frontend

WORKDIR /build
# Copy manifests first so dependency install caches across source edits.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ----------------------------------------------------------------- runtime
FROM python:3.12-slim

# pdfplumber needs no system packages, but curl earns its place as the
# container healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces runs the container as uid 1000 with a writable /home.
RUN useradd -m -u 1000 app
USER app
ENV PATH="/home/app/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /home/app

COPY --chown=app:app backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --user -r backend/requirements.txt

COPY --chown=app:app backend/ ./backend/
COPY --from=frontend --chown=app:app /build/dist ./frontend/dist

# A public deployment must never be able to spend the owner's credits, and the
# reviewer has no key of their own. Live mode stays reachable so the bundled
# pre-computed results are served, but no server key exists to fall back on.
ENV PI_ALLOW_SERVER_KEY=0 \
    PI_CACHE_DIR=/home/app/.cache/pi \
    PORT=7860

RUN mkdir -p /home/app/.cache/pi

WORKDIR /home/app/backend
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:${PORT}/api/health || exit 1

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
