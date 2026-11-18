#!/usr/bin/env bash
# Development helper. Run inside WSL (Docker daemon lives there):
#   wsl -e bash /mnt/d/Projects/Hackathon/dev/run.sh <command> [args]
# Commands:
#   build            build the dev image (Python dependencies only)
#   test [args]      run pytest in a throwaway container, e.g. test tests -q
#   py [args]        run python in a throwaway container, e.g. py -m app.sim.run
#   up [port]        start the API on http://localhost:<port> (default 8000), own container and database per port
#   down [port]      stop that API
#   logs [port] [n]  show the last n log lines of that API
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG=halqa-dev
RUN=(docker run --rm -e SQLITE_PATH=/tmp/halqa.db -e PYTHONPATH=/srv/backend -v "$ROOT":/srv -w /srv/backend)

cmd="${1:-help}"
shift || true

case "$cmd" in
  build) docker build -t "$IMG" -f "$ROOT/dev/Dockerfile.dev" "$ROOT" ;;
  test)  "${RUN[@]}" "$IMG" python -m pytest "$@" ;;
  py)    "${RUN[@]}" "$IMG" python "$@" ;;
  up)
    # up [port] : each port gets its own container and its own database.
    PORT="${1:-8000}"
    docker rm -f "halqa-api-$PORT" >/dev/null 2>&1 || true
    docker run -d --name "halqa-api-$PORT" -p "$PORT":8000 \
      -e SQLITE_PATH=/tmp/halqa.db -e PYTHONPATH=/srv/backend \
      -v "$ROOT":/srv -w /srv/backend "$IMG" \
      uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /srv/backend/app
    ;;
  down)  docker rm -f "halqa-api-${1:-8000}" ;;
  logs)  docker logs --tail "${2:-80}" "halqa-api-${1:-8000}" ;;
  *)     sed -n '2,11p' "$0" ;;
esac
