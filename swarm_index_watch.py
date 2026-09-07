#!/usr/bin/env python3
"""
swarm_index_watch.py — index-first anomaly watcher for swarm surfaces.

Philosophy: don't scrape content, scrape indexes. Metadata is cheap;
content gets pulled only when metadata moves AND scores.

Tiers:
  0  index scan        (always, cheap: recentchanges API / list-page hash)
  1  meta fetch        (title/headers, when index shows a NEW id)
  2  body fetch        (only when the cheap score crosses threshold)

State:  ./state.json  (per-venue cursors, author hit windows)
Output: ./shards/YYYY-MM-DD.jsonl  (append-only day shards, one event/line)

Cron (15-min ticks, self-overlap-safe):
  */15 * * * *  flock -n /tmp/swarmwatch.lock /path/to/swarm_index_watch.py \
                  --config /path/to/venues.json >> /var/log/swarmwatch.log 2>&1

Stdlib only. No deps. GPLvwhatever, take it.
"""

import argparse, hashlib, json, os, re, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone

UA = {"User-Agent": "index-watch/1.0 (research; contact: you)"}
EPOCH_RE = re.compile(r"\b(?:ts=)?(1[6-9]\d{8})\b")  # plausible 2026+ epoch ints


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers)


# ---------- venue adapters: each yields candidate items from the CHEAP index ----------
# item = {"id": str, "author": str|None, "title": str|None, "url": str|None, "ts": epoch|None}

def idx_mediawiki(v):
    """MediaWiki recentchanges firehose: one call, every recent edit."""
    q = urllib.parse.urlencode({
        "action": "query", "list": "recentchanges", "format": "json",
        "rclimit": v.get("limit", 100), "rcprop": "title|user|timestamp|sizes|ids",
    })
    data, _ = fetch(f"{v['api']}?{q}")
    for rc in json.loads(data).get("query", {}).get("recentchanges", []):
        yield {
            "id": f"rc{rc['revid']}",
            "author": rc.get("user"),
            "title": rc.get("title"),
            "url": v.get("page_base", "") + urllib.parse.quote(rc.get("title", "")),
            "ts": int(datetime.fromisoformat(
                rc["timestamp"].replace("Z", "+00:00")).timestamp()),
        }


def idx_listpage(v):
    """Generic pastebin-style recent/archive list: hash the list, diff the ids.
    The anchor's own line is kept as the item's text so grammar/epoch scoring
    works without a body fetch."""
    data, _ = fetch(v["url"])
    text = data.decode("utf-8", "replace")
    seen = set()
    for line in text.splitlines():
        for m in re.findall(v["id_regex"], line):
            pid = m if isinstance(m, str) else m[0]
            if pid in seen:
                continue
            seen.add(pid)
            clean = re.sub(r"<[^>]+>", " ", line).strip()
            yield {
                "id": pid,
                "author": None,
                "title": clean[:300],
                "url": v["item_url"].format(id=pid) if v.get("item_url") else None,
                "ts": None,
            }



ADAPTERS = {"mediawiki": idx_mediawiki, "listpage": idx_listpage}


# ---------- scoring: cheap metadata only ----------

def score_item(item, author_hits, cfg):
    s, why = 0, []
    author = item.get("author") or ""
    text = " ".join(str(x) for x in (item.get("title"), author, item.get("id")) if x)

    for rx in cfg.get("grammar_regexes", []):
        if re.search(rx, text, re.I):
            s += cfg.get("w_grammar", 2)
            why.append("grammar")
            break

    if EPOCH_RE.search(text):
        s += cfg.get("w_epoch_ts", 1)
        why.append("epoch-ts")

    # cadence: same author hitting repeatedly inside the window
    now = time.time()
    recent = [t for t in author_hits.get(author, []) if now - t < cfg.get("cadence_window_s", 3600)]
    if author and len(recent) >= cfg.get("cadence_min_hits", 3):
        s += cfg.get("w_cadence", 2)
        why.append(f"cadence x{len(recent)}")

    return s, why


# ---------- main loop ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="venues.json")
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()

    cfg = json.load(open(a.config))
    state_path = os.path.join(a.dir, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {"venues": {}, "authors": {}}
    os.makedirs(os.path.join(a.dir, "shards"), exist_ok=True)
    shard = os.path.join(a.dir, "shards", datetime.now(timezone.utc).strftime("%Y-%m-%d.jsonl"))

    body_thr = cfg.get("body_threshold", 3)
    events = 0

    with open(shard, "a") as out:
        for v in cfg["venues"]:
            name = v["name"]
            cursor = state["venues"].setdefault(name, {"seen": []})
            seen = set(cursor["seen"])
            try:
                items = list(ADAPTERS[v["type"]](v))
            except Exception as e:
                out.write(json.dumps({"t": "error", "venue": name, "err": str(e),
                                      "ts": datetime.now(timezone.utc).isoformat()}) + "\n")
                continue

            for item in items:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                s, why = score_item(item, state["authors"], cfg)
                ev = {"t": "new", "venue": name, "score": s, "why": why,
                      "ts": datetime.now(timezone.utc).isoformat(), **item}

                # tier 2: body fetch only when the cheap score says so
                if s >= body_thr and item.get("url") and v.get("fetch_body", True):
                    try:
                        body, hdrs = fetch(item["url"])
                        ev["body_sha256"] = hashlib.sha256(body).hexdigest()
                        ev["body_bytes"] = len(body)
                        # keep small bodies; big ones get hashed + truncated
                        ev["body"] = body[:20000].decode("utf-8", "replace")
                        ev["tier"] = 2
                    except Exception as e:
                        ev["body_err"] = str(e)
                else:
                    ev["tier"] = 1

                out.write(json.dumps(ev) + "\n")
                events += 1
                if item.get("author"):
                    state["authors"].setdefault(item["author"], []).append(time.time())

            cursor["seen"] = list(seen)[-cfg.get("seen_keep", 5000):]

    # prune author hit windows
    cutoff = time.time() - cfg.get("cadence_window_s", 3600)
    for k in list(state["authors"]):
        state["authors"][k] = [t for t in state["authors"][k] if t > cutoff]
        if not state["authors"][k]:
            del state["authors"][k]

    json.dump(state, open(state_path, "w"))
    print(f"{datetime.now(timezone.utc).isoformat()} tick ok: {events} new items -> {shard}")


if __name__ == "__main__":
    main()
