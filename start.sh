#!/bin/bash
# Inicia o Circuit em http://localhost:8787
cd "$(dirname "$0")"
if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi
exec python3 server.py
