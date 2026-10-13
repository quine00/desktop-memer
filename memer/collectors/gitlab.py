"""GitLab activity, per configured instance."""
from __future__ import annotations

import httpx

from ..config import Config, Person
from . import Row, window


def collect(cfg: Config, person: Person, days: int) -> list[Row]:
    rows: list[Row] = []
    _, since_iso, _ = window(days)
    for instance, token in cfg.gitlab_tokens.items():
        username = person.gitlab.get(instance)
        if not username:
            continue
        base = f"https://{instance}/api/v4"
        with httpx.Client(headers={"PRIVATE-TOKEN": token}, timeout=30) as c:
            for path, kind in (("issues", "issue"), ("merge_requests", "mr")):
                r = c.get(
                    f"{base}/{path}",
                    params={
                        "author_username": username,
                        "created_after": since_iso,
                        "scope": "all",
                        "per_page": 100,
                    },
                )
                r.raise_for_status()
                for item in r.json():
                    rows.append({
                        "person": person.name,
                        "source": f"gitlab:{instance}",
                        "kind": kind,
                        "headline": item["title"],
                        "url": item["web_url"],
                        "date": item["created_at"],
                    })
    return rows
