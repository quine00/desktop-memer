"""Collectors return rows: {person, source, kind, headline, url, date}.

kind is one of: pr, mr, issue, bug, comment, commit, jira.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

Row = dict


def window(days: int) -> tuple[datetime, str, str]:
    """Return (since_datetime, iso8601, yyyy-mm-dd) for `days` back from now."""
    since = datetime.now(UTC) - timedelta(days=days)
    return since, since.isoformat(), since.strftime("%Y-%m-%d")


from . import github, gitlab, jira, launchpad  # noqa: F401
