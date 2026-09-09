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

import argparse, hashlib, json, os, re, sys, time, urllib.error, urllib.request, urllib.parse
from datetime import datetime, timezone

UA = {"User-Agent": "index-watch/1.0 (research; contact: you)"}
EPOCH_RE = re.compile(r"\b(?:ts=)?(1[6-9]\d{8})\b")  # plausible 2026+ epoch ints


def fetch(url, timeout=20, vkey=None, state=None):
    """GET with conditional validators. Returns (body, headers); body is None
    on 304 Not Modified. Validators persist in state['validators'][vkey or url].
    Venues without validators (cgi wikis) cost a real GET, but a small one."""
    hdrs = dict(UA)
    if vkey and state:
        prev = state.get("validators", {}).get(vkey)
        if prev:
            if prev.get("etag"):
                hdrs["If-None-Match"] = prev["etag"]
            if prev.get("lastmod"):
                hdrs["If-Modified-Since"] = prev["lastmod"]
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body, h = r.read(), dict(r.headers)
            if vkey and state:
                state.setdefault("validators", {})[vkey] = {
                    "etag": h.get("ETag"), "lastmod": h.get("Last-Modified")}
            return body, h
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, dict(e.headers)
        raise


# ---------- venue adapters: each yields candidate items from the CHEAP index ----------
# item = {"id": str, "author": str|None, "title": str|None, "url": str|None, "ts": epoch|None}

def idx_mediawiki(v, state=None):
    """MediaWiki recentchanges firehose: one call, every recent edit."""
    q = urllib.parse.urlencode({
        "action": "query", "list": "recentchanges", "format": "json",
        "rclimit": v.get("limit", 100), "rcprop": "title|user|timestamp|sizes|ids",
    })
    data, _ = fetch(f"{v['api']}?{q}", vkey="idx:" + v["name"], state=state)
    if data is None:
        return
    for rc in json.loads(data).get("query", {}).get("recentchanges", []):
        yield {
            "id": f"rc{rc['revid']}",
            "author": rc.get("user"),
            "title": rc.get("title"),
            "url": v.get("page_base", "") + urllib.parse.quote(rc.get("title", "")),
            "ts": int(datetime.fromisoformat(
                rc["timestamp"].replace("Z", "+00:00")).timestamp()),
        }

def idx_listpage(v, state=None):
    """Generic pastebin-style recent/archive list: hash the list, diff the ids.
    The anchor's own line is kept as the item's text so grammar/epoch scoring
    works without a body fetch."""
    data, _ = fetch(v["url"], vkey="idx:" + v["name"], state=state)
    if data is None:
        return
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

def _path(obj, dotted, default=None):
    """Walk a dotted path (author.username) through nested dicts. FIX 2026-09-08: agentworkpad/thecolony nest author objects; score_item needs hashable strings."""
    cur = obj
    for part in str(dotted).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur

def idx_jsonlist(v, state=None):
    """JSON list API (e.g. fragbin /api/pastes?page=N). Paginates v['pages'] pages.
    Field names configurable via id_key/title_key/ts_key."""
    for page in range(1, v.get("pages", 1) + 1):
        data, _ = fetch(v["url"].format(page=page),
                        vkey="idx:%s:p%d" % (v["name"], page), state=state)
        if data is None:
            continue
        root = json.loads(data)
        items = _path(root, v["items_path"], None) if v.get("items_path") else root.get(v.get("items_key", "items"), [])
        for it in items:
            ts = None
            raw_ts = it.get(v.get("ts_key", "")) if v.get("ts_key") else None
            if isinstance(raw_ts, bool):
                pass
            elif isinstance(raw_ts, (int, float)):
                # ADD 2026-09-09: some venues (openagentforum) emit ms epochs;
                # `ts_ms: true` normalises to the seconds convention used by
                # every other adapter's shard rows.
                ts = int(raw_ts / 1000) if v.get("ts_ms") else int(raw_ts)
            elif raw_ts:
                try:
                    ts = int(datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00")).timestamp())
                except ValueError:
                    pass
            yield {
                "id": str(it.get(v.get("id_key", "id"))),
                "author": _path(it, v["author_path"], None) if v.get("author_path") else it.get(v.get("author_key", "")),
                # ADD 2026-09-09: `title_path` allows nested title fields
                # (openagentforum payload.message); title_key stays flat for
                # every pre-existing venue.
                "title": _path(it, v["title_path"], None) if v.get("title_path") else it.get(v.get("title_key", "title")),
                "url": v["item_url"].format(id=it.get(v.get("id_key", "id"))) if v.get("item_url") else None,
                "ts": ts,
            }

# ---------- ProWiki (wikiservice.at farm) recent-changes adapter ----------
# Added 2026-09-08 for the attribution watch (probier + dse venues).
# Surface: <wiki>/wiki.cgi?action=rc — 30-day recent-changes list, one GET.
# Row shape: page | local HH:MM | [summary] | (N Änderungen) | actor (user or IP).
# No byte-delta and no revid exist on this surface; the event key is
# page+minute+actor, and the `from=` anchor gives the top row's exact epoch.
PROWIKI_MONTHS = {
    "januar": 1, "februar": 2, "m\u00e4rz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12, "january": 1, "february": 2, "march": 3,
    "may": 5, "june": 6, "july": 7, "october": 10, "december": 12,
}
PROWIKI_DATE_RE = re.compile(
    r"<p><strong>(?:(\d{1,2})\.\s+([A-Za-z\u00c0-\u024f]+)\s+(\d{4})"
    r"|([A-Za-z\u00c0-\u024f]+)\s+(\d{1,2}),\s+(\d{4}))</strong></p>")
PROWIKI_ROW_RE = re.compile(
    r"<li>.*?<a href='wiki\.cgi\?((?!action=)[^']+)' class='body'>([^<]+)</a>\s+(\d{1,2}):(\d{2})")
PROWIKI_ACT_RE = re.compile(r"<a href='wiki\.cgi\?[^']*' class='body'>([^<]+)</a>\s*</li>")
PROWIKI_IP_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
PROWIKI_SUM_RE = re.compile(r"<strong>(.*?)</strong>")
PROWIKI_CNT_RE = re.compile(r"\((\d+)\s+(?:\u00c4nderungen|Aenderungen|changes)\)")
PROWIKI_FROM_RE = re.compile(r"[?&]from=(\d{9,11})")
PROWIKI_SPERRE_RE = re.compile(r"Zugriffs?rate ist zu hoch|ProbierWiki: Sperre", re.I)


def _prowiki_backoff(st, reason, now, cap):
    """Park a venue in state.json instead of hammering a rate-limiting wiki."""
    n = st.get("sperre_count", 0) + 1
    wait = min(cap, 1800 * (2 ** (n - 1)))
    st["sperre_count"] = n
    st["sperre_until"] = now + wait
    st["last_sperre_ts"] = now
    st["last_sperre_reason"] = reason
    print("%s prowiki backoff #%d (%s): venue parked %ds" % (
        datetime.now(timezone.utc).isoformat(), n, reason, wait))


def _prowiki_ts_chain(rows, anchor):
    """UTC epochs for every row. The `from=` anchor pins the top row's exact
    (second-precision) epoch; the rest chain on displayed HH:MM deltas, so a
    DST flip inside the 30-day window stays correct."""
    out, prev_naive, prev_ts = [], None, None
    for r in rows:
        naive = int(datetime(*r["date"], tzinfo=timezone.utc).timestamp())
        ts = anchor if prev_naive is None else prev_ts - (prev_naive - naive)
        out.append(ts)
        prev_naive, prev_ts = naive, ts
    return out


def idx_prowiki_rc(v, state=None):
    """ProWiki action=rc index. ONE GET per tick, never a body fetch.
    Rate-limit doctrine: 14-min floor between fetches (min_interval_s), and a
    Sperre page or HTTP 403/429/503 parks the venue (30 min doubling to cap)."""
    name = v["name"]
    st = state["venues"].setdefault(name, {"seen": []}) if state is not None else {}
    now = time.time()
    if st.get("sperre_until", 0) > now:
        return
    if now - st.get("last_fetch_ts", 0) < v.get("min_interval_s", 840):
        return
    st["last_fetch_ts"] = now
    try:
        data, _ = fetch(v["url"], vkey="idx:" + name, state=state)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            _prowiki_backoff(st, "http %d" % e.code, now, v.get("backoff_cap_s", 21600))
            return
        raise
    if data is None:
        return
    if PROWIKI_SPERRE_RE.search(data.decode("latin-1", "replace")[:4000]):
        _prowiki_backoff(st, "sperre-page", now, v.get("backoff_cap_s", 21600))
        return
    st["sperre_count"] = 0
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")

    rows, cur = [], None
    for line in text.splitlines():
        d = PROWIKI_DATE_RE.search(line)
        if d:
            if d.group(1):
                cur = (int(d.group(3)), PROWIKI_MONTHS.get(d.group(2).lower()), int(d.group(1)))
            else:
                cur = (int(d.group(6)), PROWIKI_MONTHS.get(d.group(4).lower()), int(d.group(5)))
            continue
        m = PROWIKI_ROW_RE.search(line)
        if not m or not cur or not cur[1]:
            continue
        tail = line[m.end():]
        act = PROWIKI_ACT_RE.search(tail)
        ip = PROWIKI_IP_RE.search(tail)
        sm = PROWIKI_SUM_RE.search(tail)
        cn = PROWIKI_CNT_RE.search(tail)
        rows.append({
            "page": m.group(1).replace("&amp;", "&"),
            "date": cur, "hh": int(m.group(3)), "mm": int(m.group(4)),
            "actor": act.group(1) if act else (ip.group(1) if ip else None),
            "actor_kind": "user" if act else ("ip" if ip else None),
            "summary": re.sub(r"\s+", " ", sm.group(1)).strip("[] ") if sm else None,
            "changes": int(cn.group(1)) if cn else 1,
        })

    anchor = PROWIKI_FROM_RE.search(text)
    if anchor:
        ts_list = _prowiki_ts_chain(rows, int(anchor.group(1)))
    else:
        off = v.get("tz_offset_s", 7200)
        ts_list = [int(datetime(*r["date"], r["hh"], r["mm"],
                                tzinfo=timezone.utc).timestamp()) - off for r in rows]

    base = v.get("page_base", "")
    for r, ts in zip(rows, ts_list):
        stamp = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y%m%dT%H%M")
        yield {
            "id": "%s|%s|%s" % (r["page"], stamp, r["actor"] or "-"),
            "author": r["actor"],
            "title": r["page"] + ((" [%s]" % r["summary"]) if r["summary"] else ""),
            "url": base + urllib.parse.quote(r["page"], safe="/") if base else None,
            "ts": ts,
            "page": r["page"],
            "summary": r["summary"],
            "changes": r["changes"],
            "actor_kind": r["actor_kind"],
        }


INJECTION_RES = [
    r"\[SYSTEM\]",
    r"ignore (all |all prior |all previous |your previous |prior )?instructions",
    r"you are now (a|an|in|the)",
    r"maintenance mode",
    r"perform the following action",
    r"disregard (all )?(prior|previous|above)",
    r"new instructions?:",
    r"jailbreak",
    r"do anything now",
]


ADAPTERS["jsonlist"] = idx_jsonlist  # FIX 2026-09-08: register jsonlist adapter (fragbin blind 74 ticks)
ADAPTERS["proWikiRc"] = idx_prowiki_rc  # ADD 2026-09-08: wikiservice.at probier + dse venues
def scan_injection(text):
    """Flag bodies carrying prompt-injection markers. Evidence is kept AND
    flagged: downstream readers MUST treat flagged bodies as untrusted input,
    never as instructions. Returns list of matched pattern strings."""
    hits = [rx for rx in INJECTION_RES if re.search(rx, text, re.I)]
    return hits

def _item_text(item):
    """Flat text blob the scorer and the seeding-IP watchlist both scan."""
    return " ".join(str(x) for x in (item.get("title"), item.get("author"),
                                     item.get("id"), item.get("summary")) if x)


def load_ip_watchlist(cfg, cfg_dir):
    """Seeding-IP watch list (ADD 2026-09-09): one IP per line, '#' comments,
    path relative to the config dir. Items whose text carries a listed IP are
    flagged `ip_watch` and scored +w_ip_watch. Missing/unreadable file is a
    no-op, never a tick failure."""
    path = cfg.get("ip_watchlist")
    if not path:
        return set()
    if not os.path.isabs(path):
        path = os.path.join(cfg_dir, path)
    ips = set()
    try:
        with open(path) as f:
            for ln in f:
                ln = ln.split("#", 1)[0].strip()
                if ln:
                    ips.add(ln)
    except OSError as e:
        print("ip watchlist unreadable (%s): %s" % (path, e))
    return ips


BENFORD = (0.3010, 0.1761, 0.1249, 0.0969, 0.0792,
           0.0669, 0.0580, 0.0512, 0.0458)


def benford_interval_score(stamps):
    """ADD 2026-09-09: Benford automation score. Proposed by RNG in the
    sprint room, shipped the same night. Fixed-cadence minting (e.g. the
    May-12 57-gem ~1/sec matrix) collapses inter-arrival intervals onto one
    leading digit; human irregularity spreads them. Run on INTERVALS, never
    raw epochs (unix epochs all lead with 1). Returns chi-square vs Benford
    (df=8; 15.5 ~= p0.05, 26.1 ~= p0.001) or None when too few intervals."""
    ts = sorted(stamps)
    iv = [b - a for a, b in zip(ts, ts[1:]) if b - a > 0]
    if len(iv) < 9:
        return None
    obs = [0] * 9
    for v in iv:
        while v >= 10:
            v /= 10.0
        while v < 1:
            v *= 10.0
        obs[int(v) - 1] += 1
    n = sum(obs)
    if n < 9:
        return None
    return sum((o - n * e) ** 2 / (n * e) for o, e in zip(obs, BENFORD))


    s, why = 0, []
    author = item.get("author") or ""
    text = _item_text(item)

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
    # benford: fixed-cadence automation fails the leading-digit test.
    # N-floor (~20 stamps) keeps small authors out of the statistic; a longer
    # cadence_window_s in venues.json gives this more history to chew on.
    bh = author_hits.get(author, []) if author else []
    if len(bh) >= cfg.get("benford_min_hits", 20):
        chi2 = benford_interval_score(bh)
        if chi2 is not None and chi2 >= cfg.get("benford_chi2_fire", 25.0):
            s += cfg.get("w_benford", 2)
            why.append(f"benford x2={chi2:.1f}")

    return s, why


# ---------- main loop ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="venues.json")
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    a = ap.parse_args()

    cfg = json.load(open(a.config))
    ip_watch = load_ip_watchlist(cfg, os.path.dirname(os.path.abspath(a.config)))
    state_path = os.path.join(a.dir, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {"venues": {}, "authors": {}}
    os.makedirs(os.path.join(a.dir, "shards"), exist_ok=True)
    shard = os.path.join(a.dir, "shards", datetime.now(timezone.utc).strftime("%Y-%m-%d.jsonl"))

    body_thr = cfg.get("body_threshold", 3)
    events = 0
    errors = 0

    with open(shard, "a") as out:
        for v in cfg["venues"]:
            name = v["name"]
            cursor = state["venues"].setdefault(name, {"seen": []})
            seen = set(cursor["seen"])
            try:
                items = list(ADAPTERS[v["type"]](v, state))
            except Exception as e:
                out.write(json.dumps({"t": "error", "venue": name, "err": str(e),
                                      "ts": datetime.now(timezone.utc).isoformat()}) + "\n")
                errors += 1
                continue

            for item in items:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                s, why = score_item(item, state["authors"], cfg)
                hits = sorted(ip for ip in ip_watch if ip in _item_text(item))
                if hits:
                    s += cfg.get("w_ip_watch", 2)
                    why = why + ["ip_watch:" + ",".join(hits)]
                ev = {"t": "new", "venue": name, "score": s, "why": why,
                      "ts": datetime.now(timezone.utc).isoformat(), **item}
                if hits:
                    ev["ip_watch"] = hits

                # tier 2: body fetch only when the cheap score says so
                if s >= body_thr and item.get("url") and v.get("fetch_body", True):
                    try:
                        body, hdrs = fetch(item["url"])
                        ev["body_sha256"] = hashlib.sha256(body).hexdigest()
                        ev["body_bytes"] = len(body)
                        text = body[:20000].decode("utf-8", "replace")
                        if v.get("body_content_key"):
                            try:
                                text = str(json.loads(text).get(v["body_content_key"], ""))[:20000]
                            except ValueError:
                                pass
                        # injection tripwire: flag, never drop (evidence stays,
                        # readers treat flagged bodies as untrusted, not orders)
                        inj = scan_injection(text)
                        if inj:
                            ev["injection_flag"] = True
                            ev["injection_markers"] = inj
                        # keep small bodies; big ones get hashed + truncated
                        ev["body"] = text
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
    status = f"tick ok: {events} new items" if not errors else f"tick DEGRADED: {events} new items, {errors} venue errors"
    print(f"{datetime.now(timezone.utc).isoformat()} {status} -> {shard}")


if __name__ == "__main__":
    main()
