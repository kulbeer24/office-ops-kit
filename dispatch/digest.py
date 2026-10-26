#!/usr/bin/env python3
"""Morning digest: one short push per day at digest_hour. Reads cache/launch.json and cache/health.json. Prints nothing unless it is time; run_batch.sh calls it every loop."""
import os, json, time, subprocess
D = os.path.dirname(os.path.abspath(__file__))
def jl(p, d):
    try: return json.load(open(os.path.join(D, p)))
    except Exception: return d
conf = {}
try:
    for l in open(os.path.join(D, "push.conf")).read().splitlines():
        if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); conf[k.strip()] = v.strip()
except Exception: raise SystemExit
h = conf.get("digest_hour", "")
if conf.get("channel", "none") == "none" or not h.isdigit(): raise SystemExit
today = time.strftime("%Y%m%d"); stamp = os.path.join(D, "cache", "digest.day")
if time.localtime().tm_hour < int(h) or (os.path.exists(stamp) and open(stamp).read().strip() == today): raise SystemExit
L = jl("cache/launch.json", {}); H = jl("cache/health.json", {}); c = H.get("counts", {})
bits = []
if L: bits.append("%s: launch-ready %s vs %s (%s)." % (L.get("head", ""), L.get("chain_end", ""), L.get("target", ""), L.get("slack", "")))
bits.append("%d agents running, %d open PRs." % (c.get("slots", 0), c.get("open_prs", 0)))
bad = [i["text"] for i in H.get("items", []) if i.get("sev") in ("crit", "warn")][:2]
if bad: bits.append("Attention: " + " ".join(bad))
if L.get("need"): bits.append("%d item%s need you." % (L["need"], "" if L["need"] == 1 else "s"))
if L.get("ship"): bits.append(L["ship"])
open(stamp, "w").write(today)
subprocess.run([os.path.join(D, "push.sh"), "Morning summary", " ".join(bits)[:380], "digest"], timeout=20)
