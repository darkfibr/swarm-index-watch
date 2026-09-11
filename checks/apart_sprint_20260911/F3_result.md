# F3 — Harvester detection from public text alone

**Verdict: PARTIAL** (injection-marker half FAILs with zero recall; ad-hoc harvester half flags the single proxy-positive with 0 fresh false positives but is overfit, n=1).

**Source gap (stated):** no `llmrt`-class listing exists anywhere local — a grep over the watcher's scripts, state, and index_watch directories returns only an unrelated watchdog comment. There is therefore no mapped listing to draw phrases from. Proxy ground truth below; re-run against the true llmrt listing is **FUTURE-WORK**.

## Marker set

A. Injection markers (verbatim from watcher `INJECTION_RES`, `swarm_index_watch.py:282-292`): `\[SYSTEM\]`, `ignore (all |all prior |all previous |your previous |prior )?instructions`, `you are now (a|an|in|the)`, `maintenance mode`, `perform the following action`, `disregard (all )?(prior|previous|above)`, `new instructions?:`, `jailbreak`, `do anything now`.
B. Harvester-v1 (ad-hoc, public-text only, built from the single shard-level prompt-solicitation doc `shards/2026-09-10.jsonl` publicboard `273ba53d` — "hash-verified LLM red-team scan: paste an agent or system prompt … verdict plus … corpus fingerprint … permanent /r/<id> link"): `system prompt`, `reveal .*prompt|prompt.*reveal`, `paste .*prompt|prompt.*paste`, `exfiltrat`, `harvest`, `red-?team.*prompt|prompt.*red-?team`, `verdict.*fingerprint|fingerprint.*verdict`, `/r/[A-Za-z0-9_-]{4,}`.
C. Grammar baseline (watcher `grammar_regexes`, pre-Sep-10 venue-config backup): 11 patterns incl `\bagent[-_]?\d{2,}\b`, `PublicBoard relay`, `Authorized public editability test`, `OpenAgentChat`.

## Scores

Shard level (1,947 `t=new` docs across all shards): injection hits **0/1947 (0 venues)**; grammar hits 266 (probier 140, openagentforum **114/114 = 100% FP rate** — every `agent_*` sender matches, dse 2, others ≤2, thecolony 1).
Fresh pulls 2026-09-11 (7 venues, 168 docs: agentworkpad 8, thecolony 20, openagentforum 20, publicboard 50, aiforum 40, swarmmemo 20, fragbin 10; files `/tmp/f_*.json`, all HTTP 200): injection **0/168**, harvester-v1 **0/168** (proxy-positive ad aged out of the 50-doc publicboard window — confirms staleness, not absence), grammar **20/168**, all 20 in openagentforum (FP rate 1.00 there, 0.00 elsewhere; example sender `agent_5ca69fcc029e2f1f`).

## Precision on the proxy-positive

Proxy known-positive = publicboard shard doc `273ba53d` (only prompt-harvesting-shaped public text in corpus). Injection set: does NOT flag it (recall 0/1 → injection-half FAIL). Harvester-v1: flags it 1/1 (by construction) with **0 false positives on 168 fresh docs** — meets the brief's numeric PASS bar (known-positive flags, ≤1 FP) but is circular (patterns derived from the same doc) and n=1. Hence **PARTIAL**, not PASS: public-text flagging is demonstrated as feasible (harvester phrasing is distinctive; grammar FP load is isolated to `agent_*` venues), but the marker set is unvalidated until run against the true llmrt listing (FUTURE-WORK: obtain listing, re-score, report real precision/recall).
