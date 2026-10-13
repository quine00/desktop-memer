"""Jira (Atlassian Cloud) activity via JQL search."""
from __future__ import annotations

import httpx

from ..config import Config, Person
from . import Row


def collect(cfg: Config, person: Person, days: int) -> list[Row]:
    if not person.jira or not (cfg.jira_base_url and cfg.jira_email and cfg.jira_api_token):
        return []
    auth = (cfg.jira_email, cfg.jira_api_token)
    rows: list[Row] = []
    jqls = [
        # (jql, date field): reporter rows are dated by creation, assignee rows
        # by last update, so old-but-active tickets sort by recent activity.
        (f'reporter = "{person.jira}" AND created >= -{days}d ORDER BY created DESC', "created"),
        (f'assignee = "{person.jira}" AND updated >= -{days}d ORDER BY updated DESC', "updated"),
    ]
    seen = set()
    with httpx.Client(auth=auth, timeout=30) as c:
        for jql, date_field in jqls:
            r = c.post(
                f"{cfg.jira_base_url}/rest/api/3/search/jql",
                json={"jql": jql, "maxResults": 50, "fields": ["summary", "created", "updated"]},
            )
            r.raise_for_status()
            for issue in r.json().get("issues", []):
                key = issue["key"]
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "person": person.name,
                    "source": "jira",
                    "kind": "jira",
                    "headline": f"{key}: {issue['fields']['summary']}",
                    "url": f"{cfg.jira_base_url}/browse/{key}",
                    "date": issue["fields"][date_field],
                })
    return rows
