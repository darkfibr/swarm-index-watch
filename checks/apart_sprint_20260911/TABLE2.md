# Table 2 — Forecasting checks (paper-ready)

| # | Verdict | One-line evidence | Paper-ready numbers |
|---|---|---|---|
| F1 Seeding reuse | FAIL | Sep-06 `159.146.96.208` burst persists in 30-day rc windows but zero new emissions at any of 5 re-pulled venues; Sep-10/11 shards 0 hits; no /24 siblings | 0/5 venues recur; 11 shard+state hits all Sep 05–07; 1/1 distinct /24 IP is .208 |
| F2 Operator coverage | 4/26 present (15%) | Named-human revert capacity only on 4 proWiki wikis (HelmutLeitner-class + FranzNahrada revert `1.287` + `Seite gelöscht.`); paste/agent lane 0/17 | 4/26 present, 5/26 unclear, 17/26 absent (present+unclear 9/26 = 35% upper bound) |
| F3 Harvester detection | PARTIAL | `INJECTION_RES` recall 0 (0/1947 shard, 0/168 fresh docs); harvester-v1 flags proxy-positive with 0/168 fresh FPs but is overfit (n=1); grammar FP 100% on openagentforum | injection 0/2115; grammar 20/168 fresh all-FP; harvester-v1 1/1 proxy recall, 0 FP (unvalidated) |
| F4 Second-breach linkage | ECOSYSTEM | Windows, naming, cadence (57m38s vs task-cooldown tiers), infra, TTPs all distinct; same OpenAI-eval developer + shared relay grammar (`r.jina.ai`, SEC `county.json`) | 5/7 indicators distinct, 2/7 shared; agrees with collusion.wiki distinct-swarm call |
| F5 Shortener persistence | 10/26 alive (38%) | Ledger relay+target domain census: deaths cluster in CORS-proxy lane; majors alive; `sec.gov` 403 = WAF not removal | 10/26 HTTP 200; 15/26 resolving (200+3xx = 58%); 11/26 dead (42%) |

Caveats: F3 has no local llmrt listing (proxy ground truth, re-run FUTURE-WORK); F5 censuses domains not per-alias URLs (alias table FUTURE-WORK). All claims sourced in `F{1..5}_result.md`.
