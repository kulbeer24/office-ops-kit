#!/usr/bin/env python3
"""founder3d.py: builds dispatch/FounderView3D.html, a 3D __CITY__-office view of the founder view.
Separate page: reads the dispatcher's files and the already-generated FounderStatus.html (read-only), never edits them.
Clicking anything in the office opens the matching Founder view tab in a side drawer (an iframe of FounderStatus.html).
ponytail: stage cards are scraped from FounderStatus.html (the single source of truth for the launch maths); ceiling = a JSON export from launch.py."""
import datetime, html, json, os, re, time
D = os.path.dirname(os.path.abspath(__file__))
def rd(f, d=""):
    try: return open(os.path.join(D, f), encoding="utf-8").read()
    except OSError: return d
def jl(f, d):
    try: return json.loads(rd(f) or "null") or d
    except ValueError: return d
now = time.time()
fs = rd("FounderStatus.html")
def clean(x): return html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
stages = []
m = re.search(r"<div class=lc-path>(.*?)</div></div><h2>", fs, re.S)
for card in re.findall(r'<div class="lc-st([^"]*)">(.*?)</div><div class=w>(.*?)</div></div>', (m.group(1) + "</div>") if m else "", re.S):
    cls, inner, wait = card
    nm = re.search(r"<h4>(.*?)</h4>", inner); tg = re.search(r"<div class=d>(.*?)</div>", inner)
    f = re.search(r'<div class="f ([a-z]*)">(.*?)</div>', inner); pct = re.search(r"width:(\d+)%", inner); gt = re.search(r"<div class=g>(.*?)</div>", inner)
    stages.append(dict(name=clean(nm.group(1)) if nm else "", target=clean(tg.group(1)).replace("Target ", "") if tg else "", status=clean(f.group(2)) if f else "",
                       cls=f.group(1) if f else "", pct=int(pct.group(1)) if pct else 0, gates=clean(gt.group(1)) if gt else "", waiting=clean(wait),
                       state="done" if "done" in cls else ("cur" if "cur" in cls else "")))
launch = jl("cache/launch.json", {})
health = jl("cache/health.json", {}); c = health.get("counts", {})
issues = {str(i["number"]): i for i in jl("cache/issues_live.json", [])}
gl = rd("github.log").splitlines()
titles = {}
for ln in gl:
    mm = re.match(r"- \S+ (?:PR|Issue) #(\d+) opened: (.*?)(?: \(.*\))?$", ln)
    if mm: titles[mm.group(1)] = mm.group(2)
merged_all = set(re.findall(r"PR #(\d+) merged", rd("github.log")))
cut = datetime.datetime.utcfromtimestamp(now - 7 * 86400).strftime("%Y-%m-%dT%H:%M:%SZ")
merged7 = sum(1 for ln in gl if re.match(r"- (\S+Z) PR #\d+ merged", ln) and re.match(r"- (\S+Z)", ln).group(1) >= cut)
closed7 = sum(1 for ln in gl if re.match(r"- (\S+Z) Issue #\d+ closed", ln) and re.match(r"- (\S+Z)", ln).group(1) >= cut)
def parse_job(j):
    mm = re.match(r"(fix|qa)?-?(\d+)$", str(j))
    if not mm: return None
    role = mm.group(1) or "dev"; n = mm.group(2)
    return dict(id=n, issue=n, role=role, title=(issues.get(n) or {}).get("title") or titles.get(n, "Issue " + n), since="")
def _stopped():
    import subprocess
    try:
        o = subprocess.run(["ps", "-axo", "stat=,command="], capture_output=True, text=True, timeout=5).stdout
    except Exception: return set()
    r = set()
    for ln in o.splitlines():
        m = re.match(r"\s*(\S+)\s+(.*)", ln); mm = re.search(r"AGENT-ID-([A-Za-z0-9-]+)\.", ln)
        if m and mm and m.group(1).startswith("T"): r.add(mm.group(1))
    return r
_stp = _stopped()
agents = [a for a in (parse_job(j) for j in c.get("running", [])) if a]
for _a in agents: _a["stopped"] = (_a["id"] in _stp) or (("%s-%s" % (_a["role"], _a["id"])) in _stp)
queued = [a for a in (parse_job(j) for j in c.get("queued", [])) if a][:12]
ready, owner = [], []
for ln in rd("owner_hold.txt").splitlines():
    mm = re.match(r"\s*(\d+)\s*#\s*ready to merge", ln)
    if mm and mm.group(1) not in merged_all: ready.append(dict(pr=mm.group(1), title=titles.get(mm.group(1), "PR " + mm.group(1))))
for ln in rd("owner_tasks.txt").splitlines():
    if ln.startswith("Owner to-do|"): owner.append(ln.split("|", 1)[1].strip())
bugs = sum(1 for i in issues.values() if i.get("state") == "OPEN" and any(l.get("name") == "bug" for l in i.get("labels", [])))
tf7 = 0
try:
    tfdir = os.path.join(D, "inbox", "feedback", "testflight")
    tf7 = sum(1 for f in os.listdir(tfdir) if f.endswith(".md") and now - os.path.getmtime(os.path.join(tfdir, f)) < 7 * 86400)
except OSError: pass
lb = [l for l in rd("last_build.txt").splitlines() if l.strip() and not l.startswith("#")]
ev = []
for ln in rd("orchestrator-log.md").splitlines()[-6:]:
    mm = re.match(r"- (\S+Z) \(([^)]*)\) (.*)", ln)
    if mm: ev.append("%s: %s" % (mm.group(2), mm.group(3)[:160]))
def _age(f):
    try: return now - os.path.getmtime(os.path.join(D, f))
    except OSError: return 1e9
orch_age = 1e9
for ln in reversed(rd("orchestrator-log.md").splitlines()[-200:]):
    mm = re.match(r"- (\S+Z) \((orchestrator|founder via CompanyOS)\)", ln)
    if mm:
        try: orch_age = now - datetime.datetime.strptime(mm.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()
        except ValueError: pass
        break
fr = jl("cache/freshness.json", {}); frbad = [i for i in fr.get("items", []) if not i.get("fixed")]
mel = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=11))).strftime("%a %d %b, %H:%M")
data = dict(ts=int(now), summary=dict(head=launch.get("head", ""), chain_end=launch.get("chain_end", ""), target=launch.get("target", ""), slack=launch.get("slack", ""),
            left=launch.get("left"), items=launch.get("items", 0), work=launch.get("work", ""), need=launch.get("need", 0)),
            stages=stages, ship=launch.get("ship", ""), build=lb[0][:80] if lb else "", owner=owner, ready=ready, agents=agents, queued=queued,
            slots=c.get("slots", 3), paused=bool(c.get("paused")), open_prs=c.get("open_prs", 0), merged7=merged7, closed7=closed7, open_bugs=bugs, tf7=tf7,
            events=ev, thr="", age=mel, arch_busy=_age("cache/architect.run") < 180, orch_busy=orch_age < 900,
            fresh=dict(stale=fr.get("stale", 0), review=fr.get("review", 0), checks=fr.get("checks", 0), items=[i["source"] + ": " + i["what"] for i in frbad[:4]]))
tpl = open(os.path.join(D, "founder3d_tpl.html"), encoding="utf-8").read()
three = open(os.path.join(D, "vendor", "three.min.js"), encoding="utf-8").read()
js = json.dumps(data).replace("</", "<\\/")
out = tpl.replace("/*DATA*/", js, 1).replace("/*THREE*/", three.replace("</script", "<\\/script"), 1)
tmp = os.path.join(D, "FounderView3D.html.tmp"); open(tmp, "w", encoding="utf-8").write(out); os.replace(tmp, os.path.join(D, "FounderView3D.html"))
print("FounderView3D.html: %d stages, %d agents, %d ready, %d owner items" % (len(stages), len(agents), len(ready), len(owner)))
