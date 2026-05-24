#!/usr/bin/env python3
"""
Obtém um token OAuth do Trakt via device flow e salva em .trakt_token.json.

Uso:
  python3 get_token.py
"""
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


def post(path, body):
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type":      "application/json",
        "User-Agent":        "Circuit/1.0",
        "trakt-api-version": "2",
    }
    req = urllib.request.Request(API_BASE + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def main():
    client_id     = os.environ.get("TRAKT_CLIENT_ID")
    client_secret = os.environ.get("TRAKT_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise SystemExit("ERRO: defina TRAKT_CLIENT_ID e TRAKT_CLIENT_SECRET no .env antes de rodar.")

    print("Solicitando código de autorização…")
    info = post("/oauth/device/code", {"client_id": client_id})

    print(f"\n  Abra esta página: {info['verification_url']}")
    print(f"  Código:           {info['user_code']}")
    print("\nAguardando autorização", end="", flush=True)

    interval   = int(info.get("interval", 5))
    expires_at = time.time() + int(info.get("expires_in", 600))

    while time.time() < expires_at:
        time.sleep(interval)
        print(".", end="", flush=True)
        try:
            token = post("/oauth/device/token", {
                "code":          info["device_code"],
                "client_id":     client_id,
                "client_secret": client_secret,
            })
        except RuntimeError as exc:
            msg = str(exc)
            if "400" in msg or "authorization_pending" in msg:
                continue
            if "slow_down" in msg:
                interval += 5
                continue
            raise

        TOKEN_FILE.write_text(json.dumps(token, indent=2), encoding="utf-8")
        print(f"\n\n  Token salvo em {TOKEN_FILE}")
        print("  Agora rode: python3 setup_trakt.py\n")
        return

    raise SystemExit("\nERRO: código expirou antes da autorização.")


if __name__ == "__main__":
    main()
