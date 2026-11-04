#!/usr/bin/env bash
set -e; cd "$(dirname "$0")/backend"
[ -f ../.env ] && set -a && . ../.env && set +a
python3 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements.txt
python -m pytest -q tests
exec uvicorn main:app --port 8000
