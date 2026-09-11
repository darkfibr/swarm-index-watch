#!/usr/bin/env python3
"""
swarm_signal_scan.py — offline signal scan over watcher shards.

ADD 2026-09-11 (Apart sprint, Kane-talk integration pass): three detection
axes from the public-traces literature, folded onto shard history:

  1. CADENCE   — agents emit on metronomes. Per (venue, actor) interval
                 regularity: coefficient of variation + Benford first-digit
                 chi2 on intervals (reuses benford_interval_score).
  2. RELAY LAG — the same emission landing on 2+ venues N minutes apart
                 fingerprints the relay path (side-channel).
  3. ACTOR TEXT — "activity is typically not human-looking": name grammars
                 and template-summary repetition scoring.

Read-only: scans shards, prints a report. No fetching, no writes to state.

Usage: swarm_signal_scan.py <shards_dir> [--since YYYY-MM-DD] [--json]
"""
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from swarm_index_watch import benford_interval_score  # reuse, don't re-derive

TS_KEYS = ("ts", "epoch", "time", "timestamp")
ACTOR_KEYS = ("actor", "author", "user")
TEXT_KEYS = ("title", "summary")

NAME_RES = [
    (re.compile(r"^agent_[0-9a-f]{6,}$", re.I), "api-style agent_ id"),
    (re.compile(r"\bagent[-_]?\d{2,}\b", re.I), "agentNN grammar"),
    (re.compile(r"^[A-Z][a-z]+Agent[A-Z]", ), "camel Agent compound"),
    (re.compile(r"\b(bot|swarm|hive|node|relay)\d*\b", re.I), "machine noun"),
]

def doc_ts(d):
    for k in TS_KEYS:
        v = d.get(k)
        if isinstance(v, (int, float)) and v > 1_700_000_000:
            return int(v)
    return None

def doc_actor(d):
    for k in ACTOR_KEYS:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def doc_text(d):
    parts = [str(d[k]) for k in TEXT_KEYS if d.get(k)]
    return " | ".join(parts)

def norm_text(t):
    return re.sub(r"\s+", " ", t.lower()).strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shards")
    ap.add_argument("--since", default=None, help="YYYY-MM-DD; skip older shards")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    docs = []
    for p in sorted(Path(args.shards).glob("*.jsonl")):
        if args.since and p.stem < args.since:
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("t") == "new":
                docs.append(d)

    # ---- 1. cadence ----
    by_actor = defaultdict(list)
    for d in docs:
        ts, a, v = doc_ts(d), doc_actor(d), d.get("venue")
        if ts and a:
            by_actor[(v, a)].append(ts)
    cadence = []
    for (v, a), ts in by_actor.items():
        ts = sorted(set(ts))
        if len(ts) < 4:
            continue
        iv = [b - a_ for a_, b in zip(ts, ts[1:]) if b - a_ > 0]
        if len(iv) < 3:
            continue
        mean = sum(iv) / len(iv)
        if mean <= 0:
            continue
        var = sum((x - mean) ** 2 for x in iv) / len(iv)
        cv = (var ** 0.5) / mean
        bf = benford_interval_score(iv)
        cadence.append({
            "venue": v, "actor": a, "n": len(ts), "mean_interval_s": round(mean, 1),
            "cv": round(cv, 3), "benford_chi2": round(bf, 2) if bf is not None else None,
            "metronome": cv < 0.15,
        })
    cadence.sort(key=lambda r: (not r["metronome"], r["cv"]))

    # ---- 2. relay lag ----
    by_text = defaultdict(list)
    for d in docs:
        ts, t, v = doc_ts(d), doc_text(d), d.get("venue")
        if ts and t and v:
            by_text[norm_text(t)].append((ts, v))
    lags = defaultdict(list)
    for t, obs in by_text.items():
        venues = sorted({v for _, v in obs})
        if len(venues) < 2:
            continue
        per_venue = defaultdict(list)
        for ts, v in obs:
            per_venue[v].append(ts)
        ordered = sorted(per_venue.items(), key=lambda kv: min(kv[1]))
        for (v1, ts1), (v2, ts2) in zip(ordered, ordered[1:]):
            for a_, b_ in zip(sorted(ts1), sorted(ts2)):
                lags[(v1, v2)].append(b_ - a_)
    relay = [{"from": a, "to": b, "n": len(v), "lags_s": sorted(v)[:10],
              "median_s": sorted(v)[len(v)//2]}
             for (a, b), v in lags.items() if len(v) >= 2]
    relay.sort(key=lambda r: -r["n"])

    # ---- 3. actor text ----
    actors = defaultdict(lambda: {"docs": 0, "name_hits": [], "summaries": defaultdict(int)})
    for d in docs:
        a = doc_actor(d)
        if not a:
            continue
        rec = actors[a]
        rec["docs"] += 1
        for rx, why in NAME_RES:
            if rx.search(a) and why not in rec["name_hits"]:
                rec["name_hits"].append(why)
        s = d.get("summary") or d.get("title")
        if s:
            rec["summaries"][norm_text(str(s))] += 1
    actor_rep = []
    for a, rec in actors.items():
        reps = max(rec["summaries"].values(), default=0)
        template_ratio = round(reps / rec["docs"], 2) if rec["docs"] else 0
        if rec["name_hits"] or (rec["docs"] >= 3 and template_ratio >= 0.6):
            actor_rep.append({"actor": a, "docs": rec["docs"], "name_hits": rec["name_hits"],
                              "template_ratio": template_ratio})
    actor_rep.sort(key=lambda r: (-len(r["name_hits"]), -r["template_ratio"]))

    report = {"docs_scanned": len(docs), "cadence": cadence, "relay_lag": relay,
              "actor_text": actor_rep}
    if args.json:
        print(json.dumps(report, indent=1))
        return

    print(f"scanned {len(docs)} emission docs")
    print(f"\n== CADENCE ({sum(1 for c in cadence if c['metronome'])} metronomes of {len(cadence)} scored actors)")
    for c in cadence[:15]:
        flag = "METRONOME" if c["metronome"] else ""
        bf = f"{c['benford_chi2']:6}" if c['benford_chi2'] is not None else "    - "
        print(f"  {c['venue']}:{c['actor'][:32]:32} n={c['n']:4} mean={c['mean_interval_s']:>9}s cv={c['cv']:.3f} benford={bf} {flag}")
    print(f"\n== RELAY LAG ({len(relay)} cross-venue pairs)")
    for r in relay[:15]:
        print(f"  {r['from']} -> {r['to']}: n={r['n']} median lag {r['median_s']}s")
    print(f"\n== ACTOR TEXT ({len(actor_rep)} flagged actors)")
    for a in actor_rep[:15]:
        print(f"  {a['actor'][:40]:40} docs={a['docs']:4} template={a['template_ratio']} {'; '.join(a['name_hits'])}")

if __name__ == "__main__":
    main()
