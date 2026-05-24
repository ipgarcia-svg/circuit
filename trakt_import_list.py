#!/usr/bin/env python3
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_BASE = "https://api.trakt.tv"
TOKEN_FILE = Path(".trakt_token.json")


def request_json(method, path_or_url, *, client_id=None, token=None, body=None):
    url = path_or_url if path_or_url.startswith("http") else API_BASE + path_or_url
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Codex Trakt Sundance Importer/1.0",
        "trakt-api-version": "2",
    }
    if client_id:
        headers["trakt-api-key"] = client_id
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Trakt respondeu HTTP {exc.code}: {details}") from exc


def load_saved_token():
    if not TOKEN_FILE.exists():
        return None
    try:
        token_data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return token_data.get("access_token")


def get_device_token(client_id, client_secret):
    code_info = request_json(
        "POST",
        "/oauth/device/code",
        body={"client_id": client_id},
    )

    print()
    print("Abra esta pagina no navegador e confirme o codigo:")
    print(f"  {code_info['verification_url']}")
    print(f"  Codigo: {code_info['user_code']}")
    print()

    device_code = code_info["device_code"]
    interval = int(code_info.get("interval", 5))
    expires_at = time.time() + int(code_info.get("expires_in", 600))

    while time.time() < expires_at:
        time.sleep(interval)
        try:
            token_data = request_json(
                "POST",
                "/oauth/device/token",
                body={
                    "code": device_code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
        except RuntimeError as exc:
            message = str(exc)
            if "authorization_pending" in message or "HTTP 400" in message:
                print("Aguardando autorizacao...")
                continue
            if "slow_down" in message:
                interval += 5
                continue
            raise

        TOKEN_FILE.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
        return token_data["access_token"]

    raise RuntimeError("O codigo expirou antes da autorizacao.")


def load_items(path):
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(path)

    if source.suffix.lower() == ".json":
        rows = json.loads(source.read_text(encoding="utf-8"))
    else:
        with source.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))

    movies = []
    shows = []
    for index, row in enumerate(rows, start=1):
        item_type = (row.get("type") or row.get("tipo") or "movie").strip().lower()
        title = (row.get("title") or row.get("titulo") or row.get("name") or "").strip()
        year = (row.get("year") or row.get("ano") or "").strip()
        imdb = (row.get("imdb") or row.get("imdb_id") or "").strip()
        tmdb = (row.get("tmdb") or row.get("tmdb_id") or "").strip()
        trakt = (row.get("trakt") or row.get("trakt_id") or "").strip()

        ids = {}
        if imdb:
            ids["imdb"] = imdb
        if tmdb:
            ids["tmdb"] = int(tmdb)
        if trakt:
            ids["trakt"] = int(trakt)

        item = {}
        if title:
            item["title"] = title
        if year:
            item["year"] = int(year)
        if ids:
            item["ids"] = ids

        if not item:
            raise ValueError(f"Linha {index} nao tem titulo nem ids.")

        if item_type in {"show", "shows", "serie", "series", "tv"}:
            shows.append(item)
        elif item_type in {"movie", "movies", "filme", "filmes"}:
            movies.append(item)
        else:
            raise ValueError(f"Linha {index} tem tipo desconhecido: {item_type}")

    payload = {}
    if movies:
        payload["movies"] = movies
    if shows:
        payload["shows"] = shows
    return payload


def create_list(client_id, token, args):
    body = {
        "name": args.name,
        "description": args.description or "",
        "privacy": args.privacy,
        "display_numbers": True,
        "allow_comments": True,
        "sort_by": "rank",
        "sort_how": "asc",
    }
    created = request_json("POST", "/users/me/lists", client_id=client_id, token=token, body=body)
    return created["ids"]["slug"]


def chunks(values, size):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def add_items(client_id, token, list_id, payload, chunk_size):
    combined = []
    for key, values in payload.items():
        for item in values:
            combined.append((key, item))

    summary = {"added": {}, "existing": {}, "not_found": {}}
    for group in chunks(combined, chunk_size):
        body = {}
        for key, item in group:
            body.setdefault(key, []).append(item)
        result = request_json(
            "POST",
            f"/users/me/lists/{urllib.parse.quote(str(list_id))}/items",
            client_id=client_id,
            token=token,
            body=body,
        )
        for bucket in summary:
            for media_type, value in result.get(bucket, {}).items():
                if isinstance(value, list):
                    summary[bucket].setdefault(media_type, []).extend(value)
                else:
                    summary[bucket][media_type] = summary[bucket].get(media_type, 0) + value

    return summary


def main():
    parser = argparse.ArgumentParser(description="Cria/preenche uma lista do Trakt a partir de CSV ou JSON.")
    parser.add_argument("--input", required=True, help="Arquivo CSV ou JSON com os indicados.")
    parser.add_argument("--name", default="Sundance - Indicados", help="Nome da lista nova.")
    parser.add_argument("--description", default="", help="Descricao da lista nova.")
    parser.add_argument("--privacy", default="private", choices=["private", "friends", "public"])
    parser.add_argument("--list-id", help="Slug ou id de uma lista existente. Se omitido, cria lista nova.")
    parser.add_argument("--chunk-size", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true", help="Mostra o que seria enviado, sem chamar o Trakt.")
    args = parser.parse_args()

    client_id = os.environ.get("TRAKT_CLIENT_ID")
    client_secret = os.environ.get("TRAKT_CLIENT_SECRET")

    payload = load_items(args.input)
    total = sum(len(values) for values in payload.values())

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"\nTotal: {total} item(ns).")
        return 0

    if not client_id:
        print("Defina TRAKT_CLIENT_ID antes de rodar.", file=sys.stderr)
        return 2

    token = os.environ.get("TRAKT_ACCESS_TOKEN") or load_saved_token()
    if not token:
        if not client_secret:
            print("Defina TRAKT_CLIENT_SECRET para autenticar pela primeira vez.", file=sys.stderr)
            return 2
        token = get_device_token(client_id, client_secret)

    list_id = args.list_id or create_list(client_id, token, args)
    print(f"Lista alvo: {list_id}")
    print(f"Enviando {total} item(ns)...")

    summary = add_items(client_id, token, list_id, payload, args.chunk_size)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nPronto: https://trakt.tv/users/me/lists/{list_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
