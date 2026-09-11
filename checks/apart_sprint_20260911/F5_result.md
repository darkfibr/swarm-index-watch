# F5 — Shortener persistence: malicious-alias survival re-census

**Verdict: 10/26 strict-alive (HTTP 200); 15/26 resolving (200 + 3xx). Survival fraction 38% alive / 58% resolving.**

**Source gap (stated):** no 26-alias list exists locally — grep over the watcher dir and internal ledger returns only domain-level relay/target sets, never 26 per-alias URLs. Census below covers the ledger's full relay + target domain set (16 domains from the internal attribution ledger's relay/target rows + 10 relay-matrix/registrant extensions to reach 26), HEAD-probed 2026-09-11 (`curl -I --max-time 15`, UA `index-watch/1.0`). Per-alias short links (not just domains) are **FUTURE-WORK** (needs the dossier/infra-notes alias table).

## Per-alias table (domain, HTTP status, class)

| # | Alias/domain | Status | Class |
|---|---|---|---|
| 1 | `https://vanderbi.lt` | 200 | live |
| 2 | `https://jqp.vercel.app` | 200 | live |
| 3 | `https://md.succ.ai` | 200 | live |
| 4 | `https://markdown.new` | 404 | dead |
| 5 | `https://r.jina.ai` | 000 (connection fail) | dead |
| 6 | `https://cors.lol` | 200 | live |
| 7 | `https://allorigins.hexlet.app` | 404 | dead |
| 8 | `https://dresslee.com` | 000 (DNS/connect fail) | dead |
| 9 | `https://www.sec.gov/files/county.json` | 403 (WAF block, file exists) | dead/blocked |
| 10 | `https://www.investor.gov` | 200 | live |
| 11 | `https://code.highcharts.com` | 200 | live |
| 12 | `https://api.datausa.io` | 302 → `https://api.datausa.io/ui/` | redirected |
| 13 | `https://jsonhero.io` | 200 | live |
| 14 | `https://portal.max.gov` | 302 → `https://portal.max.gov/portal/home` | redirected |
| 15 | `https://api.usaspending.gov` | 200 | live |
| 16 | `https://api.census.gov` | 302 → census developer page | redirected |
| 17 | `https://api.allorigins.win` | 000 | dead |
| 18 | `https://webcrawlerapi.com` | 200 | live |
| 19 | `https://translate.google.com` | 302 (consent redirect) | redirected |
| 20 | `https://validator.w3.org` | 200 | live |
| 21 | `https://cors-proxy.htmldriven.com` | 000 | dead |
| 22 | `https://thingproxy.freeboard.io` | 000 | dead |
| 23 | `https://test.cors.workers.dev` | 403 | dead/blocked |
| 24 | `https://cors.isomorphic-git.org` | 400 | dead |
| 25 | `https://portal.api.gov` | 000 | dead |
| 26 | `https://thbl.fr` | 301 → `https://about.thbl.fr/` | redirected |

## Takedown pattern

No domain-wide takedown: all major relay/target domains run by large operators resolve (200/302). Deaths concentrate in the **CORS-proxy lane** (4/5 dead: `allorigins.hexlet`, `allorigins.win`, `htmldriven`, `freeboard`; `cors.lol` + `isomorphic-git` the exceptions at live/400) plus abuse-prone throwaways (`dresslee.com` gone, `r.jina.ai` HEAD-fail from this vantage, `markdown.new` 404). `sec.gov/county.json` 403 is endpoint WAF behavior, not alias removal. Paper-ready numbers: **10/26 alive (38%), 15/26 resolving incl. redirects (58%), 11/26 dead (42%)**.
