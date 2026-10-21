"""GitLab activity, per configured instance."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from ..config import Config, Person
from . import Row, window


def collect(cfg: Config, person: Person, days: int) -> list[Row]:
    rows: list[Row] = []
    since, since_iso, since_date = window(days)
    until = datetime.now(timezone.utc)
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

            # The issues/MRs endpoints above only find items authored during
            # the window. User events also capture pushes to existing branches
            # and comments on existing discussions.
            user_response = c.get(f"{base}/users", params={"username": username})
            user_response.raise_for_status()
            users = user_response.json()
            if not users:
                continue
            user_id = users[0]["id"]

            page = 1
            project_urls: dict[int, str] = {}
            while True:
                events_response = c.get(
                    f"{base}/users/{user_id}/events",
                    params={
                        "after": since_date,
                        "before": (until.date() + timedelta(days=1)).isoformat(),
                        "per_page": 100,
                        "page": page,
                    },
                )
                events_response.raise_for_status()
                events = events_response.json()
                for event in events:
                    project_id = event.get("project_id")
                    if project_id is None:
                        continue
                    if project_id not in project_urls:
                        project_response = c.get(f"{base}/projects/{project_id}")
                        project_response.raise_for_status()
                        project_urls[project_id] = project_response.json()["web_url"].rstrip("/")
                    row = _event_row(event, person.name, instance, project_urls[project_id])
                    if row:
                        event_date = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
                        if since <= event_date <= until:
                            rows.append(row)
                if len(events) < 100:
                    break
                page += 1

    # An item created in this window can also generate a GitLab event. Remove
    # exact duplicate rows without collapsing multiple comments on one item.
    unique: dict[tuple[str, str], Row] = {}
    for row in rows:
        unique.setdefault((row["kind"], row["url"] + row["date"]), row)
    return list(unique.values())


def _event_row(event: dict, person: str, instance: str, project_url: str) -> Row | None:
    """Convert meaningful authored GitLab events into report rows."""
    action = event.get("action_name")
    date = event.get("created_at")
    # "pushed new" creates a branch; "pushed to" extends an existing one.
    if action in {"pushed new", "pushed to"}:
        push = event.get("push_data", {})
        sha = push.get("commit_to")
        if not sha:
            return None
        branch = push.get("ref", "branch")
        latest_title = push.get("commit_title") or ""
        headline = f"Pushed to {branch}"
        if latest_title:
            headline += f": {latest_title}"
        url = f"{project_url}/-/commit/{sha}"
        kind = "commit"
    elif action == "commented on":
        note = event.get("note", {})
        noteable_type = note.get("noteable_type")
        iid = note.get("noteable_iid")
        if not iid or noteable_type not in {"Issue", "MergeRequest"}:
            return None
        target = "issues" if noteable_type == "Issue" else "merge_requests"
        title = event.get("target_title", "discussion")
        body = " ".join(note.get("body", "").split())
        excerpt = body[:180] + ("…" if len(body) > 180 else "")
        headline = f"Commented on {title}"
        if excerpt:
            headline += f": {excerpt}"
        note_id = event.get("target_id")
        anchor = f"#note_{note_id}" if note_id else ""
        url = f"{project_url}/-/{target}/{iid}{anchor}"
        kind = "comment"
        date = note.get("created_at", date)
    else:
        return None

    return {
        "person": person,
        "source": f"gitlab:{instance}",
        "kind": kind,
        "headline": headline,
        "url": url,
        "date": date,
    }
