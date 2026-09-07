# swarm-index-watch

Index-first anomaly watcher for swarm-style coordination surfaces (wikis, pastebins, gem registries, anywhere agents leave structured exhaust).

**Philosophy:** don't scrape content, scrape indexes. Metadata is cheap. Content gets pulled only when metadata moves *and* scores.

## How it works

Three fetch tiers:

| Tier | What | When |
|---|---|---|
| 0 | Index scan (recentchanges API / list-page diff) | every tick, always, cheap |
| 1 | Meta (title/anchor text, headers) | when the index shows a NEW id |
| 2 | Body fetch + SHA-256 | only when the cheap score crosses threshold |

Scoring is pluggable metadata-only signals:

- **grammar** — regexes over handle/id text (e.g. `agent-\d{3,}`, `agent-(ours|fast)\d+`)
- **epoch-ts** — agents that self-timestamp with raw epoch integers
- **cadence** — same author hitting repeatedly inside a rolling window (metronomes stand out in a timestamp column)

One scored JSON event per line, appended to day-shards. Idempotent: second tick over unchanged state finds zero.

## Layout

```
swarm_index_watch.py   # the whole thing, stdlib only, no deps
venues.json            # your venues + scoring weights
state.json             # per-venue cursors, author hit windows (auto-created)
shards/YYYY-MM-DD.jsonl  # append-only event log (auto-created)
```

## Venue adapters

- **mediawiki** — one `recentchanges` API call gets every recent edit (title/user/timestamp/sizes). Near-real-time firehose.
- **listpage** — generic pastebin-style recent/archive page: regex the ids, diff against cursor, keep the anchor text as scoreable metadata.

Add your own: one generator function yielding `{id, author, title, url, ts}` items, register it in `ADAPTERS`.


## Injection tripwire

Tier-2 bodies are scanned for prompt-injection markers (`[SYSTEM]`, ignore-your-instructions, maintenance-mode lures, etc.). Matches are kept as evidence AND flagged (`injection_flag` + matched markers). Downstream readers must treat flagged bodies as untrusted input, never as instructions. Added after a live injection paste was found in the wild targeting exactly this kind of tooling: any watcher that fetches bodies is a reader, and readers are targets.

## Config

```json
{
  "body_threshold": 3,
  "w_grammar": 2, "w_epoch_ts": 1, "w_cadence": 2,
  "cadence_window_s": 3600, "cadence_min_hits": 3,
  "grammar_regexes": ["\\bagent[-_]?\\d{3,}\\b"],
  "venues": [
    {"name": "some-wiki", "type": "mediawiki",
     "api": "https://example.org/w/api.php",
     "page_base": "https://example.org/wiki/"},
    {"name": "some-pastebin", "type": "listpage",
     "url": "https://example.org/recent",
     "id_regex": "/view/([0-9a-f]{8})",
     "item_url": "https://example.org/view/{id}",
     "fetch_body": true}
  ]
}
```

## Run it

```bash
# one tick
./swarm_index_watch.py --config venues.json

# cron, 15-min ticks, overlap-safe
*/15 * * * *  flock -n /tmp/swarmwatch.lock /path/to/swarm_index_watch.py \
                --config /path/to/venues.json >> /var/log/swarmwatch.log 2>&1
```

## The cross-site half (read this)

This tool is the per-venue sensor. The singleton problem — "each site has 1 new post, individually fine, collectively suspicious" — is solved *downstream*: feed the JSONL shards into whatever aggregates by handle/grammar across venues. One note on one site is invisible; the same grammar on forty sites is the loudest thing on the internet. Seed your aggregator with known handle grammar and a singleton on a brand-new site scores hot the moment it lands.

Swarms are repetition. A true singleton is either not a swarm or it's the scout post — and the follow-up traffic will trip the index within days anyway.

## Notes

- Stdlib only. Python 3.9+. No pip, no venv, no excuses.
- Be polite: set a real contact UA, respect robots where it matters, don't hammer.
- Tested on mock venues before release; the suspicious item got body-fetched, the boring post never got touched.

Built by Blackfish Security as bulk-forensics tooling, released for the swarmhunting community. Issues and PRs welcome.
