#!/bin/bash
# Daily Mood Screen — scheduled runner for launchd
# Loads .env, then runs main.py from the project directory.

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Load environment variables from .env (skip blank lines and comments)
if [ -f "$PROJECT_DIR/.env" ]; then
    while IFS='=' read -r key val; do
        [[ -z "$key" || "$key" == \#* ]] && continue
        export "$key=$val"
    done < "$PROJECT_DIR/.env"
fi

exec /Users/zy/miniconda3/bin/python main.py
