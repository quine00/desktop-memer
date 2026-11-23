from __future__ import annotations

from typing import ClassVar
from unittest.mock import patch

from memer.collectors import github
from memer.config import Config, Person


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeClient:
    queries: ClassVar[list[str]] = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url, params=None):
        assert url == "https://api.github.com/search/issues"
        q = params["q"]
        FakeClient.queries.append(q)
        if "author:quine00 is:pr updated:>=" in q:
            return Response({
                "items": [
                    {
                        "title": "tools: Fix NULL session bus in ibus start",
                        "html_url": "https://github.com/ibus/ibus/pull/2984",
                        "user": {"login": "quine00"},
                        "created_at": "2026-11-01T10:00:00Z",
                        "updated_at": "2026-11-20T15:24:06Z",
                        "pull_request": {"merged_at": "2026-11-20T15:24:06Z"},
                    },
                    {
                        "title": "bus/ibusimpl: Keep static global engine when a component exits",
                        "html_url": "https://github.com/ibus/ibus/pull/2973",
                        "user": {"login": "quine00"},
                        "created_at": "2026-10-28T09:00:00Z",
                        "updated_at": "2026-11-18T16:07:07Z",
                        "pull_request": {"merged_at": None},
                    },
                ]
            })
        if "commenter:quine00 is:pr updated:>=" in q:
            return Response({
                "items": [
                    {
                        "title": "tools: Fix NULL session bus in ibus start",
                        "html_url": "https://github.com/ibus/ibus/pull/2984",
                        "user": {"login": "quine00"},
                        "created_at": "2026-11-01T10:00:00Z",
                        "updated_at": "2026-11-20T15:24:06Z",
                    },
                    {
                        "title": "Other person's PR",
                        "html_url": "https://github.com/ibus/ibus/pull/2999",
                        "user": {"login": "someone-else"},
                        "created_at": "2026-10-01T00:00:00Z",
                        "updated_at": "2026-11-21T12:00:00Z",
                    },
                ]
            })
        return Response({"items": []})


def config_and_person():
    cfg = Config(
        summary_model="summary",
        image_model="image",
        openrouter_api_key="",
        github_token="ghp_test",
        jira_base_url=None,
        jira_email=None,
        jira_api_token=None,
        mattermost_url=None,
        mattermost_token=None,
        mattermost_target="self",
        gitlab_tokens={},
        people=[],
    )
    return cfg, Person(name="Charles", github="quine00")


def test_github_collects_merged_and_updated_prs_with_activity_dates():
    FakeClient.queries.clear()
    cfg, person = config_and_person()
    with patch.object(github.httpx, "Client", FakeClient):
        rows = github.collect(cfg, person, 5)

    assert any("author:quine00 is:pr updated:>=" in q for q in FakeClient.queries)
    by_url = {(r["url"], r["kind"]): r for r in rows}
    assert by_url[("https://github.com/ibus/ibus/pull/2984", "pr")]["date"] == "2026-11-20T15:24:06Z"
    assert by_url[("https://github.com/ibus/ibus/pull/2973", "pr")]["date"] == "2026-11-18T16:07:07Z"
    assert ("https://github.com/ibus/ibus/pull/2984", "comment") not in by_url
    assert by_url[("https://github.com/ibus/ibus/pull/2999", "comment")]["date"] == "2026-11-21T12:00:00Z"
