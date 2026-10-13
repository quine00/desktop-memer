"""desktop-memer CLI.

Usage:
  memer collect [--days 7]            -> JSON rows to stdout
  memer meme [--days 7] [--top 8]     -> writes out/meme.png, prints prompt
  memer run  [--days 7]               -> collect + meme + post to Mattermost
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import collectors, meme, rank as rank_mod
from .config import load

OUT = Path(__file__).resolve().parent.parent / "out"

COLLECTORS = [collectors.github, collectors.gitlab, collectors.jira, collectors.launchpad]


def collect_all(days: int) -> list[dict]:
    cfg = load()
    rows: list[dict] = []
    for person in cfg.people:
        for col in COLLECTORS:
            try:
                rows.extend(col.collect(cfg, person, days))
            except Exception as e:  # keep other sources alive
                print(f"warn: {col.__name__} failed for {person.name}: {e}", file=sys.stderr)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(prog="memer")
    ap.add_argument("cmd", choices=["collect", "meme", "post", "run", "report"])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--weeks", type=int, default=1)
    ap.add_argument("--per-person", type=int, default=5,
                    help="max highlight items per person fed to the model")
    ap.add_argument("--image", type=Path, default=None, help="existing png for 'post'")
    args = ap.parse_args()

    if args.cmd == "collect":
        print(json.dumps(rank_mod.rank(collect_all(args.days)), indent=2))
        return

    if args.cmd == "report":
        from . import report as report_mod
        cfg = load()
        rows = collect_all(args.weeks * 7)
        md = report_mod.render(rows, [p.name for p in cfg.people], args.weeks)
        OUT.mkdir(exist_ok=True)
        path = OUT / "report.md"
        path.write_text(md)
        print(path)
        return

    cfg = load()
    rows = rank_mod.per_person(collect_all(args.days), n=args.per_person)

    if args.cmd == "meme":
        summary = meme.summarise(cfg, rows)
        print(f"prompt: {summary.image_prompt}", file=sys.stderr)
        OUT.mkdir(exist_ok=True)
        img = meme.generate_image(cfg, summary.image_prompt, OUT / "meme.png")
        print(f"{img.path} (cost ${summary.cost + img.cost:.4f})")
        return

    if args.cmd == "post":
        image = args.image or (OUT / "meme.png")
        from . import mattermost
        post_id = mattermost.post(cfg, image, rows)
        print(f"posted: {post_id}")
        return

    # run
    summary = meme.summarise(cfg, rows)
    print(f"prompt: {summary.image_prompt}", file=sys.stderr)
    OUT.mkdir(exist_ok=True)
    img = meme.generate_image(cfg, summary.image_prompt, OUT / "meme.png")
    from . import mattermost
    post_id = mattermost.post(cfg, img.path, rows, caption=_caption(summary, img.cost))
    print(f"posted: {post_id}")


def _caption(summary: "meme.Summary", image_cost: float) -> str:
    people = "\n".join(f"- **{name}**: {line}" for name, line in summary.people.items())
    total = summary.cost + image_cost
    return (
        f"{summary.image_prompt}\n\n"
        f"{people}\n\n"
        f"_run cost: ${total:.4f} (summary ${summary.cost:.4f}, image ${image_cost:.4f})_"
    )


if __name__ == "__main__":
    main()
