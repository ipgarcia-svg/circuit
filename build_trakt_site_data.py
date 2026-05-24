#!/usr/bin/env python3
import csv
import difflib
import json
import os
import time
import urllib.parse
import urllib.request
import unicodedata
from pathlib import Path

# Carrega .env se existir (permite rodar direto com python3 build_trakt_site_data.py)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


API_BASE = "https://api.trakt.tv"
OUTPUT = Path("site/movies.json")
TOKEN_FILE = Path(".trakt_token.json")
MANUAL_TRAKT_IDS = {
    ("love me", 2024): 705999,
    ("jane", 2017): 318126,
    ("collective", 2020): 461379,
    ("ibelin", 2024): 940447,
    ("slacker", 1991): 8376,
    ("crumb", 1994): 16173,
}

_sources_file = Path(__file__).parent / "sources.json"
SOURCES = json.loads(_sources_file.read_text(encoding="utf-8")) if _sources_file.exists() else []


def headers():
    client_id = os.environ.get("TRAKT_CLIENT_ID")
    if not client_id:
        raise SystemExit("Defina TRAKT_CLIENT_ID antes de rodar.")
    result = {
        "Content-Type": "application/json",
        "User-Agent": "Codex Trakt Sundance Browser/1.0",
        "trakt-api-version": "2",
        "trakt-api-key": client_id,
    }
    if TOKEN_FILE.exists():
        token = json.loads(TOKEN_FILE.read_text(encoding="utf-8")).get("access_token")
        if token:
            result["Authorization"] = f"Bearer {token}"
    return result


def get_json(path):
    req = urllib.request.Request(API_BASE + path, headers=headers())
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def read_sources():
    by_key = {}
    for source in SOURCES:
        path = Path(source["file"])
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                title = (row.get("title") or "").strip()
                year = (row.get("year") or "").strip()
                trakt_id = (row.get("trakt_id") or "").strip()
                key = trakt_id or f"{title.lower()}::{year}"
                item = by_key.setdefault(
                    key,
                    {
                        "input_title": title,
                        "input_year": int(year) if year else None,
                        "trakt_id": int(trakt_id) if trakt_id else None,
                        "lists": [],
                        "themes": [],
                        "award_years": [],
                    },
                )
                manual_id = MANUAL_TRAKT_IDS.get((title.lower(), int(year) if year else None))
                if manual_id and not item["trakt_id"]:
                    item["trakt_id"] = manual_id
                item["lists"].append(source["list"])
                if source["theme"] not in item["themes"]:
                    item["themes"].append(source["theme"])
                award_year = (row.get("award_year") or "").strip()
                if award_year and int(award_year) not in item["award_years"]:
                    item["award_years"].append(int(award_year))
    return list(by_key.values())


def search_movie(title, year):
    query = urllib.parse.quote(title)
    year_param = f"&years={year}" if year else ""
    results = get_json(f"/search/movie?query={query}{year_param}&extended=full")
    if not results and year:
        results = get_json(f"/search/movie?query={query}&extended=full")
    if not results:
        return None
    return results[0].get("movie")


def slugify(title, year):
    value = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    chars = []
    for char in value.lower():
        chars.append(char if char.isalnum() else "-")
    slug = "-".join(part for part in "".join(chars).split("-") if part)
    return f"{slug}-{year}" if year else slug


def get_movie_by_slug(title, year):
    if not title or not year:
        return None
    try:
        return get_movie_by_id(slugify(title, year))
    except Exception:
        return None


def normalize_title(value):
    keep = []
    for char in value.lower():
        keep.append(char if char.isalnum() else " ")
    return " ".join("".join(keep).split())


def plausible_match(input_title, movie):
    found = movie.get("title") or ""
    original = normalize_title(input_title)
    candidate = normalize_title(found)
    if not original or not candidate:
        return False
    if original == candidate:
        return True
    if len(original) >= 8 and (original in candidate or candidate in original):
        return True
    ratio = difflib.SequenceMatcher(None, original, candidate).ratio()
    return ratio >= 0.72


def get_movie_by_id(trakt_id):
    return get_json(f"/movies/{trakt_id}?extended=full")


def classify(movie, item):
    genres = set(movie.get("genres") or [])
    themes = set(item["themes"])
    tags = []
    if "Documentary" in themes or "documentary" in genres:
        tags.append("Documentary")
    if "Comedy & Dramedy" in themes or "comedy" in genres:
        tags.append("Comedy")
    if "drama" in genres and ("Comedy & Dramedy" in themes or "comedy" in genres):
        tags.append("Dramedy")
    if item["award_years"]:
        tags.append("Award Winner")
    if "romance" in genres:
        tags.append("Romance")
    if movie.get("runtime") and movie["runtime"] <= 90:
        tags.append("Short-ish")
    if movie.get("year") and movie["year"] >= 2023:
        tags.append("Recent")
    return tags


def watch_score(movie, item, tags):
    rating = movie.get("rating") or 0
    votes = movie.get("votes") or 0
    score = rating * 10
    if votes >= 10000:
        score += 10
    elif votes >= 2500:
        score += 6
    elif votes >= 500:
        score += 3
    score += min(len(item["lists"]) * 4, 12)
    if item["award_years"]:
        score += 8
    if movie.get("year") and movie["year"] >= 2023:
        score += 2
    return round(score, 1)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    items = read_sources()
    movies = []
    misses = []

    for index, item in enumerate(items, start=1):
        try:
            if item["trakt_id"]:
                movie = get_movie_by_id(item["trakt_id"])
            else:
                movie = get_movie_by_slug(item["input_title"], item["input_year"])
                if not movie:
                    movie = search_movie(item["input_title"], item["input_year"])
        except Exception as exc:
            misses.append({**item, "error": str(exc)})
            continue

        if not movie:
            misses.append(item)
            continue
        if not item["trakt_id"] and not plausible_match(item["input_title"], movie):
            misses.append(
                {
                    **item,
                    "matched_title": movie.get("title"),
                    "matched_year": movie.get("year"),
                    "reason": "low_title_similarity",
                }
            )
            continue

        tags = classify(movie, item)
        ids = movie.get("ids") or {}
        imdb_id = ids.get("imdb")
        movies.append(
            {
                "title": movie.get("title") or item["input_title"],
                "input_title": item["input_title"],
                "input_year": item["input_year"],
                "year": movie.get("year") or item["input_year"],
                "overview": movie.get("overview") or "",
                "runtime": movie.get("runtime"),
                "rating": round(movie.get("rating") or 0, 1),
                "votes": movie.get("votes") or 0,
                "genres": movie.get("genres") or [],
                "language": movie.get("language"),
                "country": movie.get("country"),
                "certification": movie.get("certification"),
                "trakt": ids.get("trakt"),
                "slug": ids.get("slug"),
                "imdb": imdb_id,
                "tmdb": ids.get("tmdb"),
                "poster": f"https://images.metahub.space/poster/medium/{imdb_id}/img" if imdb_id else None,
                "poster_small": f"https://images.metahub.space/poster/small/{imdb_id}/img" if imdb_id else None,
                "background": f"https://images.metahub.space/background/medium/{imdb_id}/img" if imdb_id else None,
                "lists": sorted(item["lists"]),
                "themes": sorted(item["themes"]),
                "award_years": sorted(item["award_years"]),
                "tags": tags,
                "watch_score": watch_score(movie, item, tags),
            }
        )
        if index % 25 == 0:
            print(f"Enriquecidos {index}/{len(items)}...")
        time.sleep(0.12)

    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sources": SOURCES,
        "movies": sorted(movies, key=lambda movie: (-movie["watch_score"], movie["title"])),
        "misses": misses,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Gerado {OUTPUT} com {len(movies)} filmes e {len(misses)} pendencia(s).")


if __name__ == "__main__":
    main()
