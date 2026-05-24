#!/usr/bin/env python3
"""
Configuração única do Trakt para o Circuit.

O que este script faz:
  1. Lista as listas do usuário no Trakt
  2. (Opcional) Deleta "Sundance 2026 - Feature Film Program"
     para liberar espaço no plano gratuito (limite de 3 listas)
  3. Cria a lista "Quero ver"
  4. Salva o slug em .trakt_list_slug (usado pelo server.py)

Pré-requisitos:
  • .trakt_token.json válido na raiz do projeto
  • TRAKT_CLIENT_ID exportado no ambiente (obrigatório):
      export TRAKT_CLIENT_ID=<seu_client_id>

Uso:
  python3 setup_trakt.py
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_DIR    = Path(__file__).parent
TOKEN_FILE     = PROJECT_DIR / ".trakt_token.json"
SLUG_FILE      = PROJECT_DIR / ".trakt_list_slug"
API_BASE       = "https://api.trakt.tv"

# Slug da lista a ser substituída (ajuste se necessário)
SLUG_TO_DELETE = "sundance-2026-feature-film-program"

NEW_LIST_NAME  = "Quero ver"
NEW_LIST_DESC  = (
    "Filmes de festivais que quero assistir, "
    "sincronizados automaticamente pelo Circuit."
)


# ── helpers ───────────────────────────────────────────────────────────────────

def request_json(method, path, *, token, client_id=None, body=None):
    headers = {
        "Content-Type":      "application/json",
        "User-Agent":        "Circuit Setup/1.0",
        "trakt-api-version": "2",
        "Authorization":     f"Bearer {token}",
    }
    if client_id:
        headers["trakt-api-key"] = client_id
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req  = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Trakt HTTP {exc.code}: {details}") from exc


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    # Credenciais
    client_id = os.environ.get("TRAKT_CLIENT_ID")
    if not client_id:
        print(
            "ERRO: TRAKT_CLIENT_ID não definido.\n"
            "  export TRAKT_CLIENT_ID=<seu_client_id>",
            file=sys.stderr,
        )
        return 2

    if not TOKEN_FILE.exists():
        print(f"ERRO: {TOKEN_FILE} não encontrado.", file=sys.stderr)
        return 2

    token_data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    token      = token_data["access_token"]

    # ── 1. listar listas atuais ───────────────────────────────────────────────
    print("\nBuscando suas listas no Trakt…")
    lists = request_json("GET", "/users/me/lists", token=token, client_id=client_id)
    print(f"  {len(lists)} lista(s) encontrada(s):")
    for lst in lists:
        print(f"    · {lst['name']}  (slug: {lst['ids']['slug']})")

    # Verifica se "Quero ver" já existe
    existing_want = next((l for l in lists if l["name"].lower() == NEW_LIST_NAME.lower()), None)
    if existing_want:
        slug = existing_want["ids"]["slug"]
        print(f'\n  A lista "{NEW_LIST_NAME}" já existe (slug: {slug}).')
        SLUG_FILE.write_text(slug, encoding="utf-8")
        print(f"  Slug salvo em {SLUG_FILE.name}")
        print(f"\n  Pronto → https://trakt.tv/users/me/lists/{slug}\n")
        return 0

    # ── 2. deletar lista antiga (opcional) ────────────────────────────────────
    target = next((l for l in lists if l["ids"]["slug"] == SLUG_TO_DELETE), None)
    if target:
        print(f'\n  Encontrada lista para substituir: "{target["name"]}" (slug: {SLUG_TO_DELETE})')
        answer = input("  Deletar esta lista para liberar espaço? [s/N] ").strip().lower()
        if answer == "s":
            request_json(
                "DELETE",
                f"/users/me/lists/{urllib.parse.quote(SLUG_TO_DELETE)}",
                token=token,
                client_id=client_id,
            )
            print(f'  ✓ Lista "{target["name"]}" deletada.')
        else:
            print("  Pulando deleção — se você atingiu o limite de listas, a criação abaixo pode falhar.")
    else:
        print(f'\n  Lista com slug "{SLUG_TO_DELETE}" não encontrada — nenhuma deleção necessária.')

    # ── 3. criar "Quero ver" ──────────────────────────────────────────────────
    print(f'\nCriando lista "{NEW_LIST_NAME}"…')
    created = request_json(
        "POST",
        "/users/me/lists",
        token=token,
        client_id=client_id,
        body={
            "name":            NEW_LIST_NAME,
            "description":     NEW_LIST_DESC,
            "privacy":         "private",
            "display_numbers": False,
            "allow_comments":  True,
            "sort_by":         "added",
            "sort_how":        "desc",
        },
    )
    slug = created["ids"]["slug"]
    SLUG_FILE.write_text(slug, encoding="utf-8")
    print(f"  ✓ Lista criada!  Slug: {slug}")
    print(f"  ✓ Slug salvo em {SLUG_FILE.name}")
    print(f"\n  Pronto → https://trakt.tv/users/me/lists/{slug}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
