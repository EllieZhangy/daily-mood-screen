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

# Easy on/off switch for the scheduled daily run — set AUTO_RUN=true in .env
# to re-enable. The launchd job stays registered either way; this just makes
# each scheduled trigger a no-op while AUTO_RUN is not "true".
if [ "${AUTO_RUN:-false}" != "true" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S')  AUTO_RUN is not 'true' — skipping scheduled run."
    exit 0
fi

exec /Users/zy/miniconda3/bin/python main.py
