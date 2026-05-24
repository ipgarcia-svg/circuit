#!/bin/bash
# Inicia o Circuit em http://localhost:8787
cd "$(dirname "$0")"
exec python3 server.py
