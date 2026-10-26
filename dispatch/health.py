#!/usr/bin/env python3
"""One source of truth for 'what needs attention' and the live counts. Run every dispatcher cycle (no tokens, no network).
Writes cache/health.json: {ts, counts, items:[{sev, text, link}]}. The status page and the founder page both render it.
New critical/warn items also raise one Mac notification each (via dispatch/alerts/), at most once per 6 hours per item."""
import json, os, re, time, datetime
D = os.path.dirname(os.path.abspath(__file__)); now = time.time(); R = "__REPO__"
def P(*a): return os.path.join(D, *a)
def jl(p, d):
    try: return json.load(open(P(p)))
    except Exception: return d
def ls(p):
    try: return [x for x in os.listdir(P(p)) if " " not in x]
    except Exception: return []
def age(p):
    try: return now - os.path.getmtime(P(p))
    except Exception: return None
def hrs(s): return ("%dm" % (s // 60)) if s < 3600 else ("%.1fh" % (s / 3600))
paused = os.path.exists(P("PAUSED")); limit = os.path.exists(P("LIMIT_HIT"))
started, done = ls("started"), set(ls("done")); gaveup = {x[:-7] for x in ls("retries") if x.endswith(".gaveup")}
batch = [l.strip() for l in open(P("batch.txt")).read().splitlines() if l.strip() and not l.strip().startswith("#")] if os.path.exists(P("batch.txt")) else []
running = sorted(n for n in started if n not in done and n not in gaveup)
queued = [n for n in batch if n not in started]
prs = jl("cache/prs.json", []); pr_ = jl("priorities.json", {}) or {}; tiers = pr_.get("tiers", {})
issues = jl("cache/issues_live.json", []); title = {str(i["number"]): i["title"] for i in issues}
nxt = jl("cache/next.json", {}); order = nxt.get("order", [])
counts = {"running": running, "queued": [n for n in order if n in queued] or queued, "slots": len(running), "open_prs": len(prs), "paused": paused,
          "next": ([n for n in order if n in queued] or [None])[0], "next_why": (nxt.get("why") or {}).get([n for n in order if n in queued][0], "") if [n for n in order if n in queued] else ""}
try: OWNER_HOLD = {l.split("#")[0].strip() for l in open(P("owner_hold.txt")) if l.split("#")[0].strip().isdigit()}
except Exception: OWNER_HOLD = set()
items = []
_conf_h = open(P("local.conf")).read() if os.path.exists(P("local.conf")) else ""
def add(sev, text, link="", key=None): items.append({"sev": sev, "text": text, "link": link, "key": key or text})
try:
    import urllib.request
    if "enabled=1" in _conf_h:
        try: urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.5).read()
        except Exception: add("warn", "The local model (Ollama) is not answering, so the local agent is stuck retrying. The dispatcher tries to restart it every 2 minutes.", key="ollama-down")
except Exception: pass
if limit: add("warn", "Usage limit reached: " + (open(P("LIMIT_HIT")).read().strip()[:120] or "agents are held until it resets."), key="limit")
for n in sorted(gaveup): add("crit", "Agent %s gave up after 3 restarts and needs you." % n, "https://github.com/%s/issues/%s" % (R, n) if n.isdigit() else "", "dead-" + n)
for n in running:
    a = age("started/" + n)
    if a and a > 120 * 60 and not paused: add("warn", "Agent %s has been running for %s (usually under 90 minutes)." % (n, hrs(a)), key="long-" + n)
active = set(running)
for p in prs:
    m = re.match(r"(\d+)-", p.get("headRefName", "")); iss = m.group(1) if m else ""
    try: upd = datetime.datetime.strptime(p["updatedAt"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()
    except Exception: continue
    idle = now - upd
    if (p.get("number") and str(p["number"]) in OWNER_HOLD): continue   # waiting for the owner by design, not a stuck PR
    if idle < 4 * 3600 or active & {iss, "fix-" + iss, "qa-%d" % p["number"], "qa-" + iss}: continue
    t = tiers.get(iss, ""); sev = "crit" if t == "P0" or idle > 24 * 3600 else "warn"
    add(sev, "PR #%d (#%s%s) has had no activity for %s and no agent is assigned%s." % (p["number"], iss, ", " + t if t else "", hrs(idle), "; dev is paused" if paused else ""), "https://github.com/%s/pull/%d" % (R, p["number"]), "pr-%d" % p["number"])
openn = {str(i["number"]) for i in issues if i.get("state") == "OPEN"}; inpr = {re.match(r"(\d+)-", p.get("headRefName", "")).group(1) for p in prs if re.match(r"(\d+)-", p.get("headRefName", ""))}
_conf = open(P("local.conf")).read() if os.path.exists(P("local.conf")) else ""
_off = any(l.strip() == "claude=off" for l in _conf.splitlines())
# claude=off: the only slot is the local agent; "a slot is free" only when no job is running at all
if not paused and not limit and len(running) < (1 if _off else 3):
    for n, t in tiers.items():
        if t == "P0" and n in openn and n not in started and n not in batch and n not in inpr and n not in done:
            add("warn", "P0 #%s (%s) is not queued although a slot is free." % (n, title.get(n, "")[:60]), "https://github.com/%s/issues/%s" % (R, n), "p0-" + n)
for f, label in (("cache/issues_live.json", "GitHub issue data"), ("cache/prs.json", "GitHub PR data")):
    a = age(f)
    if a is None: add("warn", label + " has not been fetched yet.", key="fetch-" + f)
    elif a > 20 * 60: add("warn", "%s is %s old: GitHub may be offline or the gh login expired." % (label, hrs(a)), key="fetch-" + f)
try:
    import usage as _u
    _r = _u.real(now)
    if _r and _r["age"] < 6 * 3600:
        if (_r.get("spct") or 0) >= 85: add("warn", "Claude session usage is at %d%%; agents may pause until it resets." % round(_r["spct"]), key="usage-session")
        if _r.get("wrun_out"): add("warn", "At this pace the weekly Claude limit runs out before it resets (about %s)." % time.strftime("%a %I:%M %p", time.localtime(_r["wrun_out"])), key="usage-week")
        elif (_r.get("wpct") or 0) >= 85: add("warn", "Weekly Claude usage is at %d%%." % round(_r["wpct"]), key="usage-week")
except Exception: pass
if not os.path.exists(P("cache/serve.url")): add("info", "Phone address is not up (Tailscale off or not connected). The laptop address still works.", key="tailscale")
if paused and not limit:
    a = age("PAUSED")
    if a and a > 12 * 3600: add("info", "Dev has been paused for %s." % hrs(a), key="paused-long")
sev_rank = {"crit": 0, "warn": 1, "info": 2}; items.sort(key=lambda x: sev_rank[x["sev"]])
out = {"ts": int(now), "counts": counts, "items": items}
tmp = P("cache/health.json.tmp"); json.dump(out, open(tmp, "w")); os.replace(tmp, P("cache/health.json"))
# one Mac notification per new critical/warn item, at most every 6h per item (and none while paused for PR idleness)
# architect review is a Cowork scheduled task: it only runs while the Cowork app is open and the Mac awake
try: ac = float(open(P("cache/arch.checked")).read().strip())
except Exception: ac = 0
if prs and not paused and ac and now - ac > 35 * 60 and not os.path.exists(P("LIMIT_HIT")):
    add("warn", "The architect review has not run for %s, so merges, fix notes and new queue items are waiting. Open the Cowork app (keep the Mac awake) or run it by hand." % hrs(now - ac), key="arch-overdue")
sent = jl("cache/attn.sent.json", {}); os.makedirs(P("alerts"), exist_ok=True); changed = False
for it in items:
    if it["sev"] == "info" or (paused and it["key"].startswith(("pr-", "p0-"))): continue
    if now - sent.get(it["key"], 0) < 6 * 3600: continue
    sent[it["key"]] = now; changed = True
    open(P("alerts", time.strftime("%Y%m%dT%H%M%S") + "-attn-%d.txt" % abs(hash(it["key"]) % 10000)), "w").write("Needs attention\n" + it["text"] + "\n")
if changed: json.dump({k: v for k, v in sent.items() if now - v < 86400}, open(P("cache/attn.sent.json"), "w"))
