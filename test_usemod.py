#!/usr/bin/env python3
"""Mock-venue test for the usemod adapter: UseMod (English, am/pm), ProWiki (German, 24h)."""
import swarm_index_watch as W

USEMOD = """<p><strong>September 6, 2026</strong></p> <ul>
<li><a href="wiki.pl?action=browse&amp;diff=1&amp;id=PublicBoard">(diff)</a> <a href="wiki.pl?PublicBoard" class="wikipagelink">PublicBoard</a> 16:59 <strong>[Spam]</strong> . . . . . <a href="wiki.pl?Meow" title="ID 108833">Meow</a>
<li><a href="wiki.pl?action=browse&amp;diff=1&amp;id=PublicBoard">(diff)</a> <a href="wiki.pl?PublicBoard" class="wikipagelink">PublicBoard</a> 08:14 <strong>[Public Board announcement]</strong> . . . . . 159.146.96.208
<li><a href="wiki.pl?id=APoc&action=browse&diff=1">(diff)</a> <a href="wiki.pl?APoc">APoc</a> 7:44 pm <strong>[Comment]</strong> . . . . . 212.11.62.xxx </UL>"""
PROWIKI = """<p><strong>7. September 2026</strong></p> <ul>
<li><a href='wiki.cgi?action=browse&amp;diff=4&amp;id=Agent010LeminoDirect1781807025' class='body' rel='nofollow'>(diff)</a> <a href='wiki.cgi?Agent010LeminoDirect1781807025' class='body'>Agent010LeminoDirect1781807025</a> 21:52 <strong>[agent010]</strong> . . . . . 52.44.229.124</li>
<li><a href='wiki.cgi?action=browse&amp;diff=4&amp;id=OrdnerOrdner' class='body' rel='nofollow'>(diff)</a> <a href='wiki.cgi?OrdnerOrdner' class='body'>OrdnerOrdner</a> 21:52 . . . . . 44.215.210.112</li></ul>"""

def run(html, enc="utf-8"):
    W.fetch = lambda url, timeout=20, **kw: (html.encode(enc), {})
    return list(W.idx_usemod({"url": "x", "page_base": "https://ex/wiki.cgi?"}))

u = run(USEMOD)
assert [i["author"] for i in u] == ["Meow", "159.146.96.208", "212.11.62.xxx"], u
assert u[0]["title"] == "PublicBoard [Spam]"
assert u[0]["ts"] == 1788713940, u[0]["ts"]          # 2026-09-06 16:59Z
assert u[2]["ts"] == 1788723840, u[2]["ts"]          # 19:44Z from "7:44 pm"
assert len({i["id"] for i in u}) == 3
p = run(PROWIKI, "latin-1")
assert p[0]["author"] == "52.44.229.124" and p[0]["ts"] == 1788817920, p[0]
assert p[0]["url"] == "https://ex/wiki.cgi?Agent010LeminoDirect1781807025"
W.fetch = lambda url, timeout=20, **kw: (PROWIKI.encode("latin-1"), {})
q = list(W.idx_usemod({"url": "x", "utc_offset_h": 2}))
assert q[0]["ts"] == 1788817920 - 7200, q[0]["ts"]   # 21:52 CEST -> 19:52Z
cfg = {"grammar_regexes": [r"\bagent[-_]?\d{3,}\b", r"(?:[A-Z][a-z]+){0,3}Agent[A-Z0-9][A-Za-z0-9]*"]}
s, why = W.score_item(p[0], {}, cfg)
assert s == 2 and why == ["grammar"], (s, why)  # epoch int is glued to the handle, so EPOCH_RE (word-bounded) stays quiet
s2, _ = W.score_item(p[1], {}, cfg)
assert s2 == 0
W.fetch = lambda url, timeout=20, **kw: (None, {})
assert list(W.idx_usemod({"url": "x", "name": "n"})) == []   # 304 Not Modified -> no items
print("usemod adapter: ok", len(u), len(p))
