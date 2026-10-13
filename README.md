# desktop-memer

Scrapes a team's open-source activity (GitHub, GitLab, Launchpad, Jira),
turns the week's highlights into a vintage-comic-cover meme via OpenRouter,
and posts it to Mattermost.

## Install

```sh
uv venv && uv pip install -e .
```

## Configure

Copy `config.toml.example` to `config.toml` (gitignored) and fill in
credentials, or export them as environment variables:

| TOML key (`[credentials]`) | Env var |
|---|---|
| `openrouter_api_key` | `MEMER_OPENROUTER_API_KEY` |
| `github_token` | `MEMER_GITHUB_TOKEN` |
| `jira_api_token` | `MEMER_JIRA_API_TOKEN` |
| `jira_base_url` | `MEMER_JIRA_BASE_URL` |
| `jira_email` | `MEMER_JIRA_EMAIL` |
| `mattermost_url` | `MEMER_MATTERMOST_URL` |
| `mattermost_token` | `MEMER_MATTERMOST_TOKEN` |

Per-instance GitLab tokens live in `[credentials.gitlab]`, keyed by hostname.
Launchpad uses the OAuth1 credentials file `~/.lp_creds` (launchpadlib).

One `[[person]]` block per human; sources that are absent are skipped.
Models (summariser + image) are pinned under `[models]`.

## Usage

```sh
uv run memer collect --days 7      # JSON activity rows to stdout (no LLM)
uv run memer report  --weeks 2     # per-person markdown report -> out/report.md
uv run memer meme    --days 7      # prompt + image -> out/meme.png (OpenRouter)
uv run memer post    --days 7      # post an existing out/meme.png to Mattermost
uv run memer run     --days 7      # the whole pipeline, posted to your self-DM
```

`--per-person N` caps how many highlight items per person feed the model
(default 5).

The Mattermost post contains the image, a witty per-person digest, the
OpenRouter cost of the run, and the raw headline table.

## Design notes

- Deterministic core: all LLM calls live in `memer/meme.py` behind two
  pinned models; everything else is plain API scraping and sorting.
- Selection: `rank.py` picks each person's top-N items weighted by kind
  (MR/PR > issue/bug > jira > comment).
- Launchpad has a circuit breaker: LP is flaky, so one failure skips the
  source for the rest of the run rather than retrying for every person.
- Cost: run cost is read from OpenRouter's usage accounting and printed in
  the post.
