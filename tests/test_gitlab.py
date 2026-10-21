from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from memer.collectors import gitlab
from memer.config import Config, Person


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.event_date = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, params=None):
        if url.endswith("/issues") or url.endswith("/merge_requests"):
            # Item creation results duplicate the matching GitLab event.
            return Response([{
                "title": "An older item",
                "web_url": "https://gitlab.example/group/project/-/merge_requests/12",
                "created_at": self.event_date,
            }] if url.endswith("/merge_requests") else [])
        if url.endswith("/users"):
            return Response([{"id": 7}])
        if url.endswith("/users/7/events"):
            return Response([
                {
                    "project_id": 99,
                    "action_name": "pushed new",
                    "created_at": self.event_date,
                    "push_data": {
                        "commit_count": 5,
                        "ref": "work/fix",
                        "commit_to": "abc123",
                        "commit_title": "Fix stale input context",
                    },
                },
                {
                    "project_id": 99,
                    "action_name": "pushed to",
                    "created_at": self.event_date,
                    "push_data": {
                        "commit_count": 1,
                        "ref": "main",
                        "commit_to": "def456",
                        "commit_title": "Follow-up fix",
                    },
                },
                {
                    "project_id": 99,
                    "action_name": "commented on",
                    "target_id": 2900843,
                    "target_title": "Existing GTK merge request",
                    "created_at": self.event_date,
                    "note": {
                        "noteable_type": "MergeRequest",
                        "noteable_iid": 12,
                        "created_at": self.event_date,
                        "body": "I tested the follow-up commits.",
                    },
                },
                {"project_id": 99, "action_name": "joined", "created_at": self.event_date},
            ])
        if url.endswith("/projects/99"):
            return Response({"web_url": "https://gitlab.example/group/project"})
        raise AssertionError(f"Unexpected URL: {url}")


def config_and_person():
    cfg = Config(
        summary_model="summary",
        image_model="image",
        openrouter_api_key="",
        github_token=None,
        jira_base_url=None,
        jira_email=None,
        jira_api_token=None,
        mattermost_url=None,
        mattermost_token=None,
        mattermost_target="self",
        gitlab_tokens={"gitlab.example": "token"},
        people=[],
    )
    return cfg, Person(name="Charles", gitlab={"gitlab.example": "charles"})


def test_gitlab_activity_includes_pushes_and_existing_mr_comments():
    cfg, person = config_and_person()
    with patch.object(gitlab.httpx, "Client", FakeClient):
        rows = gitlab.collect(cfg, person, 5)

    assert {row["kind"] for row in rows} == {"mr", "commit", "comment"}
    commits = {row["url"]: row["headline"] for row in rows if row["kind"] == "commit"}
    assert commits == {
        "https://gitlab.example/group/project/-/commit/abc123": "Pushed to work/fix: Fix stale input context",
        "https://gitlab.example/group/project/-/commit/def456": "Pushed to main: Follow-up fix",
    }
    comment = next(row for row in rows if row["kind"] == "comment")
    assert "I tested the follow-up commits." in comment["headline"]
    assert comment["url"].endswith("/-/merge_requests/12#note_2900843")
    # The event and authored-item endpoints identify the same MR; keep one row.
    assert sum("/-/merge_requests/12" in row["url"] for row in rows) == 2


def test_gitlab_event_converter_ignores_non_contribution_events():
    assert gitlab._event_row(
        {"action_name": "joined", "project_id": 99, "created_at": "2026-10-16T12:00:00Z"},
        "Charles",
        "gitlab.example",
        "https://gitlab.example/group/project",
    ) is None
