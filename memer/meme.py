"""OpenRouter: headlines -> meme prompt -> PNG. All model calls live here, not in the agent."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .collectors import Row
from .config import Config

API = "https://openrouter.ai/api/v1/chat/completions"

SUMMARY_SYSTEM = (
    "You write image-generation prompts and weekly team-meme digests. "
    "Given engineering activity headlines grouped by person, output ONLY a JSON "
    "object (no markdown fences) with exactly these keys:\n"
    '- "image_prompt": ONE absurd, funny, self-contained image prompt. It must '
    "start with \"Vintage comic cover:\". Anthropomorphise where apt; exaggerated "
    "golden-age comic composition, bold inks, halftone dots, dramatic poses. "
    "Weave the input headlines into the scene, clustering related ones into a "
    "single element where natural; at most 8 distinct scene elements so the "
    "composition stays readable, and no single headline may dominate - it is "
    "an ensemble piece about the whole team's week, not a portrait of one "
    "ticket. No text in the image.\n"
    '- "people": an object mapping each person\'s name to one witty sentence '
    "summarising their week from their headlines."
)


@dataclass
class Summary:
    image_prompt: str
    people: dict[str, str]
    cost: float = 0.0


@dataclass
class ImageResult:
    path: Path
    cost: float = 0.0


def _post(cfg: Config, payload: dict) -> tuple[dict, float]:
    payload = dict(payload, usage={"include": True})
    r = httpx.post(
        API,
        headers={"Authorization": f"Bearer {cfg.openrouter_api_key}"},
        json=payload,
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    cost = float((data.get("usage") or {}).get("cost") or 0.0)
    return data, cost


def summarise(cfg: Config, rows: list[Row]) -> Summary:
    by_person: dict[str, list[str]] = {}
    for r in rows:
        by_person.setdefault(r["person"], []).append(f"[{r['kind']}] {r['headline']}")
    bullets = "\n".join(
        f"{name}:\n" + "\n".join(f"  - {h}" for h in heads)
        for name, heads in by_person.items()
    ) or "(no activity this week)"
    data, cost = _post(cfg, {
        "model": cfg.summary_model,
        "messages": [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": f"This week's activity:\n{bullets}"},
        ],
    })
    text = data["choices"][0]["message"]["content"].strip()
    # tolerate accidental markdown fences
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    parsed = json.loads(text)
    return Summary(
        image_prompt=parsed["image_prompt"].strip(),
        people=parsed.get("people", {}),
        cost=cost,
    )


def generate_image(cfg: Config, prompt: str, out_path: Path) -> ImageResult:
    data, cost = _post(cfg, {
        "model": cfg.image_model,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    })
    images = data["choices"][0]["message"].get("images") or []
    if not images:
        raise RuntimeError(f"image model returned no images: {data}")
    url = images[0]["image_url"]["url"]
    if url.startswith("data:"):
        out_path.write_bytes(base64.b64decode(url.split(",", 1)[1]))
    else:
        resp = httpx.get(url, timeout=120)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
    return ImageResult(path=out_path, cost=cost)
