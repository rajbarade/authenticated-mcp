#!/usr/bin/env bash
set -euo pipefail
# App Service's owner must set Startup Command to: bash startup.sh
# Oryx activates the environment containing requirements.txt dependencies.
exec python -m uvicorn app.main:create_app --factory \
  --host 0.0.0.0 --port 8000 --no-access-log --no-proxy-headers
