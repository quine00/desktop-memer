"""Mattermost posting: self-DM or named channel, PNG upload + headline table."""
from __future__ import annotations

from pathlib import Path

import httpx

from .collectors import Row
from .config import Config


def _client(cfg: Config) -> httpx.Client:
    if not (cfg.mattermost_url and cfg.mattermost_token):
        raise RuntimeError("mattermost_url/token not configured")
    return httpx.Client(
        base_url=f"{cfg.mattermost_url}/api/v4",
        headers={"Authorization": f"Bearer {cfg.mattermost_token}"},
        timeout=60,
    )


def _channel_id(c: httpx.Client, cfg: Config) -> str:
    me = c.get("/users/me").json()
    if cfg.mattermost_target == "self":
        ch = c.post("/channels/direct", json=[me["id"], me["id"]]).json()
        return ch["id"]
    # named channel: target must be "teamname/channelname"
    team, channel = cfg.mattermost_target.split("/", 1)
    ch = c.get(f"/teams/name/{team}/channels/name/{channel}").json()
    return ch["id"]


def post(cfg: Config, image: Path, rows: list[Row], caption: str = "") -> str:
    with _client(cfg) as c:
        channel_id = _channel_id(c, cfg)

        table = "\n".join(
            f"| {r['person']} | {r['source']} | {r['kind']} | [{r['headline'][:80]}]({r['url']}) |"
            for r in rows
        )
        message = (caption + "\n\n" if caption else "") + (
            "| who | where | what | headline |\n|---|---|---|---|\n" + table if table else ""
        )

        with open(image, "rb") as f:
            up = c.post(
                "/files",
                params={"channel_id": channel_id},
                files={"files": (image.name, f, "image/png")},
            ).json()
        file_ids = [fi["id"] for fi in up.get("file_infos", [])]

        p = c.post("/posts", json={"channel_id": channel_id, "message": message, "file_ids": file_ids})
        p.raise_for_status()
        return p.json()["id"]
