#!/bin/bash
# Daily Mood Screen — called by launchd at 7:00 AM
# API keys live in .env (never committed to git)

set -e
cd "$(dirname "$0")"

# Load secrets from .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

/Users/zy/miniconda3/bin/python3 main.py
