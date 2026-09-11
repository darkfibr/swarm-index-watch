# F2 — Operator coverage: fraction of swarm venues with revert capacity

**Verdict: 4/26 operator-present (15%); 5/26 unclear; 17/26 absent.** Present + unclear = 9/26 (35%) upper bound.

Method: mined all 2,130 watcher shard docs (shards 2026-09-07..11) per venue for `actor_kind=user` (named, non-IP actors), human-moderator names, and revert/moderation traces (`revert|undo|delete|lösch|gelöscht|minor editing` in summary, `changes>1` bursts); spot-checked unclear venues live (fractal rc + getpostingboard, 2026-09-11). Census denominator 26 = 25 `venues.json` venues + `getpostingboard` (recovered from the pre-Sep-10 venue-config backup; live `venues.json` omits it).

## Full 26-row venue table

| Venue | Operator presence | Evidence one-liner |
|---|---|---|
| probier | present | `HelmutLeitner` 22 user-kind edits incl `ForumSeite` 8-change burst; Sep-08 shard `probier` HelmutLeitner rows (e.g. `MessageBoardsForAgents`, `TestSeite` changes=4) — source: `shards/2026-09-08.jsonl:531,535-537,544-557` |
| dse | present | `HelmutLeitner` + `GertMUC` + `MartinQuicksilber`; `WikiIncident`/`KategorieWikiIncident`/`WikiIncident2026` pages Sep-10 with changes up to 21, `ForumSeite [minor editing of my post]` — source: `shards/2026-09-10.jsonl:490,504,506-510,516,518,520,523-525,535-537` |
| gruender | present | `HelmutLeitner` `TestSeite`/`Context`/`RecentChanges` edits Sep-08 — source: `shards/2026-09-09.jsonl:215-217` |
| dorfwiki | present | `FranzNahrada` `TestSeite [revert to revision 1.287]` + `Seite gelöscht.` + `AgentsImDorfWiki` changes=6; `FritzEndl` Triesterviertel edit — source: shard mining + `shards/2026-09-09.jsonl:221-225` |
| fractal | unclear | 8 user-kind actors (`CentaurAgent`,`ClaudeForScry`,`CollusionWikiProbe`,`HeraldAgent`,`JonesHarode`,`SomeSGuy`,`help_peer`) — researcher/probe-shaped, no human-moderator name, no revert trace; live rc 2026-09-11 (200, 7139 B) shows only probe names — source: shard mining + `/tmp/rc_fractal.html` |
| culios | unclear | Single user-kind actor `SacrificeRational` (agent-shaped), no revert trace — source: shard mining |
| lotr | unclear | Single user-kind actor `ObeyCollective` (agent-shaped), no revert trace — source: shard mining |
| schulwiki | unclear | Single user-kind actor `ForOurOwnNoWayFix` (agent-shaped), no revert trace — source: shard mining |
| getpostingboard | unclear | Sep-10 shard: `{"t":"error","venue":"getpostingboard","err":"Expecting value: line 1 column 1 (char 0)"}` (endpoint serves HTML, not JSON); live 2026-09-11 HTTP 200 `Unsorted` board (`/tmp/f_gpb.html`, 17670 B) — no moderation surface observed — sources: `shards/2026-09-10.jsonl:430`, live GET |
| k4be | absent | 15 docs, 0 user-kind actors, no revert traces — source: shard mining |
| fragbin | absent | 30 docs, 0 user-kind actors — source: shard mining |
| agentworkpad | absent | 8 docs, 0 user-kind actors — source: shard mining |
| thecolony | absent | 595 docs, 0 user-kind actors — source: shard mining |
| mobdarkforest | absent | 126 docs, 0 user-kind actors — source: shard mining |
| minetest | absent | 15 docs, 0 user-kind actors — source: shard mining |
| artixlinux | absent | 32 docs, 0 user-kind actors — source: shard mining |
| openagentforum | absent | 114 docs, 0 user-kind actors (all `agent_*` senders are IP/anon-kind API identities, no moderator) — source: shard mining |
| publicboard | absent | 139 docs, 0 user-kind actors, no moderation trace — source: shard mining |
| aiforum | absent | 114 docs, 0 user-kind actors — source: shard mining |
| swarmmemo | absent | 72 docs, 0 user-kind actors — source: shard mining |
| probyte | absent | 15 docs, 0 user-kind actors — source: shard mining |
| annafyi | absent | 15 docs, 0 user-kind actors — source: shard mining |
| fasterit | absent | 7 docs, 0 user-kind actors — source: shard mining |
| tarcseh | absent | 15 docs, 0 user-kind actors — source: shard mining |
| dynavirt | absent | 15 docs, 0 user-kind actors — source: shard mining |
| smirky | absent | 7 docs, 0 user-kind actors — source: shard mining |

## Paper-ready numbers

Operator-present fraction **4/26 ≈ 15%** (probier, dse, gruender, dorfwiki — all proWiki-farm wikis with named human moderators and revert/delete traces). Pastebin/agent-board lane: **0/17** show any operator trace. Note: `actor_kind=user` alone is insufficient (agent names such as `CentaurAgent` also appear as named actors); presence requires a human-moderator name and/or revert evidence, which only the 4 listed venues meet.
