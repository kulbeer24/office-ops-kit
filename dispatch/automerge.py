#!/usr/bin/env python3
"""automerge.py: merges PRs the architect has approved ('ready to merge' lines in owner_hold.txt), and logs each merge.
OFF unless automerge.conf says enabled=1. A plain script, not an AI agent. A PR merges only if all hold:
 the open head commit is the one the architect approved, GitHub says it is mergeable, no check is failing or pending,
 and the PR does not touch CLAUDE.md or other owner-only files. Anything else is left alone and logged once."""
import os, re, json, subprocess, time, datetime
D = os.path.dirname(os.path.abspath(__file__)); R = "__REPO__"
OWNER_ONLY = ("CLAUDE.md", ".github/", "01-vision/architecture.md")
def now(): return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
def log(t): open(os.path.join(D, "orchestrator-log.md"), "a").write(f"- {now()} (architect run) {t}\n")
try: on = "enabled=1" in open(os.path.join(D, "automerge.conf")).read().replace(" ", "")
except Exception: on = False
if not on: raise SystemExit
C = os.path.join(D, "cache"); os.makedirs(C, exist_ok=True)
st = os.path.join(C, "automerge.stamp")
if os.path.exists(st) and time.time() - os.path.getmtime(st) < 120: raise SystemExit
open(st, "w").close()
def gh(a):
    r = subprocess.run(["gh"] + a, capture_output=True, text=True, timeout=60); return r.returncode, r.stdout, r.stderr
hp = os.path.join(D, "owner_hold.txt"); lines = open(hp).read().split("\n")
sk = os.path.join(C, "automerge.skipped"); skipped = set(open(sk).read().split("\n")) if os.path.exists(sk) else set()
keep = []; merged = []
def skip(pr, sha, why):
    k = f"{pr}-{sha}-{why}"
    if k not in skipped: skipped.add(k); log(f"PR #{pr} approved at {sha} but not auto-merged: {why}")
for ln in lines:
    m = re.match(r"^(\d+)\s+#\s*ready to merge \(architect approved ([0-9a-f]{7,40})\)", ln)
    if not m: keep.append(ln); continue
    pr, sha = m.group(1), m.group(2)
    rc, out, _ = gh(["pr", "view", pr, "--repo", R, "--json", "state,headRefOid,mergeable,statusCheckRollup,files,title"])
    try: p = json.loads(out)
    except Exception: keep.append(ln); continue
    if p["state"] != "OPEN": merged.append(pr); continue          # already merged or closed by someone else: drop the hold line
    head = p["headRefOid"]
    if not head.startswith(sha): skip(pr, sha, "new commits since approval; waits for the architect to re-review"); keep.append(ln); continue
    if p.get("mergeable") != "MERGEABLE": skip(pr, sha, f"GitHub says {p.get('mergeable')}"); keep.append(ln); continue
    checks = p.get("statusCheckRollup") or []
    bad = [c for c in checks if (c.get("conclusion") or c.get("state") or "").upper() not in ("SUCCESS", "NEUTRAL", "SKIPPED")]
    if bad: skip(pr, sha, "checks not all green yet"); keep.append(ln); continue
    if any(f["path"].startswith(OWNER_ONLY) for f in p.get("files", [])): skip(pr, sha, "touches an owner-only file"); keep.append(ln); continue
    rc, out, err = gh(["pr", "merge", pr, "--repo", R, "--merge", "--match-head-commit", head])
    if rc == 0:
        merged.append(pr); log(f"PR #{pr} merged automatically after architect approval ({sha}): {p['title']}")
    else: skip(pr, sha, "merge refused: " + (err.strip().splitlines() or ["unknown"])[-1][:120]); keep.append(ln)
open(hp + ".tmp", "w").write("\n".join(keep)); os.replace(hp + ".tmp", hp)
open(sk, "w").write("\n".join(sorted(skipped)))
