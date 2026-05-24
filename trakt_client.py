#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API_BASE   = "https://api.trakt.tv"
TOKEN_FILE = Path(__file__).parent / ".trakt_token.json"


def load_token() -> str | None:
    try:
        return json.loads(TOKEN_FILE.read_text(encoding="utf-8")).get("access_token")
    except Exception:
        return None


def call(method: str, path: str, *, token: str, body=None) -> dict:
    client_id = os.environ.get("TRAKT_CLIENT_ID")
    headers = {
        "Content-Type":      "application/json",
        "User-Agent":        "Circuit/1.0",
        "trakt-api-version": "2",
        "Authorization":     f"Bearer {token}",
    }
    if client_id:
        headers["trakt-api-key"] = client_id
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req  = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        text = r.read().decode("utf-8")
        return json.loads(text) if text else {}
