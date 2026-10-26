#!/usr/bin/env python3
"""gh_events.py: write every PR and issue event on GitHub to dispatch/github.log (once each), so the Activity log shows
merges, closes and new PRs no matter who did them (owner, orchestrator, dispatcher). Called by run_batch.sh; at most once a minute."""
import os, json, subprocess, time, datetime
D = os.path.dirname(os.path.abspath(__file__)); R = "__REPO__"
C = os.path.join(D, "cache"); os.makedirs(C, exist_ok=True)
stamp = os.path.join(C, "ghevents.stamp")
if os.path.exists(stamp) and time.time() - os.path.getmtime(stamp) < 60: raise SystemExit
open(stamp, "w").close()

def gh(args):
    try: return json.loads(subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=40).stdout)
    except Exception: return None

keyf = os.path.join(C, "ghevents.keys")
seen = set(open(keyf).read().split("\n")) if os.path.exists(keyf) else set()
first = not os.path.exists(keyf)
cut = (datetime.datetime.utcnow() - datetime.timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
new = []
def ev(key, ts, text):
    if not ts or key in seen: return
    seen.add(key)
    if not first or ts >= cut: new.append((ts, text))

prs = gh(["pr", "list", "--repo", R, "--state", "all", "-L", "60", "--json", "number,title,state,createdAt,mergedAt,closedAt,mergedBy,headRefName"])
for p in prs or []:
    n, t = p["number"], p["title"]
    ev(f"pr-open-{n}", p.get("createdAt"), f"PR #{n} opened: {t} ({p.get('headRefName', '')})")
    if p.get("mergedAt"):
        who = (p.get("mergedBy") or {}).get("login", "?")
        ev(f"pr-merge-{n}", p["mergedAt"], f"PR #{n} merged by {who}: {t}")
    elif p.get("state") == "CLOSED":
        ev(f"pr-close-{n}", p.get("closedAt"), f"PR #{n} closed without merging: {t}")
iss = gh(["issue", "list", "--repo", R, "--state", "all", "-L", "80", "--json", "number,title,state,createdAt,closedAt"])
for i in iss or []:
    n, t = i["number"], i["title"]
    ev(f"is-open-{n}", i.get("createdAt"), f"Issue #{n} opened: {t}")
    if i.get("state") == "CLOSED": ev(f"is-close-{n}", i.get("closedAt"), f"Issue #{n} closed: {t}")

if prs is not None and iss is not None:
    open(keyf, "w").write("\n".join(sorted(seen)))
    if new:
        with open(os.path.join(D, "github.log"), "a") as f:
            for ts, text in sorted(new): f.write(f"- {ts} {text}\n")
