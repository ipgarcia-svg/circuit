#!/usr/bin/env python3
"""
Coleta sinais de "tração" para cada filme e salva em site/buzz.json.

Sinais (todos gratuitos, sem API key adicional):
  - Trakt watchers  — endpoint público (só precisa de TRAKT_CLIENT_ID)
  - Google News RSS — artigos dos últimos 30 dias
  - Reddit          — posts dos últimos 30 dias

Opcional:
  - TMDB popularity — requer TMDB_API_KEY (cadastro gratuito em themoviedb.org)

Uso:
  python3 build_buzz.py
"""
import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import trakt_client  # carrega .env

MOVIES_FILE = Path("site/movies.json")
BUZZ_FILE = Path("site/buzz.json")


def _get(url, extra_headers=None):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Circuit/1.0)"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=12) as r:
        return r.read().decode("utf-8")


def fetch_trakt_watchers(trakt_id):
    if not trakt_id:
        return 0
    client_id = os.environ.get("TRAKT_CLIENT_ID")
    if not client_id:
        return 0
    try:
        text = _get(
            f"https://api.trakt.tv/movies/{trakt_id}/stats",
            {"trakt-api-version": "2", "trakt-api-key": client_id},
        )
        return json.loads(text).get("watchers") or 0
    except Exception:
        return 0


def fetch_tmdb_popularity(tmdb_id):
    api_key = os.environ.get("TMDB_API_KEY")
    if not api_key or not tmdb_id:
        return None
    try:
        text = _get(f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={api_key}")
        return json.loads(text).get("popularity")
    except Exception:
        return None


def fetch_news_count(title, year):
    q = urllib.parse.quote(f'"{title}" film')
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        tree = ET.fromstring(_get(url))
        count = 0
        for item in tree.findall(".//item"):
            pub = item.findtext("pubDate") or ""
            try:
                if parsedate_to_datetime(pub) > cutoff:
                    count += 1
            except Exception:
                count += 1
        return count
    except Exception:
        return 0


def fetch_reddit_count(title):
    q = urllib.parse.quote(f'"{title}"')
    url = f"https://www.reddit.com/search.json?q={q}&sort=new&t=month&limit=25&type=link"
    try:
        data = json.loads(_get(url, {"User-Agent": "Circuit/1.0 (buzz tracker)"}))
        return data.get("data", {}).get("dist") or 0
    except Exception:
        return 0


def normalize(values):
    clean = [v for v in values if v is not None]
    if not clean:
        return [0.0] * len(values)
    lo, hi = min(clean), max(clean)
    if hi == lo:
        return [50.0 if v is not None else 0.0 for v in values]
    return [
        round((v - lo) / (hi - lo) * 100, 1) if v is not None else 0.0
        for v in values
    ]


def load_previous():
    try:
        data = json.loads(BUZZ_FILE.read_text(encoding="utf-8"))
        return {m["trakt"]: m["buzz_score"] for m in data.get("movies", []) if m.get("trakt")}
    except Exception:
        return {}


def main():
    if not MOVIES_FILE.exists():
        raise SystemExit(f"{MOVIES_FILE} não encontrado. Rode build_trakt_site_data.py primeiro.")

    movies = json.loads(MOVIES_FILE.read_text(encoding="utf-8")).get("movies", [])
    if not movies:
        raise SystemExit("Nenhum filme em movies.json.")

    print(f"Coletando sinais de tração para {len(movies)} filmes…")
    previous = load_previous()
    raw = []

    for i, movie in enumerate(movies, start=1):
        title = movie.get("title") or ""
        year = movie.get("year")
        trakt_id = movie.get("trakt") or movie.get("slug")
        tmdb_id = movie.get("tmdb")

        watchers = fetch_trakt_watchers(trakt_id)
        tmdb_pop = fetch_tmdb_popularity(tmdb_id)
        time.sleep(0.3)
        news = fetch_news_count(title, year)
        time.sleep(0.3)
        reddit = fetch_reddit_count(title)
        time.sleep(0.3)

        raw.append({
            "trakt": movie.get("trakt"),
            "title": title,
            "year": year,
            "watchers": watchers,
            "tmdb_popularity": tmdb_pop,
            "news_count": news,
            "reddit_count": reddit,
        })

        if i % 10 == 0:
            print(f"  {i}/{len(movies)} processados…")

    w_norm = normalize([r["watchers"] for r in raw])
    t_norm = normalize([r["tmdb_popularity"] for r in raw])
    n_norm = normalize([r["news_count"] for r in raw])
    r_norm = normalize([r["reddit_count"] for r in raw])
    has_tmdb = any(r["tmdb_popularity"] is not None for r in raw)

    result = []
    for i, r in enumerate(raw):
        if has_tmdb:
            score = w_norm[i] * 0.35 + t_norm[i] * 0.30 + n_norm[i] * 0.20 + r_norm[i] * 0.15
        else:
            score = w_norm[i] * 0.45 + n_norm[i] * 0.30 + r_norm[i] * 0.25
        score = round(score, 1)

        prev = previous.get(r["trakt"])
        if prev is None:
            trend = "new"
        elif score >= prev + 5:
            trend = "rising"
        elif score <= prev - 5:
            trend = "falling"
        else:
            trend = "stable"

        result.append({**r, "buzz_score": score, "prev_score": prev, "trend": trend})

    BUZZ_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUZZ_FILE.write_text(
        json.dumps(
            {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "movies": sorted(result, key=lambda x: -x["buzz_score"]),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rising = sum(1 for r in result if r["trend"] == "rising")
    print(f"Gerado {BUZZ_FILE} — {len(result)} filmes, {rising} em alta.")


if __name__ == "__main__":
    main()
