#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

for service in api web; do
  pid_file=".run/$service.pid"
  if [ -f "$pid_file" ]; then
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
    fi
    rm -f "$pid_file"
  fi
done

if [ -f .run/searxng-managed ]; then
  if command -v docker >/dev/null 2>&1; then
    docker compose --profile mafer stop searxng >/dev/null 2>&1 || true
  fi
  rm -f .run/searxng-managed
fi

printf '%s\n' "MIRSAD stopped."
