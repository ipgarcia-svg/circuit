#!/usr/bin/env python3
"""
Circuit — servidor local na porta 8787.

Serve os arquivos estáticos em site/ e expõe o endpoint:
  POST /api/want  { "trakt_id": <int>, "action": "add" | "remove" }

Pré-requisitos:
  • .trakt_token.json válido na raiz do projeto
  • (opcional) TRAKT_CLIENT_ID no ambiente — necessário para vários
    endpoints autenticados do Trakt; sem ele as chamadas têm maior
    chance de retornar 401.
  • .trakt_list_slug (criado por setup_trakt.py) ou variável
    TRAKT_LIST_SLUG; se nenhum dos dois existir usa "quero-ver".

Uso:
  python3 server.py
  # ou simplesmente: ./start.sh
"""

import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8787
PROJECT_DIR = Path(__file__).parent
SITE_DIR    = PROJECT_DIR / "site"
TOKEN_FILE  = PROJECT_DIR / ".trakt_token.json"
SLUG_FILE   = PROJECT_DIR / ".trakt_list_slug"
API_BASE    = "https://api.trakt.tv"


# ── helpers ───────────────────────────────────────────────────────────────────

def load_token():
    try:
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        return data.get("access_token")
    except Exception:
        return None


def get_list_slug() -> str:
    if SLUG_FILE.exists():
        return SLUG_FILE.read_text(encoding="utf-8").strip()
    return os.environ.get("TRAKT_LIST_SLUG", "quero-ver")


def trakt_call(method, path, *, token, body=None):
    client_id = os.environ.get("TRAKT_CLIENT_ID")
    headers = {
        "Content-Type":    "application/json",
        "User-Agent":      "Circuit/1.0",
        "trakt-api-version": "2",
        "Authorization":   f"Bearer {token}",
    }
    if client_id:
        headers["trakt-api-key"] = client_id
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req  = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        text = r.read().decode("utf-8")
        return json.loads(text) if text else {}


# ── request handler ───────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()}  {fmt % args}")

    # ── static files ──────────────────────────────────────────────────────────

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            path = "/index.html"

        # Prevent directory traversal
        file_path = (SITE_DIR / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(SITE_DIR.resolve())):
            self._respond(403, "text/plain", b"Forbidden")
            return

        if not file_path.exists() or file_path.is_dir():
            self._respond(404, "text/plain", b"Not found")
            return

        mime, _ = mimetypes.guess_type(str(file_path))
        mime = mime or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ── API ───────────────────────────────────────────────────────────────────

    def do_POST(self):
        if self.path != "/api/want":
            self._respond(404, "application/json", json.dumps({"error": "not found"}).encode())
            return

        # Parse request body
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._respond(400, "application/json", json.dumps({"error": "invalid json"}).encode())
            return

        trakt_id = payload.get("trakt_id")
        action   = payload.get("action")

        if not trakt_id or action not in ("add", "remove"):
            self._respond(400, "application/json",
                json.dumps({"error": "trakt_id and action ('add'|'remove') are required"}).encode())
            return

        token = load_token()
        if not token:
            print("  AVISO: .trakt_token.json não encontrado ou inválido.")
            self._respond(500, "application/json", json.dumps({"error": "no token"}).encode())
            return

        slug     = get_list_slug()
        endpoint = f"/users/me/lists/{urllib.parse.quote(slug)}/items"
        if action == "remove":
            endpoint += "/remove"

        body = {"movies": [{"ids": {"trakt": int(trakt_id)}}]}
        try:
            result = trakt_call("POST", endpoint, token=token, body=body)
            self._respond(200, "application/json", json.dumps({"ok": True, "result": result}).encode())
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            print(f"  Trakt HTTP {exc.code}: {details}")
            self._respond(exc.code, "application/json",
                json.dumps({"error": details}).encode())
        except Exception as exc:
            print(f"  Erro ao chamar Trakt: {exc}")
            self._respond(502, "application/json", json.dumps({"error": str(exc)}).encode())

    # ── util ──────────────────────────────────────────────────────────────────

    def _respond(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    if not TOKEN_FILE.exists():
        print(f"\n  AVISO: {TOKEN_FILE} não encontrado — sincronização com Trakt desativada.")
    if not os.environ.get("TRAKT_CLIENT_ID"):
        print("\n  AVISO: TRAKT_CLIENT_ID não definido — algumas chamadas ao Trakt podem falhar.")
    slug = get_list_slug()
    print(f"\n  Lista Trakt alvo: {slug}")
    print(f"  Circuit em http://localhost:{PORT}\n")

    server = HTTPServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor encerrado.\n")


if __name__ == "__main__":
    main()
