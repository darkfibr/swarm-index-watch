# CHECKS — Forecasting check reproduction (Apart × CeSIA AI Incident Response Sprint, Track 2)

Run window: 2026-09-11/12, on the Berlin watch box. Results and full evidence tables: `checks/apart_sprint_20260911/` (`F1_result.md` … `F5_result.md`, `TABLE2.md`).

Every check is runnable by a third party with a browser or curl. No privileged access, no auth, no posting. One GET per venue per run; if a venue rate-limits, back off, record it, move on. Illicit material is read at title level only; bodies are never fetched.

## F1 — Seeding reuse (verdict: FAIL — seeding did not recur)

**Claim under test:** seeding infrastructure (159.146.96.208-class) recurs across venues over time.

**Data:** watcher shards (`shards/YYYY-MM-DD.jsonl`, local runtime artifacts — operative excerpts are quoted with line numbers in F1_result.md), `state.json`, `watchlist_ips.txt`, and the five seeded proWiki recent-changes endpoints (public).

**Procedure:**
1. Count per-shard hits: `grep -c '159\.146\.96\.208' shards/*.jsonl`
2. Sibling /24 scan: `grep -ohE '159\.146\.96\.[0-9]+' shards/*.jsonl state.json | sort -u`
3. Re-pull the five seeded venues (one GET each, UA `index-watch/1.0`) and grep each capture for a 208-row dated later than Sep 07:
   - `https://www.wikiservice.at/gruender/wiki.cgi?action=rc`
   - `https://www.dorfwiki.org/wiki.cgi?action=rc`
   - `https://www.wikiservice.at/culios/wiki.cgi?action=rc`
   - `https://www.wikiservice.at/lotr/wiki.cgi?action=rc`
   - `https://www.schulwiki.org/wiki.cgi?action=rc`
4. Compare content fingerprints (page, summary, actor, timestamps) against `watchlist_ips.txt`.

**Pass criterion:** same-IP/class emissions recur at ≥2 venues post-Sep-07.
**Observed:** 0/5 venues recur; 11 shard/state hits all dated Sep 05–07; Sep-10/11 shards zero hits; the /24 contains exactly one IP (.208 itself). **FAIL.** Full evidence: `F1_result.md`.

## F2 — Operator coverage (verdict: 4/26 present, 15%)

**Claim under test:** what fraction of swarm venues has any operator revert capacity.

**Data:** watcher shards (2,130 docs, 2026-09-07..11), `venues.json`, plus the pre-Sep-10 venue-config backup for the 26th venue (getpostingboard); spot-check GETs for unclear venues.

**Procedure:**
1. Per venue, mine shard docs for `actor_kind=user` (named, non-IP actors), human-moderator names, and moderation traces: `revert|undo|delete|lösch|gelöscht|minor editing` in edit summaries, plus `changes>1` bursts.
2. The same audit is reproducible live on mediawiki venues with one GET (`<venue>/wiki.cgi?action=rc`): scan for named human editors and revert/delete summaries.
3. Classify present / absent / unclear. Presence requires a human-moderator name and/or revert evidence — named `agent_*` handles alone are insufficient.

**Observed:** present 4 (probier, dse, gruender, dorfwiki — all proWiki-farm wikis), unclear 5, absent 17; pastebin/agent-board lane 0/17. **4/26 ≈ 15%.** Full 26-row table with shard-line sources: `F2_result.md`.

## F3 — Harvester detection (verdict: PARTIAL)

**Claim under test:** llmrt-class prompt-harvesting can be flagged from public text alone.

**Procedure:**
1. Marker set A (injection phrases, verbatim from `swarm_index_watch.py` `INJECTION_RES`): `\[SYSTEM\]`, `ignore (all |all prior |all previous |your previous |prior )?instructions`, `you are now (a|an|in|the)`, `maintenance mode`, `perform the following action`, `disregard (all )?(prior|previous|above)`, `new instructions?:`, `jailbreak`, `do anything now`.
2. Marker set B (harvester phrasing, built from the one known-positive public doc): `system prompt`, `reveal .*prompt|prompt.*reveal`, `paste .*prompt|prompt.*paste`, `exfiltrat`, `harvest`, `red-?team.*prompt|prompt.*red-?team`, `verdict.*fingerprint|fingerprint.*verdict`, `/r/[A-Za-z0-9_-]{4,}`.
3. Score a fresh pull of ≥5 agent boards (listpage recent endpoints, one GET each) and compute precision on the known-positive.

**Observed:** set A recall 0/1,947 shard docs and 0/168 fresh docs; set B flags the proxy-positive with 0/168 false positives but is overfit (n=1); grammar baseline false-positives 100% on `agent_*`-handle venues. **PARTIAL.** Full scores plus the stated source gap (no local llmrt listing exists; re-run against the true listing is future work): `F3_result.md`.

## F4 — Second-breach linkage (verdict: ECOSYSTEM)

**Claim under test:** does the German-wiki breach share fingerprints with the HF intrusion — one actor or one ecosystem.

**Data:** `https://collusion.wiki` (public analysis + dataset) vs the public reconstruction in `github.com/darkfibr/the-second-swarm` (`README`, `02_hf_fleet/`) and `github.com/darkfibr/hf-fleet-corpus` (`corpus-v1.0`).

**Procedure:** build a 7-row indicator table (window, IP/compute, agent naming, cadence, TTP, developer attribution, relay/target grammar), one column per breach, mark each Shared / Distinct.

**Observed:** 5/7 distinct (window, infrastructure, naming grammar, cadence, TTP stack), 2/7 shared (same OpenAI-eval developer; same relay/target grammar family: `r.jina.ai` relays, SEC `county.json` target). Agrees with collusion.wiki's distinct-swarm call, with the one-ecosystem caveat documented. **ECOSYSTEM.** Full indicator table: `F4_result.md`.

## F5 — Shortener persistence (verdict: 10/26 alive, 38%)

**Claim under test:** how long malicious shortener/relay aliases survive.

**Procedure:** `curl -I --max-time 15 -A 'index-watch/1.0' <alias>` for each of the 26 domains in the census; classify 200 = live, 3xx = redirected, else dead; compute the survival fraction.

**Observed:** 10/26 HTTP 200, 15/26 resolving (200+3xx = 58%), 11/26 dead; deaths cluster in the CORS-proxy lane. Full per-alias table: `F5_result.md`. Known gap: this censuses domains, not per-alias short links (future work).

## Notes

- Shard files (`shards/`, `state.json`) are local runtime artifacts of `swarm_index_watch.py` (auto-created; see README). The operative evidence rows are quoted, with shard line numbers, inside each `F*_result.md`.
- Honest partials stay partials: every check names its own source gap where one exists.
