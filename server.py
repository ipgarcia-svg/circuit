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
import subprocess
import threading
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path

import trakt_client

PORT        = 8787
PROJECT_DIR = Path(__file__).parent
SITE_DIR    = PROJECT_DIR / "site"
SLUG_FILE   = PROJECT_DIR / ".trakt_list_slug"

_rebuild_lock   = threading.Lock()
_rebuild_status = {"state": "idle", "message": ""}


def _run_rebuild():
    global _rebuild_status
    script = PROJECT_DIR / "build_trakt_site_data.py"
    try:
        result = subprocess.run(
            ["python3", str(script)],
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        if result.returncode == 0:
            _rebuild_status = {"state": "done", "message": result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "Concluído."}
        else:
            _rebuild_status = {"state": "error", "message": result.stderr.strip() or "Erro desconhecido."}
    except subprocess.TimeoutExpired:
        _rebuild_status = {"state": "error", "message": "Timeout após 5 minutos."}
    except Exception as exc:
        _rebuild_status = {"state": "error", "message": str(exc)}


# ── helpers ───────────────────────────────────────────────────────────────────

def get_list_slug() -> str:
    if SLUG_FILE.exists():
        return SLUG_FILE.read_text(encoding="utf-8").strip()
    return os.environ.get("TRAKT_LIST_SLUG", "quero-ver")


# ── request handler ───────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()}  {fmt % args}")

    # ── API ───────────────────────────────────────────────────────────────────

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/want":
            self._handle_get_want()
            return

        if path == "/api/rebuild-status":
            self._respond(200, "application/json", json.dumps(_rebuild_status).encode())
            return

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

    def _handle_rebuild(self):
        global _rebuild_status
        if not _rebuild_lock.acquire(blocking=False):
            self._respond(409, "application/json", json.dumps({"error": "already running"}).encode())
            return
        _rebuild_status = {"state": "running", "message": "Buscando dados no Trakt…"}
        t = threading.Thread(target=lambda: (_run_rebuild(), _rebuild_lock.release()), daemon=True)
        t.start()
        self._respond(202, "application/json", json.dumps({"ok": True}).encode())

    def _handle_get_want(self):
        token = trakt_client.load_token()
        if not token:
            self._respond(500, "application/json", json.dumps({"error": "no token"}).encode())
            return
        slug = get_list_slug()
        try:
            items = trakt_client.call("GET", f"/users/me/lists/{urllib.parse.quote(slug)}/items/movies", token=token)
            trakt_ids = [
                item["movie"]["ids"]["trakt"]
                for item in items
                if item.get("movie", {}).get("ids", {}).get("trakt")
            ]
            self._respond(200, "application/json", json.dumps({"trakt_ids": trakt_ids}).encode())
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            self._respond(exc.code, "application/json", json.dumps({"error": details}).encode())
        except Exception as exc:
            self._respond(502, "application/json", json.dumps({"error": str(exc)}).encode())

    def do_POST(self):
        if self.path == "/api/rebuild":
            self._handle_rebuild()
            return

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

        token = trakt_client.load_token()
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
            result = trakt_client.call("POST", endpoint, token=token, body=body)
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
    if not trakt_client.TOKEN_FILE.exists():
        print(f"\n  AVISO: {trakt_client.TOKEN_FILE} não encontrado — sincronização com Trakt desativada.")
    if not os.environ.get("TRAKT_CLIENT_ID"):
        print("\n  AVISO: TRAKT_CLIENT_ID não definido — algumas chamadas ao Trakt podem falhar.")
    slug = get_list_slug()
    print(f"\n  Lista Trakt alvo: {slug}")
    print(f"  Circuit em http://localhost:{PORT}\n")

    server = ThreadingHTTPServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor encerrado.\n")


if __name__ == "__main__":
    main()
