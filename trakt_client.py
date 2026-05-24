#!/usr/bin/env python3
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API_BASE   = "https://api.trakt.tv"
TOKEN_FILE = Path(__file__).parent / ".trakt_token.json"

# Carrega .env se existir
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


def _raw_post(path, body, extra_headers=None):
    headers = {
        "Content-Type":      "application/json",
        "User-Agent":        "Circuit/1.0",
        "trakt-api-version": "2",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(API_BASE + path, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _refresh(token_data):
    client_id     = os.environ.get("TRAKT_CLIENT_ID")
    client_secret = os.environ.get("TRAKT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    try:
        new_data = _raw_post("/oauth/token", {
            "refresh_token": token_data["refresh_token"],
            "client_id":     client_id,
            "client_secret": client_secret,
            "redirect_uri":  "urn:ietf:wg:oauth:2.0:oob",
            "grant_type":    "refresh_token",
        })
        TOKEN_FILE.write_text(json.dumps(new_data, indent=2), encoding="utf-8")
        print("  Token Trakt renovado automaticamente.")
        return new_data.get("access_token")
    except Exception as exc:
        print(f"  Aviso: falha ao renovar token Trakt: {exc}")
        return None


def load_token():
    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None

    # Renova se expirar em menos de 7 dias
    created_at = data.get("created_at", 0)
    expires_in = data.get("expires_in", 7776000)
    if time.time() > created_at + expires_in - 7 * 86400:
        refreshed = _refresh(data)
        if refreshed:
            return refreshed

    return data.get("access_token")


def call(method, path, *, token, body=None):
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
