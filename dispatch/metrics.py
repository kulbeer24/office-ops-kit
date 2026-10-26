#!/usr/bin/env python3
"""Per-issue delivery metrics for the status page. Run by run_batch.sh about every 5 minutes (cheap, no network).
Reads: dispatch/status.md (STARTED/DONE lines), dispatch/metrics.ends (end timestamps, written by agent.sh from now on),
dispatch/done/* (fallback end time), dispatch/cache/prs_all.json (PR -> issue), agent transcripts under ~/.claude/projects
(token usage; override the folder with CLAUDE_PROJECTS for tests).
Writes: dispatch/metrics/summary.json (the status page reads it), dispatch/metrics/issues.csv, dispatch/metrics/projections.json.
Never writes anywhere else. Token figures are 'new' = input + output + cache-writes, and 'cached' = cache re-reads (cheap)."""
import os, re, json, glob, time, statistics, datetime
D = os.path.dirname(os.path.abspath(__file__)); M = os.path.join(D, "metrics"); os.makedirs(M, exist_ok=True)
CP = os.environ.get("CLAUDE_PROJECTS") or os.path.expanduser("~/.claude/projects")
NOW = time.time()

def ts(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception: return None
def jload(p, d):
    try: return json.load(open(p))
    except Exception: return d

# ---- 1. runs from status.md ------------------------------------------------------------
ends = {}  # agent -> [epoch,...]
for ln in open(os.path.join(D, "metrics.ends")).read().splitlines() if os.path.exists(os.path.join(D, "metrics.ends")) else []:
    p = ln.split("|")
    if len(p) >= 2 and ts(p[1]): ends.setdefault(p[0], []).append(ts(p[1]))
runs, openrun = [], {}
for ln in open(os.path.join(D, "status.md")).read().splitlines() if os.path.exists(os.path.join(D, "status.md")) else []:
    m = re.match(r"- #(\S+) STARTED (\S+)", ln)
    if m:
        r = {"agent": m.group(1), "start": ts(m.group(2)), "end": None, "result": ""}; runs.append(r); openrun[m.group(1)] = r; continue
    m = re.match(r"- #(\S+) DONE: (.*)", ln)
    if m and m.group(1) in openrun:
        r = openrun.pop(m.group(1)); r["result"] = m.group(2)
        later = sorted(e for e in ends.get(r["agent"], []) if r["start"] and e >= r["start"] and e < 1e12)
        r["end"] = later[0] if later else None
        if r["end"]: ends[r["agent"]].remove(r["end"])
        continue
# fallback end time: the done-file mtime, only for the newest run of an agent and only when plausible
latest = {}
for r in runs: latest[r["agent"]] = r
for a, r in latest.items():
    f = os.path.join(D, "done", a)
    if r["end"] is None and r["result"] and os.path.exists(f):
        mt = os.path.getmtime(f)
        if r["start"] and r["start"] < mt < r["start"] + 12 * 3600: r["end"] = mt

# ---- 2. PR -> issue ---------------------------------------------------------------------
pr2iss = {}
try:   # the architect log names the issue each PR closes: "PR #248 (#242, ..."
    for a, b in re.findall(r"PR #(\d+) \(#(\d+)", open(os.path.join(D, "orchestrator-log.md")).read()): pr2iss[a] = b
except Exception: pass
for f in ("prs_all.json", "prs.json", "prs_live.json"):
    for p in jload(os.path.join(D, "cache", f), []):
        mm = re.match(r"(\d+)-", p.get("headRefName", ""))
        if mm: pr2iss[str(p["number"])] = mm.group(1)
def kind_issue(a):
    if a.startswith("fix-"): return "fix", a[4:]
    if a.startswith("qa-"): return "qa", pr2iss.get(a[3:], a[3:])
    return "dev", a

# ---- 3. tokens from agent transcripts ----------------------------------------------------
def project_dirs(agent):
    k, iss = kind_issue(agent)
    suf = f"__SLUG__-wt-{iss}" if k == "dev" else f"__SLUG__-wt-pr-{iss}"
    out = [d for d in glob.glob(os.path.join(CP, "*")) if os.path.basename(d).endswith(suf)]
    if k == "dev": out += [d for d in glob.glob(os.path.join(CP, "*")) if os.path.basename(d).endswith(f"__SLUG__-wt-pr-{iss}")]
    return out
def tokens(run):
    if not os.path.isdir(CP) or not run["start"]: return None
    lo, hi = run["start"] - 30, run["win_end"] + 30; best = {}
    for d in project_dirs(run["agent"]):
        for f in glob.glob(os.path.join(d, "*.jsonl")):
            if os.path.getmtime(f) < lo: continue
            try:
                for ln in open(f, errors="ignore"):
                    if '"usage"' not in ln: continue
                    try: o = json.loads(ln)
                    except Exception: continue
                    t = ts(o.get("timestamp", "")) if isinstance(o.get("timestamp"), str) else None
                    msg = o.get("message") or {}; u = msg.get("usage")
                    if not u or t is None or not (lo <= t <= hi): continue
                    key = msg.get("id") or o.get("uuid") or (f, ln[:80])
                    new = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
                    if key not in best or new >= best[key][0]: best[key] = (new, u.get("cache_read_input_tokens") or 0)
            except Exception: continue
    if not best: return None
    return {"new": sum(v[0] for v in best.values()), "cached": sum(v[1] for v in best.values())}
cache_f = os.path.join(M, "tokens_cache.json"); tc = jload(cache_f, {})
for r in runs: r["kind"], r["issue"] = kind_issue(r["agent"])
byiss = {}
for r in runs: byiss.setdefault(r["issue"], []).append(r)
for lst in byiss.values():   # a run's window ends at its own end, the next run on the same issue, or 12 hours; so restarts never double count
    lst.sort(key=lambda x: x["start"] or 0)
    for k, r in enumerate(lst):
        nxt = lst[k + 1]["start"] if k + 1 < len(lst) else NOW
        r["win_end"] = min(r["end"] or NOW, nxt or NOW, (r["start"] or 0) + 12 * 3600)
for r in runs:
    key = f'{r["agent"]}|{int(r["start"] or 0)}'
    if key in tc: r["tokens"] = tc[key]; continue
    r["tokens"] = tokens(r)
    if r["end"] and r["tokens"] and r["win_end"] < NOW - 3600: tc[key] = r["tokens"]   # finished runs never change, so cache them
json.dump(tc, open(cache_f, "w"))

# ---- 4. aggregate per issue ---------------------------------------------------------------
iss = {}
for r in runs:
    i = iss.setdefault(r["issue"], {"issue": r["issue"], "dev_s": 0, "qa_s": 0, "fix_s": 0, "qa_rounds": 0, "fix_rounds": 0, "findings": 0,
                                    "flog": [], "new": 0, "cached": 0, "tok_known": False, "first": r["start"], "last": r["start"], "open": 0, "unknown_time": 0, "restarts": 0})
    dur = (r["end"] - r["start"]) if r["end"] and r["start"] else None
    if dur is not None: i[r["kind"] + "_s"] += dur
    elif r["result"]: i["unknown_time"] += 1
    elif r is latest[r["agent"]] and not os.path.exists(os.path.join(D, "done", r["agent"])): i["open"] += 1
    else: i["restarts"] += 1
    if r["kind"] == "qa" and r["result"]:
        i["qa_rounds"] += 1; mm = re.search(r"(\d+) findings", r["result"]); i["findings"] += int(mm.group(1)) if mm else 0; i["flog"].append([r["end"] or r["start"], int(mm.group(1)) if mm else 0])
    if r["kind"] == "fix" and r["result"]: i["fix_rounds"] += 1
    if r["tokens"]: i["new"] += r["tokens"]["new"]; i["cached"] += r["tokens"]["cached"]; i["tok_known"] = True
    if r["start"]: i["first"] = min(i["first"] or r["start"], r["start"])
    i["last"] = max(i["last"] or 0, r["end"] or r["start"] or 0)
rows = sorted(iss.values(), key=lambda x: -(x["last"] or 0))

# ---- 5. medians and projections -----------------------------------------------------------
def med(kind):
    v = [(r["end"] - r["start"]) / 60 for r in runs if r["kind"] == kind and r["end"] and r["start"] and 2 <= (r["end"] - r["start"]) / 60 <= 600]
    return round(statistics.median(v), 1) if v else None
meds = {k: med(k) for k in ("dev", "qa", "fix")}
done_iss = [i for i in rows if i["dev_s"] and i["qa_rounds"]]
avg_rounds = round(sum(i["qa_rounds"] for i in done_iss) / len(done_iss), 1) if done_iss else 2.0
tok_runs = [r["tokens"]["new"] for r in runs if r["tokens"] and r["end"] and r["kind"] == "dev"]
proj_f = os.path.join(M, "projections.json"); proj = jload(proj_f, {})
batch = [l.strip() for l in open(os.path.join(D, "batch.txt")).read().splitlines() if l.strip() and not l.startswith("#")] if os.path.exists(os.path.join(D, "batch.txt")) else []
if all(meds.values()):
    for a in batch:
        k, n = kind_issue(a)
        if k == "dev" and n not in proj and n not in iss:
            proj[n] = {"minutes": round(meds["dev"] + avg_rounds * (meds["qa"] + meds["fix"])), "on": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                       "basis": f"typical dev {meds['dev']}m + {avg_rounds} x (QA {meds['qa']}m + fix {meds['fix']}m)"}
# Planned estimates for the whole backlog (estimates.txt: issue | size | minutes | note). Frozen the first time they are seen, like the queue-time ones above.
est_f = os.path.join(D, "estimates.txt")
if os.path.exists(est_f):
    for l in open(est_f).read().splitlines():
        if not l.strip() or l.lstrip().startswith("#"): continue
        try: n_, sz_, mn_, nt_ = [x.strip() for x in (l.split("|") + ["", "", ""])[:4]]; mn_ = int(mn_)
        except Exception: continue
        if n_ and n_ not in proj:
            proj[n_] = {"minutes": mn_, "on": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "basis": f"size {sz_}: {nt_}"}
json.dump(proj, open(proj_f, "w"), indent=1)

# ---- 6. write -----------------------------------------------------------------------------
out = []
for i in rows:
    act = (i["dev_s"] + i["qa_s"] + i["fix_s"]) / 60
    out.append({"issue": i["issue"], "dev_min": round(i["dev_s"] / 60), "qa_min": round(i["qa_s"] / 60), "fix_min": round(i["fix_s"] / 60),
                "active_min": round(act), "qa_rounds": i["qa_rounds"], "fix_rounds": i["fix_rounds"], "findings": i["findings"], "findings_log": i["flog"],
                "tokens_new": i["new"] if i["tok_known"] else None, "tokens_cached": i["cached"] if i["tok_known"] else None,
                "elapsed_min": round((i["last"] - i["first"]) / 60) if i["first"] and i["last"] else None, "first_ts": int(i["first"]) if i["first"] else None,
                "projected_min": (proj.get(i["issue"]) or {}).get("minutes"), "running": i["open"], "restarts": i["restarts"], "time_unknown_runs": i["unknown_time"]})
_seen = {o["issue"] for o in out}
_planned_only = [{"issue": n_, "dev_min": 0, "qa_min": 0, "fix_min": 0, "active_min": 0, "qa_rounds": 0, "fix_rounds": 0, "findings": 0, "findings_log": [],
                  "tokens_new": None, "tokens_cached": None, "elapsed_min": None, "first_ts": None, "projected_min": v_.get("minutes"), "running": 0, "restarts": 0,
                  "time_unknown_runs": 0, "backlog": 1} for n_, v_ in proj.items() if n_ not in _seen]
fb = len(glob.glob(os.path.join(D, "inbox", "done", "fb-*.number")))
tot = {"issues": len(out), "findings": sum(o["findings"] for o in out), "tester_issues": fb, "qa_rounds": sum(o["qa_rounds"] for o in out),
       "fix_rounds": sum(o["fix_rounds"] for o in out), "active_min": sum(o["active_min"] for o in out),
       "tokens_new": sum(o["tokens_new"] or 0 for o in out), "tokens_known_for": sum(1 for o in out if o["tokens_new"] is not None),
       "median_dev_tokens": int(statistics.median(tok_runs)) if tok_runs else None}
out = out + _planned_only
json.dump({"generated": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "issues": out, "totals": tot, "medians_min": meds,
           "avg_qa_rounds": avg_rounds}, open(os.path.join(M, "summary.json"), "w"), indent=1)
with open(os.path.join(M, "issues.csv"), "w") as f:
    f.write("issue,dev_min,qa_min,fix_min,qa_rounds,fix_rounds,qa_findings,tokens_new,tokens_cached,elapsed_min,projected_min\n")
    for o in out: f.write(",".join("" if o[k] is None else str(o[k]) for k in ("issue", "dev_min", "qa_min", "fix_min", "qa_rounds", "fix_rounds", "findings", "tokens_new", "tokens_cached", "elapsed_min", "projected_min")) + "\n")
