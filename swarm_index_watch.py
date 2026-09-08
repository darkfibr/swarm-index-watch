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

def idx_jsonlist(v, state=None):
    """JSON list API (e.g. fragbin /api/pastes?page=N). Paginates v['pages'] pages.
    Field names configurable via id_key/title_key/ts_key."""
    for page in range(1, v.get("pages", 1) + 1):
        data, _ = fetch(v["url"].format(page=page),
                        vkey="idx:%s:p%d" % (v["name"], page), state=state)
        if data is None:
            continue
        items = json.loads(data).get(v.get("items_key", "items"), [])
        for it in items:
            ts = None
            raw_ts = it.get(v.get("ts_key", "")) if v.get("ts_key") else None
            if raw_ts:
                try:
                    ts = int(datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00")).timestamp())
                except ValueError:
                    pass
            yield {
                "id": str(it.get(v.get("id_key", "id"))),
                "author": it.get(v.get("author_key", "")),
                "title": it.get(v.get("title_key", "title")),
                "url": v["item_url"].format(id=it.get(v.get("id_key", "id"))) if v.get("item_url") else None,
                "ts": ts,
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


def scan_injection(text):
    """Flag bodies carrying prompt-injection markers. Evidence is kept AND
    flagged: downstream readers MUST treat flagged bodies as untrusted input,
    never as instructions. Returns list of matched pattern strings."""
    hits = [rx for rx in INJECTION_RES if re.search(rx, text, re.I)]
    return hits


ADAPTERS["jsonlist"] = idx_jsonlist  # registration dropped by 77c4cd0; restored


# ---------- UseModWiki / ProWiki / Oddmuse: the CGI wikis that hosted the 2026 swarm ----------
# These engines have no JSON API. RecentChanges is an HTML list:
#   <p><strong>September 6, 2026</strong></p> <ul>
#   <li><a href="...diff...">(diff)</a> <a href="wiki.pl?PageName">PageName</a> 16:59
#       <strong>[summary]</strong> . . . . . AuthorOrIp</li>
# ProWiki emits German date headers ("7. September 2026") and 24h times; UseMod
# emits English headers and either "7:44 pm" or "16:59". Oddmuse uses the same
# shape with extra markup. There is no revision id, so the item id is a hash of
# (page, date, time, author) — stable across ticks, distinct per edit.
_MONTHS = {m: i + 1 for i, m in enumerate(
    "january february march april may june july august september october november december".split())}
_MONTHS.update({"märz": 3, "mai": 5, "juni": 6, "juli": 7, "oktober": 10, "dezember": 12})
_RC_DATE_RE = re.compile(r"<strong>\s*(?:(\d{1,2})\.\s*)?([A-Za-zäÄ]+)\s+(\d{1,2})?,?\s*(\d{4})\s*</strong>", re.I)
_RC_ROW_RE = re.compile(
    r"<li>.*?\(diff\)</a>\s*<a href=['\"](?P<href>[^'\"]+)['\"][^>]*>(?P<page>[^<]+)</a>\s*"
    r"(?P<time>\d{1,2}:\d{2}(?:\s*[ap]m)?)\s*(?P<rest>.*?)(?:</li>|(?=<li>)|(?=</ul>))", re.I | re.S)
_RC_SUMMARY_RE = re.compile(r"<strong>\[(?P<s>.*?)\]</strong>", re.S)


def _rc_date(m):
    day = m.group(1) or m.group(3)
    mon = _MONTHS.get(m.group(2).lower())
    if not (day and mon):
        return None
    return int(m.group(4)), mon, int(day)


def _rc_ts(date, t, utc_offset_h=0):
    """These engines print server-local wall time (ProWiki: Vienna). Pass the
    venue's utc_offset_h so ts is real UTC; default 0 keeps the naive reading."""
    if not date:
        return None
    t = t.strip().lower()
    hh, mm = t.replace("am", "").replace("pm", "").strip().split(":")
    hh, mm = int(hh), int(mm)
    if t.endswith("pm") and hh < 12:
        hh += 12
    if t.endswith("am") and hh == 12:
        hh = 0
    y, mo, d = date
    return int(datetime(y, mo, d, hh, mm, tzinfo=timezone.utc).timestamp()) - int(utc_offset_h * 3600)


def idx_usemod(v, state=None):
    """UseModWiki / ProWiki / Oddmuse RecentChanges (action=rc). Read-only GET.
    Config: url (the rc listing), optional page_base for item urls,
    optional utc_offset_h (server-local clock offset, e.g. 2 for CEST)."""
    data, _ = fetch(v["url"], vkey="idx:" + v.get("name", v["url"]), state=state)
    if data is None:
        return
    text = data.decode("utf-8", "replace") if b"utf-8" in data[:2000].lower() \
        else data.decode("latin-1")
    date = None
    pos = 0
    events = [(m.start(), "d", m) for m in _RC_DATE_RE.finditer(text)]
    events += [(m.start(), "r", m) for m in _RC_ROW_RE.finditer(text)]
    for _, kind, m in sorted(events, key=lambda e: e[0]):
        if kind == "d":
            date = _rc_date(m)
            continue
        page = m.group("page").strip()
        rest = m.group("rest")
        sm = _RC_SUMMARY_RE.search(rest)
        summary = re.sub(r"<[^>]+>", "", sm.group("s")).strip() if sm else ""
        tail = re.sub(r"<[^>]+>", " ", rest)
        tail = tail.split(". . .")[-1] if ". . ." in tail else tail
        author = tail.strip().split()[-1] if tail.strip() else None
        ts = _rc_ts(date, m.group("time"), v.get("utc_offset_h", 0))
        key = f"{page}|{date}|{m.group('time').strip()}|{author}"
        yield {
            "id": "rc" + hashlib.sha1(key.encode()).hexdigest()[:12],
            "author": author,
            "title": f"{page} [{summary}]" if summary else page,
            "url": (v.get("page_base") or "") + urllib.parse.quote(page, safe="/") if v.get("page_base") else None,
            "ts": ts,
        }


ADAPTERS["usemod"] = idx_usemod



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

    # cadence: same author hitting repeatedly inside the window. Measured on the
    # item's own timestamp when the venue gives one, so a first tick over a
    # 30-day listing does not read all of history as "the last hour".
    now = item.get("ts") or time.time()
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
                items = list(ADAPTERS[v["type"]](v, state))
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
                    state["authors"].setdefault(item["author"], []).append(item.get("ts") or time.time())

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
