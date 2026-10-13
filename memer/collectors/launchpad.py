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
    seen = set()

    # Bugs reported by the person.
    # Note: bug_commenter search OOPS-times-out on LP (too expensive), so
    # comment activity is not collected here.
    # Launchpad intermittently 503s expensive searches (Retry-After); retry.
    # On final failure, trip the circuit breaker for the rest of this run.
    tasks = None
    for attempt in range(3):
        try:
            tasks = lp.bugs.searchTasks(bug_reporter=lp_person, created_since=since_dt.isoformat())
            break
        except Exception:
            if attempt == 2:
                _LP_DEAD = True
                raise
            time.sleep(5 * (2 ** attempt))
    for t in tasks:
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
    return rows
