#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p data reports

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -e '.[dev]'
npm install
npm --prefix apps/web install
