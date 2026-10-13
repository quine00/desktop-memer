"""GitHub activity via the search API."""
from __future__ import annotations

import httpx

from ..config import Config, Person
from . import Row, window

API = "https://api.github.com"


def collect(cfg: Config, person: Person, days: int) -> list[Row]:
    if not person.github or not cfg.github_token:
        return []
    _, _, since_date = window(days)
    h = {"Authorization": f"token {cfg.github_token}", "Accept": "application/vnd.github+json"}
    rows: list[Row] = []
    with httpx.Client(headers=h, timeout=30) as c:
        queries = [
            (f"author:{person.github} is:pr created:>={since_date}", "pr"),
            (f"author:{person.github} is:issue created:>={since_date}", "issue"),
            (f"commenter:{person.github} is:issue updated:>={since_date}", "comment"),
            (f"commenter:{person.github} is:pr updated:>={since_date}", "comment"),
        ]
        seen = set()
        for q, kind in queries:
            r = c.get(f"{API}/search/issues", params={"q": q, "per_page": 50})
            r.raise_for_status()
            for item in r.json().get("items", []):
                url = item["html_url"]
                key = (url, kind)
                if key in seen:
                    continue
                seen.add(key)
                # comments: only count if person is not the author (else dup)
                if kind == "comment" and item["user"]["login"].lower() == person.github.lower():
                    continue
                rows.append({
                    "person": person.name,
                    "source": "github",
                    "kind": kind,
                    "headline": item["title"],
                    "url": url,
                    "date": item["created_at"],
                })
    return rows
