from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import patch

from memer.collectors import launchpad
from memer.config import Person

ME = "https://api.launchpad.net/devel/~charles"
OTHER = "https://api.launchpad.net/devel/~someone"


def fake_lp():
    now = datetime.now(UTC)
    old, new = now - timedelta(days=30), now - timedelta(hours=1)
    commented = NS(id=42, title="Playback hangs", date_created=old, messages=[
        NS(owner_link=ME, date_created=old, content="Description, written by me long ago"),
        NS(owner_link=ME, date_created=old, content="An old comment"),
        NS(owner_link=OTHER, date_created=new, content="Someone else's comment"),
        NS(owner_link=ME, date_created=new, content="Tested   the\nfix."),
    ])
    reported = NS(id=7, title="New crash", date_created=new, messages=[])

    def search_tasks(**params):
        if "bug_reporter" in params:
            return [NS(bug=reported)]
        assert params["status"] == launchpad.ALL_STATUSES
        # Two tasks (series targets) of one bug must yield its comments once.
        return [NS(bug=commented), NS(bug=commented)]

    return NS(people={"charles": NS(self_link=ME)}, bugs=NS(searchTasks=search_tasks))


def test_launchpad_collects_reported_bugs_and_comments_in_window():
    person = Person(name="Charles", launchpad="charles")
    with (
        patch.object(launchpad, "_lp", fake_lp),
        patch.object(launchpad.os.path, "exists", return_value=True),
    ):
        rows = launchpad.collect(None, person, 3)

    assert [(r["kind"], r["url"]) for r in rows] == [
        ("bug", "https://bugs.launchpad.net/bugs/7"),
        ("comment", "https://bugs.launchpad.net/bugs/42/comments/3"),
    ]
    assert rows[1]["headline"] == "Commented on LP#42: Playback hangs: Tested the fix."
