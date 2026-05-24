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
  • .trakt_token.json válido na raiz do projeto (gerado por get_token.py)
  • TRAKT_CLIENT_ID no ambiente ou no .env

Uso:
  python3 setup_trakt.py
"""

import os
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import trakt_client  # também carrega o .env automaticamente

SLUG_FILE      = Path(__file__).parent / ".trakt_list_slug"
SLUG_TO_DELETE = "sundance-2026-feature-film-program"
NEW_LIST_NAME  = "Quero ver"
NEW_LIST_DESC  = (
    "Filmes de festivais que quero assistir, "
    "sincronizados automaticamente pelo Circuit."
)


def request_json(method, path, *, token, body=None):
    try:
        return trakt_client.call(method, path, token=token, body=body)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Trakt HTTP {exc.code}: {details}") from exc


def main():
    client_id = os.environ.get("TRAKT_CLIENT_ID")
    if not client_id:
        print(
            "ERRO: TRAKT_CLIENT_ID não definido.\n"
            "  Adicione ao .env ou exporte antes de rodar.",
            file=sys.stderr,
        )
        return 2

    token = trakt_client.load_token()
    if not token:
        print(
            f"ERRO: {trakt_client.TOKEN_FILE} não encontrado.\n"
            "  Rode primeiro: python3 get_token.py",
            file=sys.stderr,
        )
        return 2

    # 1. listar listas atuais
    print("\nBuscando suas listas no Trakt…")
    lists = request_json("GET", "/users/me/lists", token=token)
    print(f"  {len(lists)} lista(s) encontrada(s):")
    for lst in lists:
        print(f"    · {lst['name']}  (slug: {lst['ids']['slug']})")

    # Verifica se "Quero ver" já existe
    existing = next((l for l in lists if l["name"].lower() == NEW_LIST_NAME.lower()), None)
    if existing:
        slug = existing["ids"]["slug"]
        print(f'\n  A lista "{NEW_LIST_NAME}" já existe (slug: {slug}).')
        SLUG_FILE.write_text(slug, encoding="utf-8")
        print(f"  Slug salvo em {SLUG_FILE.name}")
        print(f"\n  Pronto → https://trakt.tv/users/me/lists/{slug}\n")
        return 0

    # 2. deletar lista antiga (opcional)
    target = next((l for l in lists if l["ids"]["slug"] == SLUG_TO_DELETE), None)
    if target:
        print(f'\n  Encontrada lista para substituir: "{target["name"]}" (slug: {SLUG_TO_DELETE})')
        answer = input("  Deletar esta lista para liberar espaço? [s/N] ").strip().lower()
        if answer == "s":
            request_json(
                "DELETE",
                f"/users/me/lists/{urllib.parse.quote(SLUG_TO_DELETE)}",
                token=token,
            )
            print(f'  ✓ Lista "{target["name"]}" deletada.')
        else:
            print("  Pulando deleção — se atingiu o limite de listas, a criação abaixo pode falhar.")
    else:
        print(f'\n  Lista "{SLUG_TO_DELETE}" não encontrada — nenhuma deleção necessária.')

    # 3. criar "Quero ver"
    print(f'\nCriando lista "{NEW_LIST_NAME}"…')
    created = request_json(
        "POST",
        "/users/me/lists",
        token=token,
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
