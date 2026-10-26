#!/usr/bin/env python3
"""Writes dispatch/status.html (auto-refreshing). Called by run_batch.sh every loop; open the file in any browser.
Reads only local dispatch files plus (cached 60s) `gh` for open PRs/issues. Never writes anywhere else."""
import os, re, json, time, html, subprocess, datetime
import attn, usage
D = os.path.dirname(os.path.abspath(__file__)); R = "__REPO__"
now = time.time()

def read(p, d=""):
    try: return open(os.path.join(D, p)).read()
    except Exception: return d


def _cut(t, n):
    """Shorten at a word boundary with an ellipsis, never mid-word or mid-bracket."""
    t = (t or "").strip()
    if len(t) <= n: return t
    c = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:(-")
    return c + "\u2026"

def auto_block():
    L = []
    run = [(n, st) for age, n, st, res in rows if st in ("running", "starting")]
    dead = [n for age, n, st, res in rows if st == "dead"]
    L.append("<h3>Right now (updates by itself every 20 seconds)</h3>")
    L.append("<p>" + (f"{len(run)} agent(s) working: " + "; ".join(f"{e(n)} ({e(_cut(label(n), 90))})" for n, st in run) if run else "No agents are working right now.") + "</p>")
    if dead: L.append("<p><b>Stuck:</b> " + ", ".join(e(n) for n in dead) + " is not running and needs a restart.</p>")
    items = []
    for p in (prs or []):
        m = re.match(r"(\d+)-", p["headRefName"]); iss = m.group(1) if m else ""
        fx = next(((st, res) for age, n, st, res in rows if n == f"fix-{iss}"), None)
        qa = next(((st, res) for age, n, st, res in rows if n == f"qa-{p['number']}"), None)
        if fx and fx[0] in ("running", "starting"): s = "a fix agent is working on QA findings"
        elif qa and qa[0] in ("running", "starting"): s = "QA is attacking it now"
        elif fx and fx[0] == "dead": s = "its fix agent is not running (needs a restart)"
        elif qa and qa[0] == "done" and re.search(r"\b0 findings", qa[1]): s = "QA passed with no findings, ready to merge"
        elif qa and qa[0] == "done": s = "QA found problems: " + qa[1][:120]
        elif qa and qa[0] == "queued": s = "QA is queued"
        else:
            try: s = pr_reason(p)
            except Exception: s = "waiting for the architect review"
            s = s[:1].lower() + s[1:]
        items.append(f"<li>PR #{p['number']} {e(_cut(p['title'], 120))}: {e(s)}.</li>")
    L.append("<p>Open PRs: " + (f"{len(items)}" if items else "none") + "</p>" + ("<ul>" + "".join(items) + "</ul>" if items else ""))
    return "".join(L)

def summary_block():
    t = read("summary.txt").strip()
    try:
        if t and now - os.path.getmtime(os.path.join(D, "summary.txt")) > 900: t = ""  # stale: the live section above is the truth
    except Exception: pass
    try: age = now - os.path.getmtime(os.path.join(D, "summary.txt"))
    except Exception: age = 0
    stamp_note = (f"<p class=m>Orchestrator note below was written {ago(age)} ago" + (" and may be out of date; the live section above is current." if age > 3600 else ".") + "</p>") if t else ""
    _p = os.path.exists(os.path.join(D, "PAUSED")); _tl = t.lower()
    if t and ((not _p and "dev is paused" in _tl) or (_p and "dev is on" in _tl)): stamp_note += "<p class=m style='color:#B42318;font-weight:600'>This note says dev is " + ("paused" if "dev is paused" in _tl else "on") + " but dev is now " + ("paused" if _p else "on") + ". Trust the live section above until the architect refreshes it.</p>"
    out, items = [], []
    def flush():
        if items: out.append("<ul>" + "".join(items) + "</ul>"); items.clear()
    for ln in t.splitlines():
        ln = ln.strip()
        if not ln: flush(); continue
        if ln.startswith("- "): items.append("<li>" + html.escape(ln[2:]) + "</li>")
        elif ln.startswith("## "): flush(); out.append("<h3>" + html.escape(ln[3:]) + "</h3>")
        else: flush(); out.append("<p>" + html.escape(ln) + "</p>")
    flush()
    return workshop() + "<h2>Where we are, in plain English</h2><div class=sum>" + auto_block() + stamp_note + "".join(out) + "</div>"

def gh(args, cache, ttl=60):
    cp = os.path.join(D, "cache"); os.makedirs(cp, exist_ok=True); f = os.path.join(cp, cache)
    if os.path.exists(f) and now - os.path.getmtime(f) < ttl:
        try: return json.load(open(f))
        except Exception: pass
    try:
        out = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=25).stdout
        data = json.loads(out); json.dump(data, open(f, "w")); return data
    except Exception:
        try: return json.load(open(f))
        except Exception: return None

def alive(n):
    # real = a claude process carrying this agent's tag; launcher-only counts as alive for the first 5 minutes (startup)
    try:
        if subprocess.run(["pgrep", "-f", f"AGENT-ID-{n}\\."], capture_output=True).returncode == 0: return True
        out = subprocess.run(["pgrep", "-f", f"agent\\.sh {n}( |$)"], capture_output=True, text=True).stdout.split()
        for pid in out[:1]:
            et = subprocess.run(["ps", "-o", "etime=", "-p", pid], capture_output=True, text=True).stdout.strip()
            if re.fullmatch(r"\d{1,2}:\d\d", et) and int(et.split(":")[0]) < 5: return True
        return False
    except Exception: return None

issues = gh(["issue", "list", "--repo", R, "--state", "all", "-L", "300", "--json", "number,title"], "issues.json", 300) or []
titles = {str(i["number"]): i["title"] for i in issues}
prs = gh(["pr", "list", "--repo", R, "--state", "open", "--json", "number,title,headRefName,updatedAt,statusCheckRollup"], "prs.json", 60)

def label(n):
    m = re.match(r"(?:fix-|qa-)?(\d+)$", n)
    if not m: return n
    base = m.group(1)
    if n.startswith("qa-"): return f"QA of PR #{base}"
    t = titles.get(base, "")
    return (f"Fix review feedback: {t}" if n.startswith("fix-") else t) or n

def describe(n, st):
    base = re.sub(r"^(fix-|qa-)", "", n)
    if st == "dead" and os.path.exists(os.path.join(D, "retries", n + ".gaveup")): pre = "Gave up after 3 restarts; needs a restart. "
    else: pre = ""
    if n.startswith("qa-"): return pre + "Adversarial QA: trying to break PR #" + base
    if n.startswith("fix-"):
        ls = read(f"fixes/{base}.txt").splitlines()[1:2]
        t = re.sub(r"^PR #\d+ \(issue #\d+[^)]*\)\s*", "", ls[0]) if ls else ""
        return pre + "Fixing: " + t[:170]
    return pre + "Building the feature"

batch = [l.strip() for l in read("batch.txt").splitlines() if l.strip() and not l.strip().startswith("#")]
started = sorted(os.listdir(os.path.join(D, "started"))) if os.path.isdir(os.path.join(D, "started")) else []
rows = []
for n in dict.fromkeys(batch):
    sp = os.path.join(D, "started", n); dp = os.path.join(D, "done", n)
    if os.path.exists(dp):
        res = read(f"done/{n}").strip(); age = now - os.path.getmtime(dp)
        if age < 6 * 3600: rows.append((age, n, "done", res))
    elif os.path.exists(sp):
        a = alive(n); age = now - os.path.getmtime(sp)
        st0 = "running" if a else ("dead" if a is False and age > 180 else "starting"); rows.append((age, n, st0, describe(n, st0)))
    else:
        rows.append((0, n, "queued", ""))
order = {"running": 0, "starting": 1, "dead": 2, "queued": 3, "done": 4}
rows.sort(key=lambda r: (order[r[2]], r[0]))

def ago(s):
    s = int(s); return f"{s//3600}h {s%3600//60}m" if s >= 3600 else f"{s//60}m" if s >= 60 else "just now"
badge = {"running": ("#1F9D8B", "Running"), "starting": ("#2F6FDE", "Starting"), "dead": ("#C0392B", "Not running"),
         "queued": ("#8A94AD", "Queued"), "done": ("#5B6785", "Finished")}
e = html.escape

# ---- Local model (Ollama) tracking: jobs that ran on the free local model are tagged "Ollama" ----
def _rd(name):
    try: return open(os.path.join(D, name)).read()
    except Exception: return ""
def _iso(t):
    try: return datetime.datetime.strptime(t.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()
    except Exception: return 0
CLAUDE_OFF = any(l.strip() == "claude=off" for l in _rd("local.conf").splitlines())
LOCAL_RUNS = []   # (epoch, job, model) in order
for _ln in _rd("local_runs.txt").splitlines():
    _p = [x.strip() for x in _ln.split("|")]
    if len(_p) >= 3: LOCAL_RUNS.append((_iso(_p[0]), _p[1], _p[2].replace("local:", "")))
_LAST = {j: (t, m) for t, j, m in LOCAL_RUNS}
def is_local(n):
    v = _LAST.get(n)
    try: st = os.path.getmtime(os.path.join(D, "started", n))
    except Exception: st = 0
    return bool(v) and bool(st) and v[0] >= st - 120
def olpill(n): return ("<span class=olp>\U0001F999 Ollama \u00B7 " + html.escape(_LAST[n][1]) + "</span>") if is_local(n) else ""
def ollama_panel(active_names):
    import urllib.request
    cfg = {}
    for l in _rd("local.conf").splitlines():
        if "=" in l and not l.lstrip().startswith("#"): a, b = l.split("=", 1); cfg[a.strip()] = b.strip()
    on = cfg.get("enabled") == "1"; model = cfg.get("model", "?")
    up, loaded = False, None
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1.5).read(); up = True
        ps = json.loads(urllib.request.urlopen("http://localhost:11434/api/ps", timeout=1.5).read())
        if ps.get("models"): loaded = sum(m.get("size", 0) for m in ps["models"]) / 1e9
    except Exception: pass
    working = [n for n in active_names if is_local(n)]
    if not on: st, col = "Off (set enabled=1 in dispatch/local.conf)", "#8A94AD"
    elif not up: st, col = "On, but Ollama is not running", "#C0392B"
    elif working: st, col = "Working: " + ", ".join(working), "#7B3FE4"
    else: st, col = "On, idle (next fix or QA job runs here first)", "#1F8A3B"
    vd = [l.split("|") for l in _rd("local_verdicts.txt").splitlines() if "|" in l and not l.startswith("#")]
    ps_, fl_ = sum(1 for v in vd if v[1].strip() == "pass"), sum(1 for v in vd if v[1].strip() == "fail")
    rate = ("%d%% passed my first review (%d of %d)" % (round(100 * ps_ / (ps_ + fl_)), ps_, ps_ + fl_)) if ps_ + fl_ else "No reviewed runs yet. Target: 50% or better over a week"
    fin = sum(1 for t, j, m in LOCAL_RUNS if os.path.exists(os.path.join(D, "done", j)) and is_local(j))
    rec = ""
    for t, j, m in reversed(LOCAL_RUNS[-5:]):
        try: res = open(os.path.join(D, "done", j)).read().strip().replace("\n", " ")[:90]
        except Exception: res = "running or waiting"
        v = next((x[1].strip() for x in reversed(vd) if x[0].strip() == j), "")
        rec += "<div class=olr><b>" + html.escape(j) + "</b> <span class=m>" + datetime.datetime.fromtimestamp(t).strftime("%a %H:%M") + " \u00B7 " + html.escape(m) + "</span> " + ("<span class=olv " + ("style='background:#E8F8EE;color:#1F8A3B'" if v == "pass" else "style='background:#FDECEA;color:#C4281C'") + ">review: " + v + "</span>" if v else "") + "<div class=m>" + html.escape(res) + "</div></div>"
    return ("<div class=olbox><div class=olh><span class=olp>\U0001F999 Ollama</span><b>Local model</b><span class=olst style='color:" + col + "'>" + html.escape(st) + "</span></div>"
            "<div class=m>Model " + html.escape(model) + (" \u00B7 using %.1f GB of RAM now" % loaded if loaded else " \u00B7 not loaded in memory right now") + " \u00B7 free, runs on this Mac, no Claude tokens. Fix and QA jobs run here once; if my review fails, the retry goes to Claude.</div>"
            "<div class=olg><div><b>" + str(len(LOCAL_RUNS)) + "</b>runs started</div><div><b>" + str(fin) + "</b>finished</div><div><b>" + str(ps_ + fl_) + "</b>reviewed</div></div>"
            "<div class=m style='margin:4px 0'>" + html.escape(rate) + "</div>" + (rec or "<div class=m>No local runs yet.</div>") + "</div>")
def limit_msg():
    """Text of the usage-limit message if agents are blocked by it right now, else None. Reads the flag the dispatcher writes, or the newest agent terminal log."""
    fp = os.path.join(D, "LIMIT_HIT")
    try:
        if os.path.exists(fp) and now - os.path.getmtime(fp) < 30 * 60: return read("LIMIT_HIT").strip() or "Usage limit hit"
    except Exception: pass
    try:
        ld = os.path.join(D, "logs"); logs = [os.path.join(ld, f) for f in os.listdir(ld) if f.endswith(".term.log")]
        if logs:
            newest = max(logs, key=os.path.getmtime)
            if now - os.path.getmtime(newest) < 30 * 60:
                with open(newest, "rb") as fh:
                    fh.seek(0, 2); fh.seek(max(0, fh.tell() - 6000)); t = fh.read().decode("utf-8", "ignore")
                t = re.sub(r"[^\x20-\x7e\n]", "", t)
                ms = re.findall(r"[^\n]*hit your [^\n]*limit[^\n]*", t, re.I)
                if ms: return ms[-1].strip()[:160]
    except Exception: pass
    return None

def _wip():
    try: return int([l for l in open(os.path.join(D, "wip.conf")) if l.startswith("open_pr_limit=")][0].split("=")[1])
    except Exception: return 4
def queue_reason(n):
    """Exact reason an item is still queued. Same rules as run_batch.sh: 3 slots, WIP limit 4 PRs for feature work, PAUSED."""
    if os.path.exists(os.path.join(D, "PAUSED")): return "Dispatcher is paused (you paused it)"
    if limit_msg(): return "Paused: usage limit hit (retries every 30 min)"
    held = [m for age, m, st, res in rows if st in ("running", "starting") or (st == "dead" and not os.path.exists(os.path.join(D, "retries", m + ".gaveup")))]
    if len(held) >= 3: return "All 3 slots are held by " + ", ".join(held[:3])
    nopen_ = len(prs) if prs else 0
    if not n.startswith(("fix-", "qa-")) and nopen_ >= _wip(): return f"Feature work waits: {nopen_} PRs open (limit {_wip()})"
    return "Nothing blocks it: starts on the next 20-second dispatcher pass"

def _ready_prs():
    """PR numbers the architect marked 'ready to merge' in owner_hold.txt."""
    try:
        return {l.split("#")[0].strip() for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "owner_hold.txt"))
                if "#" in l and l.split("#", 1)[1].strip().startswith("ready to merge") and l.split("#")[0].strip().isdigit()}
    except Exception: return set()

def next_step(n, st, res):
    pr_nums = {p["number"] for p in (prs or [])}
    by_issue = {}
    for p in (prs or []):
        m = re.match(r"(\d+)-", p["headRefName"])
        if m: by_issue[m.group(1)] = p["number"]
    nopen_ = len(prs) if prs else 0
    if st == "queued": return queue_reason(n)
    if st in ("running", "starting"): return "Keep working; hands off with a pushed fix or a PR"
    if st == "dead": return "Needs a restart (requeue it)"
    iss = n.split("-", 1)[1] if n.startswith(("fix-", "qa-")) else n
    if n.startswith("qa-"):
        if not iss.isdigit() or int(iss) not in pr_nums: return "PR is closed or merged; nothing more"
        if re.search(r"\b0 findings", res): return "Architect reviews; merge if rules pass"
        return "Fix agent repairs the findings, then QA re-checks"
    if n.startswith("fix-"):
        return "QA re-checks the fix, then merge if clean" if iss in by_issue else "PR is closed or merged; nothing more"
    m = re.search(r"/pull/(\d+)", res)
    if m:
        if int(m.group(1)) not in pr_nums: return "PR is open; already closed or merged"
        if str(m.group(1)) in _ready_prs(): return "PR is open; the architect approved it, ready to merge"
        return "PR is open; the architect reviews it next (QA only for safety-relevant changes)"
    return "Waiting for its result"

def stcls(st): return {"running": "running", "starting": "running", "queued": "queued", "done": "done", "dead": "dead"}[st]
agents = "".join(
    f"<tr class='ar {stcls(st)}'><td><span class=b style='background:{badge[st][0]}'>{badge[st][1]}</span></td><td>{e(n)}{olpill(n)}</td><td>{e(label(n))}</td>"
    f"<td>{'' if st=='queued' else ago(age)}</td><td class=m>{e(res[:140])}</td><td style='min-width:190px'>{e(next_step(n, st, res))}</td></tr>" for age, n, st, res in rows) or "<tr><td colspan=6 class=m>Nothing in the queue.</td></tr>"

try: owner_hold = {l.split("#")[0].strip() for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "owner_hold.txt")) if l.split("#")[0].strip().isdigit()}
except Exception: owner_hold = set()
def pr_reason(p):
    m = re.match(r"(\d+)-", p["headRefName"]); iss = m.group(1) if m else ""
    fx = next(((st, res) for age, n, st, res in rows if n == f"fix-{iss}"), None)
    qa = next(((st, res) for age, n, st, res in rows if n == f"qa-{p['number']}"), None)
    up = now - datetime.datetime.fromisoformat(p["updatedAt"].replace("Z", "+00:00")).timestamp()
    if str(p["number"]) in _ready_prs(): return "Approved by the architect: ready to merge (tell the orchestrator, or merge it yourself)"
    if str(p["number"]) in owner_hold: return "Waiting for you: needs your decision or approval (the architect will not merge this one)"
    if fx and fx[0] in ("running", "starting"): return "Fix agent is working on QA findings"
    if qa and qa[0] in ("running", "starting"): return "QA is testing it now"
    if fx and fx[0] == "dead": return "Fix agent stopped; needs a restart"
    if fx and fx[0] == "queued": return "Waiting in the queue for a fix agent"
    if fx and fx[0] == "done" and not (qa and qa[0] == "queued"): return "Fix pushed; waiting for a QA re-check"
    if qa and qa[0] == "done" and re.search(r"\b0 findings", qa[1]): return "QA clean; ready for review and merge"
    if qa and qa[0] == "done": return "QA found problems; " + "the architect writes the fix notes, then a fix agent starts"
    if qa and qa[0] == "queued": return "Waiting in the queue for QA"
    if up < 900: return "Just opened; review and QA not started yet"
    return "Waiting for the architect review (no agent needed)" + (f"; idle {ago(up)}" if up > 6 * 3600 else "")

HDR = "<tr class=hd><th>PR</th><th>Title</th><th>Branch</th><th>Last update</th><th>Why not merged yet</th></tr>"
if prs is None: prtab = "<tr><td class=m colspan=5>Could not reach GitHub (gh not signed in?).</td></tr>"
elif not prs: prtab = "<tr><td class=m colspan=5>No open pull requests.</td></tr>"
else:
    prtab = HDR + "".join(f"<tr><td><a href='https://github.com/{R}/pull/{p['number']}'>#{p['number']}</a></td><td>{e(p['title'])}</td>"
                    f"<td class=m>{e(p['headRefName'])}</td><td>{ago(now - datetime.datetime.fromisoformat(p['updatedAt'].replace('Z','+00:00')).timestamp())} ago</td>"
                    f"<td>{e(pr_reason(p))}</td></tr>" for p in prs)

def localize(t):
    """Turn 2026-10-17T00:18:39Z into 'Sat 17 Oct, 11:18 AM' in the Mac's local time."""
    def f(m):
        try:
            d = datetime.datetime.strptime(m.group(0)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).astimezone()
            return d.strftime("%a %-d %b, %-I:%M %p")
        except Exception: return m.group(0)
    return re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ?", f, t)

def tail(p, n, w=230):
    ls = [l.strip() for l in read(p).splitlines() if l.strip()][-n:][::-1]
    return "".join(f"<li>{e(localize(l)[:w+14])}</li>" for l in ls) or "<li class=m>Nothing yet.</li>"

sent = os.path.join(D, "alerts", "sent")
alerts = ""
if os.path.isdir(sent):
    fs = sorted(os.listdir(sent))[-6:][::-1]
    alerts = "".join(f"<li>{e(read('alerts/sent/'+f).splitlines()[0] if read('alerts/sent/'+f) else f)}</li>" for f in fs)
nrun = sum(1 for r in rows if r[2] == "running"); ndead = sum(1 for r in rows if r[2] == "dead")
stamp = datetime.datetime.now().strftime("%a %d %b, %I:%M:%S %p")

def categorize(title, labels):
    t = title.lower(); L = {x.lower() for x in labels}
    if re.search(r"red-flag|safety|clinical|emergency|medical", t): return "Safety"
    if re.search(r"analytics|privacy|policy|telemetry", t): return "Data and privacy"
    if re.search(r"\bci\b|pipeline|release|testflight|xcode cloud|dispatch|actions minutes|test_host|build number|infra|relay deploy|worktree|agent", t) or "ops" in L: return "Admin and ops"
    if re.search(r"design|visual|mockup|screen|ui\b|layout|copy", t): return "Design"
    if re.search(r"refactor|clean|tidy|dedup|stale|rename|remove|migrate|tech debt|split ", t) or "chore" in L: return "Clean-up"
    if "bug" in L or re.search(r"\bfix\b|crash|can.?t |not recognized|collapses|hidden|breaking", t): return "Bug fix"
    if "documentation" in L or re.search(r"\bdocs?\b|adr|readme", t): return "Docs"
    if "enhancement" in L: return "Feature"
    return "Other"

def backlog_block():
    oi = gh(["issue", "list", "--repo", R, "--state", "open", "-L", "200", "--json", "number,title,labels,createdAt"], "open_issues.json", 300)
    items = []
    inpr = {}
    for p in (prs or []):
        m = re.match(r"(\d+)-", p["headRefName"])
        if m: inpr[m.group(1)] = p["number"]
        for x in re.findall(r"#(\d+)", p["title"]): inpr.setdefault(x, p["number"])
    running = {re.sub(r"^(fix-|qa-)", "", n) for age, n, st, res in rows if st in ("running", "starting")}
    for i in (oi or []):
        n = str(i["number"]); labs = [l["name"] for l in i.get("labels", [])]
        if "[note]" in i["title"].lower(): continue
        title = i["title"]; cat = categorize(title, labs)
        if n in running: stt = "In progress"
        elif n in inpr: stt = f"In PR #{inpr[n]}"
        elif re.search(r"deferred|backlog:|later|epic", title.lower()): stt = "Deferred"
        else: stt = "Backlog"
        age = (now - datetime.datetime.fromisoformat(i["createdAt"].replace("Z", "+00:00")).timestamp()) / 86400
        items.append((cat, n, title, ", ".join(labs), stt, f"{int(age)}d", f"https://github.com/{R}/issues/{n}"))
    for ln in read("owner_tasks.txt").splitlines():
        if "|" in ln: c, t = ln.split("|", 1); items.append((c.strip(), "-", t.strip(), "owner", "Yours", "", ""))
    if not items: return ""
    cats = {}
    for it in items: cats[it[0]] = cats.get(it[0], 0) + 1
    chips = "<span class=tab data-c=All>All<i>%d</i></span>" % len(items) + "".join(f"<span class=tab data-c='{e(c)}'>{e(c)}<i>{k}</i></span>" for c, k in sorted(cats.items(), key=lambda x: -x[1]))
    rws = "".join(f"<tr data-c='{e(c)}' data-s='{e(s)}'><td>{('<a href=' + chr(39) + u + chr(39) + '>#' + n + '</a>') if u else ''}</td><td>{e(t)}</td><td><span class=cat>{e(c)}</span></td><td class=m>{e(s)}</td><td class=m>{e(a)}</td></tr>"
                  for c, n, t, l, s, a, u in sorted(items, key=lambda x: (x[0] == "Owner to-do" and 0 or 1, x[0], x[1])))
    return f"""<h2>Backlog: everything still to do</h2>
<div class=bar><input id=bq placeholder="Search title or number"> <span class=m id=bcnt></span></div><div class=bar>{chips}</div>
<div class=scroll><table id=bt><tr class=hd><th>Issue</th><th>What</th><th>Category</th><th>Status</th><th>Age</th></tr>{rws}</table></div>
<script>(function(){{var c=sessionStorage.getItem('bc')||'All',q='';function ap(){{var n=0;document.querySelectorAll('#bt tr[data-c]').forEach(function(r){{var ok=(c=='All'||r.dataset.c==c)&&(!q||r.textContent.toLowerCase().indexOf(q)>-1);r.style.display=ok?'':'none';if(ok)n++}});
document.querySelectorAll('.tab[data-c]').forEach(function(t){{t.classList.toggle('on',t.dataset.c==c)}});document.getElementById('bcnt').textContent=n+' shown'}}
document.querySelectorAll('.tab[data-c]').forEach(function(t){{t.onclick=function(){{c=t.dataset.c;sessionStorage.setItem('bc',c);ap()}}}});
document.getElementById('bq').oninput=function(ev){{q=ev.target.value.toLowerCase();ap()}};ap()}})();</script>"""


def fmt_min(m):
    if m is None: return "n/a"
    return f"{m//60}h {m%60:02d}m" if m >= 60 else f"{m}m"
def fmt_tok(n):
    if n is None: return "n/a"
    return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}k"
def metrics_block():
    try: S = json.load(open(os.path.join(D, "metrics", "summary.json")))
    except Exception: return "<h2>Delivery metrics</h2><div class=sum>Not collected yet. It fills in within 5 minutes of the dispatcher running.</div>"
    T, Md = S["totals"], S["medians_min"]; rws = []
    for o in S["issues"]:
        pj, ac = o["projected_min"], o["active_min"]
        pv = "-" if pj is None else f'{fmt_min(pj)} planned / {fmt_min(ac)} actual'
        st = "running" if o["running"] else ""
        rws.append(f'<tr class=mr><td><b>#{e(o["issue"])}</b></td><td>{e(titles.get(o["issue"], "")[:70])}</td><td>{fmt_min(o["dev_min"])}</td><td>{fmt_min(o["qa_min"])}</td><td>{fmt_min(o["fix_min"])}</td>'
                   f'<td>{o["qa_rounds"]} / {o["fix_rounds"]}</td><td>{o["findings"]}</td><td>{fmt_tok(o["tokens_new"])}</td><td>{fmt_min(o["elapsed_min"])}</td><td>{pv}</td><td>{o["restarts"] or ""}</td></tr>')
    typ = " | ".join(f"{k} {v} min" for k, v in (("dev", Md.get("dev")), ("QA", Md.get("qa")), ("fix", Md.get("fix"))) if v)
    tk = f'{fmt_tok(T["tokens_new"])} across {T["tokens_known_for"]} issues' if T["tokens_known_for"] else "being collected from now on"
    return f"""<h2>Delivery metrics per issue</h2>
<div class=cards><div class=c><b>{T["issues"]}</b>issues worked</div><div class=c><b>{T["findings"]}</b>bugs found by QA</div><div class=c><b>{T["tester_issues"]}</b>bugs from testers</div>
<div class=c><b>{fmt_min(T["active_min"])}</b>agent working time</div><div class=c><b>{T["qa_rounds"]} / {T["fix_rounds"]}</b>QA / fix rounds</div></div>
<div class=m style="margin:4px 0 8px">Typical run: {typ or "not enough data yet"}. Average QA rounds per issue: {S["avg_qa_rounds"]}. Tokens used (new work, not cached re-reads): {tk}. Older runs show n/a where the end time or tokens were never recorded; everything from now on is captured. Files: dispatch/metrics/issues.csv.</div>
<div class=scroll><table><tr class=hd><th>Issue</th><th>What</th><th>Dev</th><th>QA</th><th>Fix</th><th>QA / fix rounds</th><th>Bugs found</th><th>Tokens</th><th>Calendar time</th><th>Planned / actual</th><th>Restarts</th></tr>{"".join(rws)}</table></div>"""
def pipeline_block():
    L = [l.rstrip("\n") for l in read("pipeline.txt").splitlines() if l.strip() and not l.startswith("#")]
    if not L: return ""
    rws, wave = [], None
    for l in L:
        p = [x.strip() for x in l.split("|")]
        if len(p) < 4: continue
        w, n, what, why = p[:4]
        if w != wave: rws.append(f'<tr><td colspan=4 class=grp>{e(w)}</td></tr>'); wave = w
        key = n.replace("#", "")
        if os.path.exists(os.path.join(D, "done", key)): stt = "dev finished"
        elif os.path.exists(os.path.join(D, "started", key)): stt = "in progress"
        elif key in [x.strip() for x in read("batch.txt").splitlines()]: stt = "queued"
        else: stt = "planned"
        rws.append(f'<tr><td><b>#{e(key)}</b></td><td>{e(what)}</td><td>{e(why)}</td><td><span class=cat>{stt}</span></td></tr>')
    return f"""<h2>Pipeline to the next tester build</h2><div class=m style="margin-bottom:6px">Order of work. Safety and trust first, then quick wins, then the bigger design items.</div>
<table><tr class=hd><th>Issue</th><th>What</th><th>Why now</th><th>State</th></tr>{"".join(rws)}</table>"""

def workshop():
    """Visual strip: founder, architect, 3 agent desks (dev/fix/QA), queue line, and the hard limits. Pure CSS, no tables."""
    def kind(n):
        return ("qa", "\U0001F575\uFE0F", "QA") if n.startswith("qa-") else ("fix", "\U0001F527", "Fix") if n.startswith("fix-") else ("dev", "\U0001F9D1\u200D\U0001F4BB", "Dev")
    active = [(age, n, st) for age, n, st, res in rows if st in ("running", "starting")]
    stuck = [(age, n) for age, n, st, res in rows if st == "dead"]
    queued = [n for age, n, st, res in rows if st == "queued"]
    done = [(age, n) for age, n, st, res in rows if st == "done"][:4]
    nopen = len(prs) if prs else 0
    # architect: last scheduled/interactive review
    try: oage = now - max(os.path.getmtime(os.path.join(D, f)) for f in ("orchestrator-log.md", "cache/arch.checked") if os.path.exists(os.path.join(D, f)))
    except Exception: oage = 10**7
    olast = [l for l in read("orchestrator-log.md").splitlines() if l.startswith("- ")][-1:]
    otxt = re.sub(r"^- \S+ (\(scheduled run\) |\(interactive[^)]*\) )?", "", olast[0])[:95] if olast else "no entries yet"
    arch_on = oage < 40 * 60
    arch = (f"<div class='desk {'on arch' if arch_on else 'off'}'><div class=fig>\U0001F9E0</div>"
            + ("<div class=kb>\U0001F4CB</div>" if arch_on else "<div class=zz>z<span>z</span><span>Z</span></div>")
            + f"<div class=nm>Solution architect</div><div class=sb>Automatic reviewer (headless Claude, every 20 min) \u00B7 last review {ago(oage)} ago</div><div class=sb style='margin-top:3px'>{e(attn.clip(otxt,90))}</div></div>")
    todo = [l.split("|", 1)[1].strip() for l in read("owner_tasks.txt").splitlines() if l.startswith("Owner to-do|")]
    try:   # owner to-dos are real GitHub issues titled "Owner: ..."; closing one on GitHub clears it here. Falls back to owner_tasks.txt until they exist.
        _oi = [i for i in json.load(open(os.path.join(D, "cache", "issues_live.json"))) if i["title"].lower().startswith("owner:")]
        if _oi: todo = ["#%d %s" % (i["number"], i["title"][6:].strip()) for i in sorted(_oi, key=lambda i: i["number"]) if i["state"] == "OPEN"]
    except Exception: pass
    fnd = (f"<div class='desk on founder'><div class=fig>\U0001F9D1\u200D\U0001F680</div><div class=nm>Founder</div>"
           f"<div class=sb>{len(todo)} items need you</div>" + "".join(f"<div class=sb style='margin-top:3px'>\u2022 {e(attn.clip(x,60))}</div>" for x in todo[:2]) + "</div>")
    desks = ""
    active = sorted(active, key=lambda x: -x[0])   # oldest job first so a desk keeps its agent number between refreshes
    def focus(n):
        k, ic, role = kind(n); iss = n.split("-", 1)[1] if n.startswith(("fix-", "qa-")) else n
        if n.startswith("qa-"): return f"QA: attacking PR #{iss}"
        if n.startswith("fix-"): return f"Fix: repairing issue #{iss}"
        return f"Dev: building issue #{iss}"
    active_all = active; active = [a for a in active_all if not is_local(a[1])]; local_act = [a for a in active_all if is_local(a[1])]
    for i in range(3):
        if i < len(active):
            age, n, st = active[i]; k, ic, role = kind(n)
            desks += (f"<div class='desk on {k}{' ollama' if is_local(n) else ''}'><div class=ag>Agent {i+1}</div>{olpill(n)}<div class=fig>{ic}</div><div class=kb>\u2328\uFE0F</div>"
                      f"<div class=nm>{e(focus(n))}</div><div class=sb>{e(n)} \u00B7 {ago(age)}</div>" + ("<div class=sb style=\"color:#C0392B;font-weight:700\">Blocked: usage limit</div>" if limit_msg() else "<div class=dots><i></i><i></i><i></i></div>") + "</div>")
        else:
            desks += (f"<div class='desk off'><div class=ag>Agent {i+1}</div><div class=fig>\U0001F634</div><div class=zz>z<span>z</span><span>Z</span></div>"
                      "<div class=nm>" + ("Off" if CLAUDE_OFF else "On standby") + "</div><div class=sb>" + ("Saving the weekly allocation" if CLAUDE_OFF else "Takes the next dev, fix or QA job") + "</div></div>")
    _lc = {}
    for _l in _rd("local.conf").splitlines():
        if "=" in _l and not _l.lstrip().startswith("#"): _a, _b = _l.split("=", 1); _lc[_a.strip()] = _b.strip()
    _na = 4 if (_lc.get('enabled') == '1' or local_act) else 3
    if local_act:
        age, n, st = local_act[0]; k, ic, role = kind(n)
        desks += (f"<div class='desk on {k} ollama'><div class=ag>Ollama</div><div class=fig>{ic}</div><div class=kb>\u2328\uFE0F</div>"
                  f"<div class=nm>{e(focus(n))}</div><div class=sb>{e(n)} \u00B7 {ago(age)}</div><div class=dots><i></i><i></i><i></i></div></div>")
    elif _lc.get('enabled') == '1':
        desks += ("<div class='desk off ollama'><div class=ag>Ollama</div><div class=fig>\U0001F634</div><div class=zz>z<span>z</span><span>Z</span></div>"
                  f"<div class=nm>{'On standby' if _lc.get('enabled') == '1' else 'Off'}</div><div class=sb>Takes a fix or QA job</div></div>")
    desks += "".join(f"<div class='desk bad'><div class=fig>\U0001F915</div><div class=nm>{e(n)}</div><div class=sb>stuck \u00B7 {ago(age)}</div></div>" for age, n in stuck)
    qline = "".join(f"<div class=qp style='width:190px'><div class=fig2>\U0001F9CD</div><div class=nm>{e(n)}</div><div class=sb>{e(queue_reason(n))}</div></div>" for n in queued[:8])
    dn = "".join(f"<span class=dn>\u2705 {e(n)}</span>" for age, n in done)
    # hard limits
    olog = " ".join(read("orchestrator-log.md").splitlines()[-30:]).lower() + " " + " ".join(read("status.md").splitlines()[-60:]).lower()
    lm = limit_msg(); hit = lm is not None
    gave = len([f for f in os.listdir(os.path.join(D, "retries")) if f.endswith(".gaveup")]) if os.path.isdir(os.path.join(D, "retries")) else 0
    def chip(title, val, mx, note, bad=False, nobar=False):
        pct = 0 if nobar else min(100, int(100 * val / mx)) if mx else 0
        col = "#C0392B" if bad else "#E8892B" if pct >= 100 else "#1F9D8B"
        bar = "" if nobar else f"<div class=meter><i style='width:{pct}%;background:{col}'></i></div>"
        return f"<div class='lim{' hot' if bad or pct >= 100 else ''}'><div class=lt>{title}</div><div class=lv>{val}{f' / {mx}' if mx else ''}</div>{bar}<div class=ln>{note}</div></div>"
    lims = (chip("Slots in use", len(active) + len([1 for age, m in stuck if not os.path.exists(os.path.join(D, "retries", m + ".gaveup"))]), 3, "3 slots shared by all dev, fix and QA jobs. Agents that gave up do not hold one", bad=False)
            + chip("Open PRs", nopen, _wip(), f"At {_wip()}, new feature work waits. Fix and QA still run", bad=False)
            + chip("Restart cap", gave, 0, "Agents that died 3 times stay stopped until you requeue them" if gave else "Agents get 3 restarts, then stop and alert", bad=gave > 0, nobar=True)
            + chip("Architect review", ago(oage), 0, "Checks for changes about every 20 min; acts only when something changed" if oage < 60 * 60 else "Overdue: nothing gets queued or merged until it runs", bad=oage >= 60 * 60, nobar=True))
    why = ""
    return (f"<h2>The workshop</h2><div class=shop>"
            f"<div class=grp>Who is doing what</div><div class=desks>{fnd}{arch}</div>"
            f"<div class=grp>{_na} agents \u00B7 {len(active)+len(local_act)} working, {_na-len(active)-len(local_act)} on standby</div><div class=m style='margin:-4px 0 8px'>Every agent takes whatever job is next: build a feature, fix review findings, or attack a PR as QA (QA only adds failing tests).</div><div class=desks>{desks}</div>"
            + (f"<div class=queue><span class=ql>Waiting in line</span>{qline}</div>" if queued else "")
            + (f"<div class=m style='margin-top:8px'>{e(why)}</div>" if why else "")
            + (f"<div class=m style='margin-top:6px'>Just finished: {dn}</div>" if dn else "")
            + f"<div class=grp>Hard limits (why things sometimes stand still)</div><div class=lims>{lims}</div></div>")


def log_view():
    """One merged, filterable, scrollable log: architect + dispatcher, last 36 hours, newest first. CSS-only filters (work without JavaScript)."""
    ev = []; seq = 0
    def addlines(src, text):
        nonlocal seq
        last = 0.0
        for ln in text.splitlines():
            if not ln.strip(): continue
            m = re.search(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", ln)
            if m:
                try: last = datetime.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()
                except Exception: pass
            seq += 1
            ev.append((last, seq, "orchestrator" if (src == "architect" and "(orchestrator)" in ln) else src, ln.strip()))
    addlines("architect", read("orchestrator-log.md")); addlines("dispatcher", read("status.md")); addlines("github", read("github.log"))
    cut = now - 36 * 3600
    ev = [x for x in ev if x[0] >= cut]
    ev.sort(key=lambda x: (x[0], x[1]), reverse=True)
    def cls(src, t):
        tl = t.lower()
        if src == "architect":
            if re.search(r"BLOCKER|BLOCKED|never ran|failed|usage limit", t): return "fail"
        elif re.search(r"\bdead\b|gave up|stuck|failed|could not|usage limit|rate limit|error", tl): return "fail"
        if re.search(r"requeue|restart|caution|conflict|warning|stalled", tl): return "warn"
        if tl.startswith("- cleanup") or "cleanup:" in tl: return "house"
        return "info"
    out = []; prev = None; cnt = 0
    def flush():
        if prev is None: return
        t, src, text, c, k = prev
        tm = datetime.datetime.fromtimestamp(t).strftime("%a %-d %b, %-I:%M %p") if t else ""
        out.append(f"<div class='lr {src} {c}'><span class=lt2>{e(tm)}</span><span class=ls>{'Solution architect' if src=='architect' else 'Orchestrator' if src=='orchestrator' else 'GitHub' if src=='github' else 'Dispatcher'}</span>"
                   f"<span class=lx>{e(text)}{f' (x{k})' if k > 1 else ''}</span></div>")
    for t, sq, src, ln in ev:
        text = re.sub(r"^-\s*", "", ln)
        text = re.sub(r"\s*\(?(scheduled run|interactive[^)]*)\)?\s*", " ", text, count=1) if src == "architect" else re.sub(r"^\(orchestrator\)\s*", "", text) if src == "orchestrator" else text
        text = re.sub(r"\s*\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", "", text).strip()
        c = cls(src, text)
        if prev and prev[1] == src and prev[2] == text: prev = (prev[0], src, text, c, prev[4] + 1); continue
        flush(); prev = (t, src, text, c, 1)
    flush()
    body = "".join(out[:500]) or "<div class=m>Nothing in the last 36 hours.</div>"
    return ("<h2>Activity log (last 36 hours, newest first; times are __CITY__)</h2><div class=lfw>"
            "<input type=radio name=lf id=lf_all checked><label for=lf_all class=tab>All</label>"
            "<input type=radio name=lf id=lf_arch><label for=lf_arch class=tab>Solution architect (auto reviewer)</label>"
            "<input type=radio name=lf id=lf_orch><label for=lf_orch class=tab>Orchestrator (Cowork chat)</label>"
            "<input type=radio name=lf id=lf_disp><label for=lf_disp class=tab>Dispatcher</label>"
            "<input type=radio name=lf id=lf_gh><label for=lf_gh class=tab>GitHub (merges, PRs, issues)</label>"
            "<input type=radio name=lf id=lf_fail><label for=lf_fail class=tab>Failures</label>"
            "<input type=radio name=lf id=lf_warn><label for=lf_warn class=tab>Warnings</label>"
            "<input type=radio name=lf id=lf_nohouse><label for=lf_nohouse class=tab>Hide housekeeping</label>"
            f"<div class='scroll logbox'>{body}</div></div>")

def agents_view():
    return ("<h2>Agents and queue</h2><div class=afw>"
            "<input type=radio name=af id=af_all checked><label for=af_all class=tab>All</label>"
            "<input type=radio name=af id=af_run><label for=af_run class=tab>Running</label>"
            "<input type=radio name=af id=af_q><label for=af_q class=tab>Queued</label>"
            "<input type=radio name=af id=af_dead><label for=af_dead class=tab>Not running</label>"
            "<input type=radio name=af id=af_done><label for=af_done class=tab>Finished</label>"
            "<div class=scroll style='max-height:50vh'><table><tr class=hd><th>Status</th><th>Agent</th><th>What it is working on</th><th>Time</th><th>Result / what it is doing</th><th>Next step</th></tr>"
            + agents + "</table></div></div>")

_lm = limit_msg()
limit_banner = ("<div class=pause style='background:#FDECEA;border-color:#C0392B'>Usage limit hit: " + e(_lm) + ". Agents are paused and the dispatcher retries every 30 minutes.</div>") if _lm else ""
page = f"""<!doctype html><html><head><meta charset=utf-8><meta http-equiv=refresh content=20><title>__PROJECT__ build status</title><style>
body{{font:14px -apple-system,Segoe UI,Roboto,sans-serif;background:#F6F8FC;color:#16213A;margin:0;padding:24px 28px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:15px;margin:26px 0 8px}} .m{{color:#5B6785;font-size:12px}}
table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #DDE3F0;border-radius:10px;overflow:hidden}}
td{{padding:8px 10px;border-top:1px solid #EDF0F7;vertical-align:top}} tr:first-child td{{border-top:0}} .hd+tr td{{border-top:0}}
.b{{color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:12px;white-space:nowrap}}
.cards{{display:flex;gap:10px;margin:14px 0}} .c{{background:#fff;border:1px solid #DDE3F0;border-radius:10px;padding:10px 16px;min-width:120px}}
.c b{{font-size:24px;display:block}} ul{{margin:0;padding-left:18px}} li{{margin:3px 0}} a{{color:#2F6FDE}}
.warn{{border-color:#C0392B;color:#C0392B}}
.hd th{{background:#16213A;color:#fff;font-size:11px;text-align:left;padding:7px 10px;text-transform:uppercase;letter-spacing:.5px}}
.sum{{background:#fff;border:1px solid #DDE3F0;border-radius:10px;padding:6px 18px;font-size:14px;line-height:1.5}} .sum h3{{font-size:13px;margin:12px 0 2px;color:#2F6FDE;text-transform:uppercase;letter-spacing:.5px}} .sum p{{margin:4px 0}}
.bar{{display:flex;gap:8px;align-items:center;margin:8px 0;flex-wrap:wrap}} .tab{{border:1px solid #DDE3F0;background:#fff;border-radius:18px;padding:5px 13px;cursor:pointer;font-size:13px}}
.tab.on{{background:#16213A;color:#fff;border-color:#16213A}} .tab i{{font-style:normal;opacity:.7;margin-left:4px}} input{{border:1px solid #DDE3F0;border-radius:18px;padding:6px 12px;font-size:13px;min-width:220px}}
.scroll{{max-height:55vh;overflow-y:auto;border:1px solid #DDE3F0;border-radius:10px}} .scroll .hd th{{position:sticky;top:0}} .cat{{background:#EDF0F7;border-radius:10px;padding:2px 8px;font-size:11px;white-space:nowrap}}
.shop{{background:#fff;border:1px solid #DDE3F0;border-radius:14px;padding:16px 18px}} .desks{{display:flex;gap:14px;flex-wrap:wrap}}
.desk{{width:170px;border-radius:14px;padding:10px 8px 8px;text-align:center;position:relative}} .desk.on{{background:#E9F6F3;border:2px solid #1F9D8B}} .desk.on.qa{{background:#EEF3FD;border-color:#2F6FDE}} .desk.on.fix{{background:#FFF5E6;border-color:#E8892B}}
.desk.off{{background:#F4F6FA;border:2px dashed #C9D3EA;opacity:.85}} .desk.bad{{background:#FDECEA;border:2px solid #C0392B}}
.fig{{font-size:44px;line-height:1.1}} .desk.on .fig{{animation:bob .7s ease-in-out infinite}} .desk.bad .fig{{animation:shake .4s linear infinite}} .desk.off .fig{{animation:sleep 3s ease-in-out infinite}}
.kb{{font-size:20px;animation:tap .35s steps(2) infinite}} .nm{{font-weight:700;font-size:13px}} .sb{{font-size:11px;color:#5B6785}}
.dots{{margin-top:4px}} .dots i{{display:inline-block;width:6px;height:6px;border-radius:50%;background:#1F9D8B;margin:0 2px;animation:blink 1s infinite}} .dots i:nth-child(2){{animation-delay:.2s}} .dots i:nth-child(3){{animation-delay:.4s}}
.zz{{font-weight:700;color:#8A94AD;font-size:16px;height:20px}} .zz span{{display:inline-block;animation:zz 2s ease-in-out infinite;margin-left:2px}}
.queue{{display:flex;gap:8px;align-items:flex-end;margin-top:14px;flex-wrap:wrap;border-top:1px dashed #DDE3F0;padding-top:10px}} .ql{{font-size:11px;color:#5B6785;text-transform:uppercase;letter-spacing:.5px;margin-right:6px}}
.qp{{text-align:center;width:70px}} .fig2{{font-size:28px;animation:wait 2.4s ease-in-out infinite}} .qp .nm{{font-size:11px}} .dn{{margin-right:10px;white-space:nowrap}}
@keyframes bob{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-5px)}}}} @keyframes tap{{0%{{transform:translateY(0)}}100%{{transform:translateY(2px)}}}} @keyframes blink{{0%,100%{{opacity:.2}}50%{{opacity:1}}}}
@keyframes shake{{0%,100%{{transform:rotate(-6deg)}}50%{{transform:rotate(6deg)}}}} @keyframes sleep{{0%,100%{{transform:rotate(-4deg)}}50%{{transform:rotate(4deg)}}}} @keyframes zz{{0%{{opacity:0;transform:translateY(6px)}}50%{{opacity:1}}100%{{opacity:0;transform:translateY(-8px)}}}} @keyframes wait{{0%,100%{{transform:translateX(0)}}50%{{transform:translateX(4px)}}}}
.ag{{font-size:11px;font-weight:700;color:#5B6785;text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px}} .desk.ollama{{border:2px solid #7B3FE4}} .desk.off.ollama{{background:#F6F0FF}} .desk.ollama .ag{{color:#7B3FE4}} .olp{{display:inline-block;background:#F1EAFE;color:#6B2FD6;font-size:11px;font-weight:700;border-radius:999px;padding:2px 9px;margin:0 6px}} .desk.on.ollama{{background:#F6F0FF;border-color:#7B3FE4}} .olbox{{background:#fff;border:1px solid #D9C8F7;border-radius:14px;padding:12px 14px;margin:6px 0 12px}} .olh{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px}} .olst{{font-weight:600;font-size:13px}} .olg{{display:flex;gap:22px;margin:6px 0}} .olg div{{font-size:12px;color:#6E6E73}} .olg b{{display:block;font-size:20px;color:#1D1D1F}} .olr{{border-top:1px solid #F0E8FB;padding:5px 0;font-size:13px}} .olv{{font-size:11px;font-weight:700;border-radius:999px;padding:1px 8px;margin-left:4px}} .grp{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#5B6785;margin:14px 0 8px}} .grp:first-child{{margin-top:0}} .desk.on.arch{{background:#F3EEFC;border-color:#7B4FD0}} .desk.on.founder{{background:#FFF0F3;border-color:#D6456B}} .desk{{min-width:170px}} .desk.on.founder .fig,.desk.on.arch .fig{{animation:bob 1.4s ease-in-out infinite}}
.lims{{display:flex;gap:10px;flex-wrap:wrap}} .lim{{flex:1;min-width:150px;border:1px solid #DDE3F0;border-radius:12px;padding:8px 10px;background:#FAFBFE}} .lim.hot{{border-color:#C0392B;background:#FDECEA}} .lt{{font-size:11px;color:#5B6785;text-transform:uppercase;letter-spacing:.4px}} .lv{{font-size:20px;font-weight:700}} .ln{{font-size:11px;color:#5B6785;margin-top:3px}}
.meter{{height:6px;background:#E4E9F4;border-radius:4px;overflow:hidden;margin-top:4px}} .meter i{{display:block;height:100%}}
.tabs{{display:flex;gap:8px;margin:18px 0 4px}} .tabs .tab{{font-size:14px;padding:7px 18px}}
.afw input,.lfw input{{display:none}} .afw label,.lfw label{{display:inline-block;margin:0 6px 8px 0}}
.afw input:checked+label,.lfw input:checked+label{{background:#16213A;color:#fff;border-color:#16213A}}
#af_run:checked~.scroll tr.ar:not(.running),#af_q:checked~.scroll tr.ar:not(.queued),#af_dead:checked~.scroll tr.ar:not(.dead),#af_done:checked~.scroll tr.ar:not(.done){{display:none}}
#lf_arch:checked~.logbox .lr:not(.architect),#lf_orch:checked~.logbox .lr:not(.orchestrator),#lf_disp:checked~.logbox .lr:not(.dispatcher),#lf_gh:checked~.logbox .lr:not(.github),#lf_fail:checked~.logbox .lr:not(.fail),#lf_warn:checked~.logbox .lr:not(.warn),#lf_nohouse:checked~.logbox .lr.house{{display:none}}
.logbox{{max-height:55vh;background:#fff}} .lr{{display:flex;gap:10px;padding:6px 10px;border-top:1px solid #EDF0F7;font-size:12.5px;align-items:baseline}} .lr:first-child{{border-top:0}}
.lt2{{color:#5B6785;min-width:128px;flex:none}} .ls{{flex:none;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;border-radius:9px;padding:1px 7px;color:#fff;background:#7B4FD0;min-width:62px;text-align:center}} .lr.dispatcher .ls{{background:#2F6FDE}} .lr.github .ls{{background:#1F9D8B}} .lr.orchestrator .ls{{background:#C2185B}}
.lr.fail{{background:#FDECEA}} .lr.warn{{background:#FFF7E6}} .lr.house{{color:#8A94AD}} .lx{{word-break:break-word}}
.pause{{background:#FFF3CD;border:1px solid #E8B930;border-radius:10px;padding:8px 14px;margin:8px 0;font-weight:600}}
</style></head><body>
<h1>__PROJECT__ build status</h1><div class=m>Updated {stamp}. Refreshes itself every 20 seconds.</div>
<div class=m style="margin:6px 0"><a href="FounderStatus.html">Founder view (pipeline, roadmap, quality)</a> &nbsp;|&nbsp; <a href="https://github.com/__REPO__/issues/new?labels=ops&title=%5Bnote%5D%20&body=Message%20for%20the%20architect%3A%20">Send the architect a note (opens GitHub, works on your phone)</a></div>
{limit_banner}
<!--ATTN-->{attn.banner()}{attn.JS}<!--/ATTN-->
{"<div class=pause>Dev is PAUSED (saving usage). Running agents finish; nothing new starts until you say resume.</div>" if os.path.exists(os.path.join(D, "PAUSED")) else ""}
<div class=cards>
<div class=c><b>{nrun}</b>agents running</div>
<div class=c><b>{sum(1 for r in rows if r[2] in ('queued','starting'))}</b>queued or starting</div>
<div class="c {'warn' if ndead else ''}"><b>{ndead}</b>not running</div>
<div class=c><b>{len(prs) if prs is not None else '?'}</b>open PRs</div></div>
<div id=t1 class=pane>{summary_block()}</div>
<div id=t2 class=pane>
{pipeline_block()}
{metrics_block()}
{agents_view()}
<h2>Open pull requests</h2><table>{prtab}</table>
{log_view()}
{backlog_block()}
</div>
</body></html>"""
page = page.replace("What the orchestrator did", "What the architect did").replace("Orchestrator note", "Architect note").replace("orchestrator", "architect").replace("Claude Code", "Dev/QA agents").replace("Claude in Cowork", "Solution architect")
page = re.sub(r"(?<![/\\w])Claude(?![/\\w.-])", "the architect", page)
tmp = os.path.join(D, "status.html.tmp"); open(tmp, "w").write(page); os.replace(tmp, os.path.join(D, "status.html"))
