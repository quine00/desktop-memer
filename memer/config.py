"""Config loading for desktop-memer."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".config" / "desktop-memer" / "config.toml"
PROJECT_CONFIG = Path(__file__).resolve().parent.parent / "config.toml"


@dataclass
class Person:
    name: str
    github: str | None = None
    launchpad: str | None = None
    jira: str | None = None
    gitlab: dict[str, str] = field(default_factory=dict)  # instance -> username


@dataclass
class Config:
    summary_model: str
    image_model: str
    openrouter_api_key: str
    github_token: str | None
    jira_base_url: str | None
    jira_email: str | None
    jira_api_token: str | None
    mattermost_url: str | None
    mattermost_token: str | None
    mattermost_target: str
    gitlab_tokens: dict[str, str]
    people: list[Person]


def load(path: str | os.PathLike | None = None) -> Config:
    p = Path(path) if path else (PROJECT_CONFIG if PROJECT_CONFIG.exists() else DEFAULT_CONFIG)
    with open(p, "rb") as f:
        raw = tomllib.load(f)

    creds = raw.get("credentials", {})

    def secret(toml_key: str, env: str) -> str | None:
        """Environment wins over TOML so a checked-out tree needs no keys."""
        return os.environ.get(env) or creds.get(toml_key)

    people = [
        Person(
            name=pp["name"],
            github=pp.get("github"),
            launchpad=(pp.get("launchpad") or "").lstrip("~") or None,
            jira=pp.get("jira"),
            gitlab=pp.get("gitlab", {}),
        )
        for pp in raw.get("person", [])
    ]
    return Config(
        summary_model=raw["models"]["summary"],
        image_model=raw["models"]["image"],
        openrouter_api_key=secret("openrouter_api_key", "MEMER_OPENROUTER_API_KEY"),
        github_token=secret("github_token", "MEMER_GITHUB_TOKEN"),
        jira_base_url=(os.environ.get("MEMER_JIRA_BASE_URL") or creds.get("jira_base_url") or "").rstrip("/") or None,
        jira_email=os.environ.get("MEMER_JIRA_EMAIL") or creds.get("jira_email"),
        jira_api_token=secret("jira_api_token", "MEMER_JIRA_API_TOKEN"),
        mattermost_url=(os.environ.get("MEMER_MATTERMOST_URL") or creds.get("mattermost_url") or "").rstrip("/") or None,
        mattermost_token=secret("mattermost_token", "MEMER_MATTERMOST_TOKEN"),
        mattermost_target=creds.get("mattermost_target", "self"),
        gitlab_tokens=creds.get("gitlab", {}),
        people=people,
    )
