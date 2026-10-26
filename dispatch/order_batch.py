#!/usr/bin/env python3
"""Prints batch.txt entries in the order the dispatcher should start them: fix-/qa- jobs first (batch order), then feature work by the
Prioritise tab rank (P0, P1, P2, Parked), then anything unranked in batch order. Also writes cache/next.json with the reason for each entry.
No tokens, no network. run_batch.sh falls back to plain batch order if this fails."""
import json, os, re
D = os.path.dirname(os.path.abspath(__file__))
def jl(p, d):
    try: return json.load(open(os.path.join(D, p)))
    except Exception: return d
try: lines = [l.strip() for l in open(os.path.join(D, "batch.txt")).read().splitlines()]
except Exception: lines = []
names = []
for l in lines:
    if l and not l.startswith("#") and l not in names: names.append(l)
pr = jl("priorities.json", {}) or {}
tiers = pr.get("tiers", {}); pos = {str(n): i for i, n in enumerate(pr.get("order", []))}
RANK = {"P0": 0, "P1": 1, "P2": 2, "Parked": 3}
def key(item):
    i, n = item
    if n.startswith(("fix-", "qa-")): return (0, 0, i, i)
    t = tiers.get(n)
    if t in RANK: return (1, RANK[t], pos.get(n, 9999), i)
    return (2, 0, i, i)
ordered = [n for _, n in sorted(enumerate(names), key=key)]
why = {}
for k, n in enumerate(ordered):
    if n.startswith(("fix-", "qa-")): why[n] = "review work goes first"
    elif tiers.get(n) in RANK: why[n] = "%s, rank %d on the Prioritise list" % (tiers[n], pos.get(n, 0) + 1)
    else: why[n] = "not ranked yet; runs after ranked work"
try:
    tmp = os.path.join(D, "cache", "next.json.tmp"); json.dump({"order": ordered, "why": why}, open(tmp, "w")); os.replace(tmp, os.path.join(D, "cache", "next.json"))
except Exception: pass
print("\n".join(ordered))
