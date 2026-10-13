"""Deterministic ranking: most meme-worthy rows first."""
from __future__ import annotations

from .collectors import Row

KIND_WEIGHT = {"mr": 5, "pr": 5, "issue": 3, "bug": 3, "jira": 2, "comment": 1}


def rank(rows: list[Row], top: int | None = None) -> list[Row]:
    out = sorted(rows, key=lambda r: (KIND_WEIGHT.get(r["kind"], 0), r["date"]), reverse=True)
    return out[:top] if top else out


def per_person(rows: list[Row], n: int = 5) -> list[Row]:
    """Up to n highlight items per person, ranked by kind weight then date.
    Person blocks follow the global ranking of their best item."""
    ranked = rank(rows)
    counts: dict[str, int] = {}
    out: list[Row] = []
    for r in ranked:
        person = r["person"]
        if counts.get(person, 0) < n:
            out.append(r)
            counts[person] = counts.get(person, 0) + 1
    return out


def diverse(rows: list[Row], top: int) -> list[Row]:
    """Two-phase fair selection for the meme prompt.

    Pass 1: every person with activity gets exactly one slot (their best
    row). Pass 2: remaining slots are filled round-robin across
    (person, source) buckets so no noisy source dominates.
    """
    ranked = rank(rows)

    out: list[Row] = []
    seen_people: set[str] = set()
    for r in ranked:
        if r["person"] not in seen_people:
            out.append(r)
            seen_people.add(r["person"])
            if len(out) >= top:
                return out

    taken = {id(r) for r in out}
    buckets: dict[tuple[str, str], list[Row]] = {}
    for r in ranked:
        if id(r) not in taken:
            buckets.setdefault((r["person"], r["source"]), []).append(r)
    while len(out) < top and buckets:
        for key in list(buckets):
            if buckets[key]:
                out.append(buckets[key].pop(0))
                if len(out) >= top:
                    break
            else:
                del buckets[key]
    return out
