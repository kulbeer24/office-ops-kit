#!/usr/bin/env python3
"""No-token auto-queue. Run by run_batch.sh every loop while dev is ON. Reads dispatch/priorities.json (saved from the grooming tab) and, when the queue has
room, appends the top-ranked 'P0' then 'P1' open issue that is not already running, queued or in review. Never queues fix-/qa- work (the architect does that)."""
import json, os, re, time, datetime
D = os.path.dirname(os.path.abspath(__file__))
def jl(p, d):
    try: return json.load(open(os.path.join(D, p)))
    except Exception: return d
pr = jl("priorities.json", None)
if not pr: raise SystemExit
tiers, order = pr.get("tiers", {}), [str(x) for x in pr.get("order", [])]
deps = jl("deps.json", {})
openn = {str(i["number"]) for i in jl("cache/issues_live.json", []) if i.get("state") == "OPEN"} or {str(i["number"]) for i in jl("cache/open_issues.json", [])}
started = set(os.listdir(os.path.join(D, "started"))) if os.path.isdir(os.path.join(D, "started")) else set()
done = set(os.listdir(os.path.join(D, "done"))) if os.path.isdir(os.path.join(D, "done")) else set()
batch_lines = [l.strip() for l in open(os.path.join(D, "batch.txt")).read().splitlines()] if os.path.exists(os.path.join(D, "batch.txt")) else []
batch = {l for l in batch_lines if l and not l.startswith("#")}
prs = jl("cache/prs_live.json", None) or jl("cache/prs.json", [])
inpr = {m.group(1) for p in prs if p.get("state", "OPEN") == "OPEN" for m in [re.match(r"(\d+)-", p.get("headRefName", ""))] if m}
waiting = [n for n in batch if n not in started and re.fullmatch(r"\d+", n)]
running = [n for n in started if n not in done and re.fullmatch(r"\d+", n)]
if len(waiting) + len(running) >= 3: raise SystemExit      # slots are the limit; keep at most one waiting beyond what runs
for want in ("P0", "P1"):
    for n in order:
        if tiers.get(n) != want or n not in openn or n in started or n in batch or n in inpr: continue
        if any(d in openn for d in deps.get(n, [])): continue   # a prerequisite is not merged yet
        with open(os.path.join(D, "batch.txt"), "a") as f: f.write(("" if not batch_lines or batch_lines[-1] == "" else "\n") + n + "\n")
        with open(os.path.join(D, "status.md"), "a") as f: f.write(f"- autoqueue #{n} ({want}, from the grooming list) {datetime.datetime.utcnow().isoformat(timespec='seconds')}Z\n")
        raise SystemExit
