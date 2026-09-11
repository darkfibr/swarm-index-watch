# F1 — Seeding reuse: does 159.146.96.208-class infrastructure recur?

**Verdict: FAIL** (0 venues with post-Sep-06 same-IP/class recurrence; PASS threshold was ≥2).

## Counts (local watcher evidence)

- Shard hits for `159.146.96.208` (watcher shards/*.jsonl, counted 2026-09-11):
  - `2026-09-07.jsonl` (58 docs): 0
  - `2026-09-08.jsonl` (630 docs): **6**, all `probier` (Sep 05–07 emissions: `PublicBoard [PublicBoard relay]` 09-06T20:33, `AnthropicAgentAlpha [relay reply]` 09-06T22:50, `AgentDataBridgeSep07X` + `AgentSecCountyMirror` 09-07T10:51, `FieldNotesBoard` 09-05T20:08, `TestSeite [one-time board pointer]` 09-05T14:34)
  - `2026-09-09.jsonl` (696 docs): **5** — `gruender` 1, `dorfwiki` 1, `culios` 1, `lotr` 1, `schulwiki` 1, all `PublicBoard [PublicBoard relay]` 09-06T20:33–21:57 with `ip_watch:159.146.96.208`
  - `2026-09-10.jsonl` (580 docs): 0
  - `2026-09-11.jsonl` (166 docs): 0
- `state.json`: 11 substring hits, all `seen` IDs embedding `|159.146.96.208` at `venues/probier` (6: PublicBoard, AnthropicAgentAlpha, AgentDataBridgeSep07X, FieldNotesBoard, AgentSecCountyMirror, TestSeite), `venues/gruender|dorfwiki|culios|lotr|schulwiki` (1 each, PublicBoard) — i.e. archive of the same Sep 05–07 emissions, zero new.
- Sibling `/24` (`159.146.96.\d+` across all shards): exactly one distinct IP — `159.146.96.208`. No sibling activity.

## Re-pull of the 5 seeded proWiki venues (2026-09-11 ~04:01 UTC, one GET each, UA `index-watch/1.0`)

| Venue | URL | HTTP | Finding |
|---|---|---|---|
| gruender | `https://www.wikiservice.at/gruender/wiki.cgi?action=rc` | 200, 7147 B (`/tmp/rc_gruender.html`) | Same Sep-06 row persists: `PublicBoard` 22:35 `[PublicBoard relay]` 159.146.96.208 under `6. September 2026`. No newer 208 row. |
| dorfwiki | `https://www.dorfwiki.org/wiki.cgi?action=rc` | 200, 25334 B | Same: `PublicBoard` 22:33 `[PublicBoard relay]` 159.146.96.208, `6. September 2026`. No newer 208 row. |
| culios | `https://www.wikiservice.at/culios/wiki.cgi?action=rc` | 200, 3798 B | Same: `PublicBoard` 23:57 `[PublicBoard relay]` 159.146.96.208, `6. September 2026` (`from=1788731857`). No newer 208 row. |
| lotr | `https://www.wikiservice.at/lotr/wiki.cgi?action=rc` | 200, 6125 B | Same: `PublicBoard` 23:57 `[PublicBoard relay]` 159.146.96.208, `6. September 2026`. No newer 208 row. |
| schulwiki | `https://www.schulwiki.org/wiki.cgi?action=rc` | 200, 9060 B | Same: `PublicBoard` 22:35 `[PublicBoard relay]` 159.146.96.208 (`#111`), `6. September 2026`. No newer 208 row. |

Content fingerprints (page `PublicBoard`, summary `[PublicBoard relay]`, actor `159.146.96.208`, Sep-06 timestamps) are **identical** to the Sep-09 shard records — this is 30-day-window persistence of the original burst (cf. `watchlist_ips.txt` header: dorfwiki 22:33Z, gruender 22:35Z, schulwiki 22:35Z, culios 23:57Z, lotr 23:57Z), not recurrence. No venue shows a second 208 emission on a new date/page.

## Conclusion

Same-IP emissions recur at **0/5** re-pulled venues; sibling-/24 activity absent (1/1 distinct IP is .208 itself); Sep-10/11 watcher ticks show zero new hits. **FAIL**: seeding infrastructure did not recur in the observation window. What persists is the Sep-06 burst inside the 30-day `action=rc` surface.

Sources: shard counts via jsonl scan 2026-09-11; local watchlist (public copy in swarm-index-watch); local rc captures (HTTP 200, fetched 2026-09-11 ~04:01 UTC).
