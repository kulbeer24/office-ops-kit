#!/usr/bin/env python3
"""No-AI gap filler for the architect review. Run by run_batch.sh every loop (~20s, before the requeue step).
Does ONLY the mechanical hand-off: when a fix agent has finished on an open PR that was already in QA (or that the architect said to QA after the fix),
queue the QA re-check straight away instead of waiting for the next architect run. Respects the 2-round QA cap. Never merges, never decides tier, never writes fixes/*.txt (those need judgement)."""
import json, os, re, glob, time, datetime
D = os.path.dirname(os.path.abspath(__file__))
def P(*a): return os.path.join(D, *a)
def jl(p, d):
    try: return json.load(open(P(p)))
    except Exception: return d
def mt(p):
    try: return os.path.getmtime(P(p))
    except Exception: return 0
if os.path.exists(P("PAUSED")) or os.path.exists(P("LIMIT_HIT")): raise SystemExit
prs = jl("cache/prs.json", [])
batch = [l.strip() for l in open(P("batch.txt")).read().splitlines()] if os.path.exists(P("batch.txt")) else []
log = open(P("orchestrator-log.md")).read() if os.path.exists(P("orchestrator-log.md")) else ""
def pending(n): return n in batch and not os.path.exists(P("started", n))   # waiting its turn (stale batch lines of finished jobs do not count)
def running(n): return os.path.exists(P("started", n)) and not os.path.exists(P("done", n)) and not os.path.exists(P("retries", n + ".gaveup"))
for p in prs:
    m = re.match(r"(\d+)-", p.get("headRefName", ""))
    if not m: continue
    iss, pr = m.group(1), str(p["number"]); fx, qa = "fix-" + iss, "qa-" + pr
    if not os.path.exists(P("done", fx)) or running(fx) or pending(fx): continue
    try:
        if "no QA round follows" in open(P("fixes", iss + ".txt")).read(): continue   # cleanup-only final round (owner: ship the story): never queue another QA
    except Exception: pass
    if pending(qa) or running(qa) or os.path.exists(P("requeue", qa)): continue
    fdone, qdone = mt("done/" + fx), mt("done/" + qa)
    if qdone > fdone: continue                                   # QA already looked after the last fix: the architect decides next
    arch = len(glob.glob(P("qa-history", "qa-%s-round*" % pr)))
    cur = 1 if qdone and qdone > max([mt(f) for f in glob.glob(P("qa-history", "qa-%s-round*" % pr))] or [0]) else 0
    if arch + cur >= 3: continue                                 # QA cap reached: owner/architect call
    hinted = re.search(r"PR #%s\b[^\n]*(qa-%s[^\n]*to (be )?queue|queue qa-%s)" % (pr, pr, pr), log, re.I)
    if not (arch or qdone or hinted): continue                   # never QA'd and architect did not ask for it: leave to the architect
    os.makedirs(P("requeue"), exist_ok=True); open(P("requeue", qa), "w").close()
    with open(P("batch.txt"), "a") as f: f.write(("" if not batch or batch[-1] == "" else "\n") + qa + "\n")
    t = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    open(P("status.md"), "a").write("- autoreview queued %s (fix finished on PR #%s) %s\n" % (qa, pr, t))
    open(P("orchestrator-log.md"), "a").write("- %s (auto, no AI) PR #%s: %s finished, queued %s (QA round %d of 3). Not merged.\n" % (t, pr, fx, qa, arch + cur + 1))
    batch.append(qa)
