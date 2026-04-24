#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "Backend virtualenv not found."
  echo "Run from the repo root:"
  echo "  cd backend && python -m venv .venv && pip install -r requirements.txt"
  exit 1
fi

cd "$BACKEND_DIR"
# shellcheck disable=SC1091
source .venv/bin/activate

pids=()
cleanup() {
  echo "Shutting down backend and worker..."
  kill "${pids[@]}" 2>/dev/null || true
}
trap cleanup EXIT

echo "Starting backend API..."
uvicorn main:app --reload --port 8000 &
pids+=("$!")

echo "Starting Celery worker..."
celery -A celery_worker.celery_app worker --loglevel=info &
pids+=("$!")

cd "$FRONTEND_DIR"
echo "Starting frontend..."
npm run dev
