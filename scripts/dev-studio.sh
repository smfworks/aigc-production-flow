#!/usr/bin/env bash
# Start Phase 3 studio processes. From repo root:
#   ./scripts/dev-studio.sh api|web|app|worker|all
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ROLE="${1:-api}"

export STUDIO_DATABASE_URL="${STUDIO_DATABASE_URL:-sqlite:///${ROOT}/data/studio.db}"
export STUDIO_MEDIA_ROOT="${STUDIO_MEDIA_ROOT:-${ROOT}/data/media}"
export STUDIO_API_TOKEN="${STUDIO_API_TOKEN:-local-dev-token}"
export STUDIO_PACK_BUILDER_URL="${STUDIO_PACK_BUILDER_URL:-http://localhost:5173}"
export STUDIO_JOB_WORKER="${STUDIO_JOB_WORKER:-thread}"
export STUDIO_STILL_ADAPTER="${STUDIO_STILL_ADAPTER:-stub}"
export STUDIO_CLIP_ADAPTER="${STUDIO_CLIP_ADAPTER:-stub}"

mkdir -p "$ROOT/data/media"

ensure_studio_venv() {
  if [[ ! -x "$ROOT/studio/.venv/bin/python" ]]; then
    python3 -m venv "$ROOT/studio/.venv"
    "$ROOT/studio/.venv/bin/pip" install -e "$ROOT/studio[dev]"
  fi
}

start_api() {
  ensure_studio_venv
  echo "Studio API  http://localhost:8000/docs  (token: $STUDIO_API_TOKEN)"
  echo "Job worker  in-process (${STUDIO_JOB_WORKER}); adapter still=${STUDIO_STILL_ADAPTER} clip=${STUDIO_CLIP_ADAPTER}"
  cd "$ROOT/studio"
  exec "$ROOT/studio/.venv/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000
}

start_worker() {
  ensure_studio_venv
  echo "Studio job poller (standalone). Set STUDIO_JOB_WORKER=off on the API so only this process dequeues."
  echo "Celery is not running — this is the in-process worker extracted to its own loop."
  cd "$ROOT/studio"
  exec "$ROOT/studio/.venv/bin/python" -m app.jobs.worker
}

start_web() {
  if [[ ! -d "$ROOT/studio-web/node_modules" ]]; then
    (cd "$ROOT/studio-web" && npm install)
  fi
  echo "Studio shell  http://localhost:5174"
  cd "$ROOT/studio-web"
  exec npm run dev
}

start_app() {
  if [[ ! -d "$ROOT/app/node_modules" ]]; then
    (cd "$ROOT/app" && npm install)
  fi
  echo "Pack builder  http://localhost:5173"
  cd "$ROOT/app"
  exec npm run dev
}

start_all() {
  ensure_studio_venv
  if [[ ! -d "$ROOT/studio-web/node_modules" ]]; then
    (cd "$ROOT/studio-web" && npm install)
  fi
  if [[ ! -d "$ROOT/app/node_modules" ]]; then
    (cd "$ROOT/app" && npm install)
  fi

  cleanup() {
    trap - INT TERM EXIT
    kill 0 2>/dev/null || true
  }
  trap cleanup INT TERM EXIT

  echo "API     http://localhost:8000/docs  (in-process job worker)"
  echo "Studio  http://localhost:5174"
  echo "Builder http://localhost:5173"
  echo "Token   $STUDIO_API_TOKEN"
  (
    cd "$ROOT/studio"
    "$ROOT/studio/.venv/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000
  ) &
  (cd "$ROOT/studio-web" && npm run dev) &
  (cd "$ROOT/app" && npm run dev) &
  wait
}

case "$ROLE" in
  api) start_api ;;
  web) start_web ;;
  app) start_app ;;
  worker) start_worker ;;
  all) start_all ;;
  *)
    echo "Usage: $0 [api|web|app|worker|all]" >&2
    exit 1
    ;;
esac
