"""Launchpad bugs via launchpadlib, using OAuth1 creds from ~/.lp_creds."""
from __future__ import annotations

import os
import time

from ..config import Config, Person
from . import Row, window

CREDS_FILE = os.path.expanduser("~/.lp_creds")

# Circuit breaker: when LP is down, one person's failure shouldn't multiply
# into retry storms across every remaining person in the same run.
_LP_DEAD = False


_LP_CLIENT = None

ALL_STATUSES = [
    "New", "Incomplete", "Opinion", "Invalid", "Won't Fix", "Expired", "Confirmed",
    "Triaged", "In Progress", "Fix Committed", "Fix Released", "Does Not Exist",
]


def _lp():
    global _LP_CLIENT
    if _LP_CLIENT is None:
        from launchpadlib.launchpad import Launchpad

        _LP_CLIENT = Launchpad.login_with("desktop-memer", "production", credentials_file=CREDS_FILE)
    return _LP_CLIENT


def collect(cfg: Config, person: Person, days: int) -> list[Row]:
    global _LP_DEAD
    if not person.launchpad or not os.path.exists(CREDS_FILE) or _LP_DEAD:
        return []
    since_dt, _, _ = window(days)
    try:
        lp = _lp()
        lp_person = lp.people[person.launchpad]
    except Exception:
        _LP_DEAD = True
        raise
    rows: list[Row] = []

    # Bugs reported by the person.
    seen = set()
    for t in _search(lp, bug_reporter=lp_person, created_since=since_dt.isoformat()):
        bug_id = t.bug.id
        if bug_id in seen:
            continue
        seen.add(bug_id)
        rows.append({
            "person": person.name,
            "source": "launchpad",
            "kind": "bug",
            "headline": f"LP#{bug_id}: {t.bug.title}",
            "url": f"https://bugs.launchpad.net/bugs/{bug_id}",
            "date": str(t.bug.date_created),
        })

    # Comments: any bug the person commented on that changed in the window,
    # then only their messages posted in the window. All statuses, so
    # comments on closed bugs count too.
    seen = set()
    tasks = _search(
        lp, bug_commenter=lp_person, modified_since=since_dt.isoformat(), status=ALL_STATUSES,
    )
    for t in tasks:
        bug = t.bug
        if bug.id in seen:
            continue
        seen.add(bug.id)
        # Message 0 is the bug description; LP numbers comments from there.
        for n, m in enumerate(bug.messages):
            if n == 0 or m.owner_link != lp_person.self_link or m.date_created < since_dt:
                continue
            body = " ".join((m.content or "").split())
            excerpt = body[:180] + ("…" if len(body) > 180 else "")
            headline = f"Commented on LP#{bug.id}: {bug.title}"
            if excerpt:
                headline += f": {excerpt}"
            rows.append({
                "person": person.name,
                "source": "launchpad",
                "kind": "comment",
                "headline": headline,
                "url": f"https://bugs.launchpad.net/bugs/{bug.id}/comments/{n}",
                "date": str(m.date_created),
            })
    return rows


def _search(lp, **params):
    """lp.bugs.searchTasks with retries; trips the circuit breaker on final failure.

    Launchpad intermittently 503s or times out expensive searches (Retry-After).
    """
    global _LP_DEAD
    for attempt in range(3):
        try:
            return lp.bugs.searchTasks(**params)
        except Exception:
            if attempt == 2:
                _LP_DEAD = True
                raise
            time.sleep(5 * (2 ** attempt))
    return None
