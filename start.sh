#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

npm run doctor
mkdir -p .run data reports

searxng_enabled=false
searxng_url=http://127.0.0.1:8080
configured_enabled=${SEARXNG_ENABLED:-}
configured_url=${SEARXNG_URL:-}
if [ -f .env ]; then
  if [ -z "$configured_enabled" ]; then
    configured_enabled=$(sed -n 's/^[[:space:]]*SEARXNG_ENABLED[[:space:]]*=[[:space:]]*//p' .env | tail -n 1 | tr -d '\r"\047')
  fi
  if [ -z "$configured_url" ]; then
    configured_url=$(sed -n 's/^[[:space:]]*SEARXNG_URL[[:space:]]*=[[:space:]]*//p' .env | tail -n 1 | tr -d '\r"\047')
  fi
fi
configured_enabled=$(printf '%s' "$configured_enabled" | tr '[:upper:]' '[:lower:]')
case "$configured_enabled" in
  1|true|yes|on) searxng_enabled=true ;;
esac
if [ -n "$configured_url" ]; then
  searxng_url=${configured_url%/}
fi

if [ "$searxng_enabled" = true ]; then
  if command -v docker >/dev/null 2>&1 && docker compose --profile mafer up -d searxng >/dev/null 2>&1; then
    printf '%s\n' "managed" >.run/searxng-managed
    searx_ready=0
    searx_attempt=0
    while [ "$searx_attempt" -lt 20 ]; do
      if curl --silent --fail --max-time 1 "$searxng_url/search?q=MIRSAD&format=json" >/dev/null; then
        searx_ready=1
        break
      fi
      searx_attempt=$((searx_attempt + 1))
      sleep 0.5
    done
    if [ "$searx_ready" -eq 1 ]; then
      printf '%s\n' "SearXNG JSON API ready on configured local endpoint."
    else
      printf '%s\n' "SearXNG enabled but not ready; WEB_INDEX will report degraded external state."
    fi
  else
    printf '%s\n' "SearXNG enabled but the local container could not start; direct/public sources remain available."
  fi
fi

for service in api web; do
  pid_file=".run/$service.pid"
  if [ -f "$pid_file" ]; then
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      printf '%s\n' "MIRSAD appears to be running. Use ./stop.sh first."
      exit 1
    fi
    rm -f "$pid_file"
  fi
done

port_is_available() {
  .venv/bin/python - "$1" <<'PY'
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        raise SystemExit(1)
PY
}

for port in 8000 5173; do
  if ! port_is_available "$port"; then
    printf '%s\n' "Startup refused: localhost port $port is already in use by an unmanaged process."
    printf '%s\n' "Stop the existing service or use its owning process manager before retrying."
    exit 1
  fi
done

nohup .venv/bin/python -m uvicorn mirsad_api.main:app --host 127.0.0.1 --port 8000 \
  </dev/null >.run/api.log 2>&1 &
printf '%s\n' "$!" >.run/api.pid
nohup apps/web/node_modules/.bin/vite apps/web --host 127.0.0.1 --port 5173 \
  --strictPort </dev/null >.run/web.log 2>&1 &
printf '%s\n' "$!" >.run/web.pid

ready=0
attempt=0
while [ "$attempt" -lt 40 ]; do
  if ! kill -0 "$(cat .run/api.pid)" 2>/dev/null || \
     ! kill -0 "$(cat .run/web.pid)" 2>/dev/null; then
    break
  fi
  if curl --silent --fail --max-time 1 http://127.0.0.1:8000/api/v1/health >/dev/null && \
     curl --silent --fail --max-time 1 http://127.0.0.1:5173/ >/dev/null; then
    ready=1
    break
  fi
  attempt=$((attempt + 1))
  sleep 0.25
done

if [ "$ready" -ne 1 ]; then
  printf '%s\n' "Startup failed: services did not become ready on ports 8000 and 5173."
  printf '%s\n' "Inspect .run/api.log and .run/web.log."
  ./stop.sh
  exit 1
fi

printf '%s\n' "MIRSAD started: http://127.0.0.1:5173"
printf '%s\n' "Logs: .run/api.log and .run/web.log"
