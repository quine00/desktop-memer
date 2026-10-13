"""Per-person activity report over N weeks. Deterministic, no LLM."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .collectors import Row
from .rank import rank


def render(rows: list[Row], people: list[str], weeks: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# desktop-memer report ({weeks}w, generated {now})", ""]
    by_person: dict[str, list[Row]] = {p: [] for p in people}
    for r in rows:
        by_person.setdefault(r["person"], []).append(r)

    for person, prs in by_person.items():
        lines.append(f"## {person}")
        if not prs:
            lines.append("\n_No activity found._\n")
            continue
        counts = Counter((r["source"], r["kind"]) for r in prs)
        lines.append("")
        lines.append("| source | kind | count |")
        lines.append("|---|---|---|")
        for (src, kind), n in sorted(counts.items()):
            lines.append(f"| {src} | {kind} | {n} |")
        lines.append("")
        for r in rank(prs):
            date = r["date"][:10]
            lines.append(f"- {date} [{r['kind']}] [{r['headline']}]({r['url']})")
        lines.append("")
    return "\n".join(lines)
