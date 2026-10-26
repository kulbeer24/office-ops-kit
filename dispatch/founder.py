#!/usr/bin/env python3
"""Founder view: writes dispatch/founder.html (separate from status.html, which stays as the live operations page).
Seven tabs, pure HTML/CSS (works in a phone viewer with no JavaScript): Overview, Pipeline, Roadmap, Delivered, Quality, Optimisation, Systems.
Reads local dispatch files plus GitHub via `gh` (cached 5 min; falls back to older caches when gh is unavailable). Called from run_batch.sh every ~5 minutes."""
import os, re, json, time, html, glob, subprocess, datetime
D = os.path.dirname(os.path.abspath(__file__)); R = "__REPO__"; now = time.time(); e = html.escape
UTC = datetime.timezone.utc
import importlib.util
import attn
import launch, ship
_sp = importlib.util.spec_from_file_location("lab", os.path.join(D, "lab.py")); lab = importlib.util.module_from_spec(_sp)
try: _sp.loader.exec_module(lab); LAB_OK = True
except Exception as _ex: LAB_OK = False; LAB_ERR = str(_ex)
def read(p, d=""):
    try: return open(os.path.join(D, p)).read()
    except Exception: return d
def jl(p, d):
    try: return json.load(open(os.path.join(D, p)))
    except Exception: return d
def ts(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception: return None
def gh(args, cache, ttl=60):
    f = os.path.join(D, "cache", cache); os.makedirs(os.path.dirname(f), exist_ok=True)
    if os.path.exists(f) and now - os.path.getmtime(f) < ttl:
        try: return json.load(open(f))
        except Exception: pass
    try:
        data = json.loads(subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=40).stdout); json.dump(data, open(f, "w")); return data
    except Exception:
        try: return json.load(open(f))
        except Exception: return None
def short(t): return re.sub(r"^(feat|fix|chore|docs|test)(\([^)]*\))?: ", "", t)[:110]
def day(t): return datetime.datetime.fromtimestamp(t).strftime("%a %d %b")

# ---------- data ----------
issues = gh(["issue", "list", "--repo", R, "--state", "all", "--limit", "500", "--json", "number,title,labels,state,createdAt,closedAt"], "issues_live.json")
live_issues = issues is not None
if issues: issues = [i for i in issues if not i['title'].lower().startswith('owner:')]
if not issues:   # offline fallback: older caches (open list known, the rest assumed closed)
    allis = jl("cache/issues.json", []); openn = {x["number"] for x in jl("cache/open_issues.json", [])}
    issues = [{"number": x["number"], "title": x["title"], "labels": [], "state": "OPEN" if x["number"] in openn else "CLOSED", "createdAt": "", "closedAt": ""} for x in allis]
prs = gh(["pr", "list", "--repo", R, "--state", "all", "--limit", "300", "--json", "number,title,headRefName,state,createdAt,mergedAt"], "prs_live.json")
if not prs: prs = jl("cache/prs_all.json", [])
I = {str(i["number"]): i for i in issues}; title = lambda n: I.get(str(n), {}).get("title", "")
merged = [p for p in prs if p.get("mergedAt")]; openprs = [p for p in prs if p.get("state") == "OPEN"]
iss_of = lambda p: (re.match(r"(\d+)-", p.get("headRefName", "")) or [None, None])[1]
M = jl("metrics/summary.json", {"issues": [], "totals": {}})
MI = {o["issue"]: o for o in M.get("issues", [])}
started = set(os.listdir(os.path.join(D, "started"))) if os.path.isdir(os.path.join(D, "started")) else set()
donef = set(os.listdir(os.path.join(D, "done"))) if os.path.isdir(os.path.join(D, "done")) else set()
batch = [l.strip() for l in read("batch.txt").splitlines() if l.strip() and not l.startswith("#")]
tf = sorted(glob.glob(os.path.join(D, "inbox", "feedback", "testflight", "*.md")))
fb_days = {}
for f in tf:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", os.path.basename(f))
    if m: fb_days[m.group(1)] = fb_days.get(m.group(1), 0) + 1

def stage(n):
    n = str(n); it = I.get(n)
    if it and it["state"] == "CLOSED": return "Merged"
    if any(iss_of(p) == n for p in openprs):
        fx = f"fix-{n}"; fixing = (fx in started and fx not in donef) or (fx in batch and fx not in started)
        return "Fix round" if fixing else "In review / QA"
    if n in started and n not in donef: return "In build"
    if LAB_OK and n in donef and lab.blocked_reason(n): return "Blocked"
    if n in batch and n not in started: return "Queued"
    return "Planned"
STG = {"Planned": ("#636366", "#F2F2F7"), "Queued": ("#3A3A3C", "#E9E9EE"), "In build": ("#1F8A3B", "#E8F8EE"), "In review / QA": ("#0A60C2", "#E8F1FD"), "Fix round": ("#B35C00", "#FFF3E0"), "Blocked": ("#C4281C", "#FDECEA"), "Merged": ("#1F8A3B", "#DDF3E4")}
def chip(s):
    fg, bg = STG.get(s, ("#636366", "#F2F2F7"))
    return f'<span class=b style="background:{bg};color:{fg}"><i style="background:{fg}"></i>{e(s)}</span>'
def bar(done, tot, col="#0071E3"):
    pc = 0 if not tot else round(100 * done / tot)
    return f'<div class=meter><i style="width:{pc}%;background:{col}"></i></div>'
ICONS = {
 "overview": '<rect x="3.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.8"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.8"/>',
 "ops": '<polyline points="3 12 7.5 12 10 5.5 14 18.5 16.5 12 21 12"/>',
 "pipeline": '<path d="M4 6.5h16M4 12h11M4 17.5h6"/>',
 "roadmap": '<path d="M5.5 21V4"/><path d="M5.5 4.5h11.5l-2.3 3.8 2.3 3.7H5.5"/>',
 "delivered": '<circle cx="12" cy="12" r="9"/><path d="M8.2 12.4l2.6 2.6 5-5.4"/>',
 "quality": '<path d="M12 3l7.5 3v5.8c0 4.4-3.1 7.4-7.5 9.2-4.4-1.8-7.5-4.8-7.5-9.2V6z"/><path d="M8.8 12l2.2 2.2 4.2-4.4"/>',
 "optimisation": '<polyline points="3.5 17 9.5 11 13.5 15 20.5 7.5"/><polyline points="15 7.5 20.5 7.5 20.5 13"/>',
 "launch": '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6v3H9z"/><path d="M9 14l2 2 4-4"/>',
 "success": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r=".8"/>',
 "systems": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
 "merge": '<circle cx="6" cy="6" r="2.4"/><circle cx="6" cy="18" r="2.4"/><circle cx="18" cy="12" r="2.4"/><path d="M6 8.4v7.2"/><path d="M8.4 6c5.4 0 7.2 2.6 7.2 6"/>',
 "check": '<circle cx="12" cy="12" r="9"/><path d="M8.2 12.4l2.6 2.6 5-5.4"/>',
 "pr": '<circle cx="6" cy="6" r="2.4"/><circle cx="6" cy="18" r="2.4"/><circle cx="18" cy="18" r="2.4"/><path d="M6 8.4v7.2"/><path d="M18 15.6V10a3 3 0 0 0-3-3h-2.5"/><path d="M15 4.5L12.5 7 15 9.5"/>',
 "chat": '<path d="M4.5 5.5h15v10.5h-9l-4.5 3.5V16h-1.5z"/>',
 "bug": '<rect x="8" y="8" width="8" height="11" rx="4"/><path d="M12 8V5.5M4 13h4M16 13h4M5.5 7l2.8 2M18.5 7l-2.8 2M5.5 19l2.8-2M18.5 19l-2.8-2"/>',
 "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.2l3.2 2"/>',
 "repeat": '<path d="M4 11V9a3 3 0 0 1 3-3h11"/><path d="M15 3l3 3-3 3"/><path d="M20 13v2a3 3 0 0 1-3 3H6"/><path d="M9 21l-3-3 3-3"/>',
 "chart": '<path d="M4 20V10M10 20V4M16 20v-7M21 20H3"/>',
 "chev": '<path d="M9 5.5l6.5 6.5L9 18.5"/>',
}
ICONS.update({"groom": '<path d="M4 7h10M4 12h16M4 17h7"/><circle cx="18" cy="7" r="2"/>', "journey": '<path d="M5 19c0-6 14-2 14-8"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="6" r="1.6"/>', "up": '<path d="M6 15l6-6 6 6"/>', "down": '<path d="M6 9l6 6 6-6"/>'})
def icon(n, cls="ic"): return f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(n, ICONS["chart"])}</svg>'
def icon_for(label):
    l = label.lower()
    for k, v in (("merged", "merge"), ("closed", "check"), ("open pr", "pr"), ("feedback", "chat"), ("bug", "bug"), ("start to merge", "clock"), ("rounds", "repeat")):
        if k in l: return v
    return "chart"
TINT = [("#E8F1FD", "#0A60C2"), ("#E8F8EE", "#1F8A3B"), ("#FFF3E0", "#B35C00"), ("#F2F2F7", "#3A3A3C"), ("#FDECEA", "#C4281C")]
def cards(items):
    out = []
    for n_, it in enumerate(items):
        k, v = it[0], it[1]; h = it[2] if len(it) > 2 else None; bg, fg = TINT[n_ % len(TINT)]
        top = f'<span class=it style="background:{bg};color:{fg}">{icon(icon_for(k))}</span>'
        if h: out.append(f'<a class=c href="{e(h)}"{" target=_blank" if h.startswith("http") else ""}>{top}<b>{v}</b><span class=cl>{e(k)}</span><span class=go>View {icon("chev", "ic s")}</span></a>')
        else: out.append(f'<div class=c>{top}<b>{v}</b><span class=cl>{e(k)}</span></div>')
    return "<div class=cards>" + "".join(out) + "</div>"
GH = f"https://github.com/{R}"; d7 = datetime.datetime.utcfromtimestamp(now - 7 * 86400).strftime("%Y-%m-%d"); d14 = datetime.datetime.utcfromtimestamp(now - 14 * 86400).strftime("%Y-%m-%d"); d_prev = datetime.datetime.utcfromtimestamp(now - 14 * 86400).strftime("%Y-%m-%d")
FBDIR = "inbox/feedback/testflight/"
def link(n, kind="issues"): return f'<a href="https://github.com/{R}/{kind}/{n}">#{n}</a>'
wk = 7 * 86400
mw = [p for p in merged if now - ts(p["mergedAt"]) < wk]; mp = [p for p in merged if wk <= now - ts(p["mergedAt"]) < 2 * wk]
cl = [i for i in issues if i.get("closedAt") and now - (ts(i["closedAt"]) or 0) < wk] if live_issues else None

# pipeline rows
PL = []
for l in read("pipeline.txt").splitlines():
    p = [x.strip() for x in l.split("|")]
    if l.startswith("#") or len(p) < 4: continue
    PL.append(p[:4])
cur = next((w for w, n, *_ in PL if stage(n) != "Merged"), "All waves merged")

# ---------- detail views (shown inside this page when a card is clicked) ----------
DET = {}
def detail(did, parent, ttl, body): DET[did] = (parent, ttl, body)
def when(t): return day(ts(t)) if t and ts(t) else ""
def prt(ps, key="mergedAt"):
    r = "".join(f'<tr><td>{link(p["number"], "pull")}</td><td>{e(short(p["title"]))}</td><td class=m>{when(p.get(key))}</td></tr>' for p in sorted(ps, key=lambda p: -(ts(p.get(key) or p.get("createdAt") or "") or 0)))
    return f'<div class=sbox><table class=t><tr class=hd><th>PR</th><th>What</th><th>{"Merged" if key == "mergedAt" else "Opened"}</th></tr>{r or "<tr><td colspan=3>None.</td></tr>"}</table></div>'
def ist(its):
    r = "".join(f'<tr><td>{link(i["number"])}</td><td>{e(i["title"][:110])}</td><td class=m>{when(i.get("closedAt") or i.get("createdAt"))}</td></tr>' for i in its)
    return f'<div class=sbox><table class=t><tr class=hd><th>Issue</th><th>What</th><th>Date</th></tr>{r or "<tr><td colspan=3>None.</td></tr>"}</table></div>'
def fbl():
    out = []
    for f in reversed(tf):
        t = read(os.path.relpath(f, D)); m = re.search(r"\*\*Comment:\*\*\s*(.*)", t); dm = re.match(r"(\d{4}-\d{2}-\d{2})", os.path.basename(f))
        out.append(f'<tr><td class=m>{dm.group(1) if dm else ""}</td><td>{e((m.group(1) if m else "(no comment)")[:260])}</td></tr>')
    return f'<div class=sbox><table class=t><tr class=hd><th>Date</th><th>What the tester said</th></tr>{"".join(out) or "<tr><td colspan=2>None yet.</td></tr>"}</table></div>'
slug = lambda x: re.sub(r"[^a-z]+", "", x.lower())
detail("d-merged7", "overview", "PRs merged in the last 7 days", prt(mw))
detail("d-closed7", "overview", "Issues closed in the last 7 days", ist(cl) if cl is not None else "<div class=m>No GitHub access right now, so this list is unavailable.</div>")
detail("d-openprs", "overview", "Open pull requests", prt(openprs, "createdAt"))
detail("d-feedback", "quality", "Tester feedback (newest first)", fbl())
detail("d-merged14", "delivered", "PRs merged in the last 14 days", prt([p for p in merged if now - ts(p["mergedAt"]) < 14 * 86400]))
detail("d-mergedall", "delivered", "All merged PRs", prt(merged))
detail("d-openbugs", "quality", "Open bugs", ist([i for i in issues if i["state"] == "OPEN" and any((l["name"] if isinstance(l, dict) else l) == "bug" for l in i.get("labels", []))]))

# ---------- panes ----------
EXTRA_CSS = ".vl{float:right;font-size:13px;font-weight:500;color:#0071E3;text-decoration:none;letter-spacing:0;text-transform:none}.lc-strip{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin:12px 0 4px;padding:12px 16px;background:#fff;border-radius:16px;box-shadow:0 0 0 .5px rgba(0,0,0,.08);color:#1D1D1F;text-decoration:none;font-size:13.5px}.lc-strip span{margin-left:auto;color:#0071E3}input[type=radio]{display:none}.sbox{position:relative;max-height:min(60vh,520px);overflow:auto;background:#fff;border-radius:20px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05);overscroll-behavior:contain;-webkit-overflow-scrolling:touch;scrollbar-width:thin}.sbox table{box-shadow:none;border-radius:0;min-width:0;width:100%}.sbox.wide table{min-width:760px}.sbox .hd th{position:sticky;top:0;background:#fff;z-index:1;box-shadow:0 1px 0 #EDEDF0}.sbox.tall{max-height:min(60vh,520px)}.sbox.flow{max-height:none}.glane td.grp{background:#F5F5F7;padding:10px 14px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#6E6E73}.glane .m{text-transform:none;letter-spacing:0;margin-left:8px}"
def filter_css(pfx, keys, rowsel, hide_groups=True):
    c = ""
    for k in keys:
        c += f"#{pfx}-{k}:checked~.pt tr.r:not(.{rowsel}{k}){{display:none}}#{pfx}-{k}:checked~.cards label[for={pfx}-{k}]{{box-shadow:0 0 0 2px #0071E3,0 6px 18px rgba(0,113,227,.14);background:#F5FAFF}}"
    c += f"#{pfx}-all:checked~.cards label[for={pfx}-all]{{box-shadow:0 0 0 2px #0071E3,0 6px 18px rgba(0,113,227,.14);background:#F5FAFF}}"
    if hide_groups: c += f"input[name={pfx}]:not(#{pfx}-all):checked~.pt tr.glane{{display:none}}"
    return c
def pipeline():
    global EXTRA_CSS
    why_of = {str(n).replace("#", ""): (what, why) for w, n, what, why in PL}
    def eff(n, st_):
        o = MI.get(str(n))
        if not o: return "", "", ""
        a_, pj = o["active_min"], o.get("projected_min")
        t_ = ("running" if o.get("running") and not a_ else (fmt_min(a_) if a_ else "0m")) + (f' / {fmt_min(pj)}' if pj else " / no estimate")
        why = []
        qr, fr, rs, fd, el = o.get("qa_rounds", 0), o.get("fix_rounds", 0), o.get("restarts", 0) or 0, o.get("findings", 0), o.get("elapsed_min")
        br = lab.blocked_reason(n) if LAB_OK else ""
        if br: why.append("Stopped early. Blocked: " + br[:110])
        elif not a_ and not o.get("running"): why.append("Not started yet" + (" (waiting for a free slot)" if st_ == "Queued" else ""))
        elif not pj and o.get("running"): why.append("Running now; no estimate was made for this one")
        elif not pj: why.append("No estimate was made for this one (it was queued before estimates started)")
        elif st_ in ("In build", "In review / QA", "Fix round") and a_ < pj * 0.9 and o.get("running"): why.append(f"Still running: {round(100 * a_ / pj)}% of the estimate used")
        elif a_ <= pj * 1.1 and a_ >= pj * 0.5: why.append("On estimate")
        elif a_ < pj * 0.5: why.append("Much quicker than typical so far" + (" (QA not run yet)" if qr == 0 and st_ == "In review / QA" else ""))
        else:
            if qr: why.append(f"{qr} QA round{'s' if qr > 1 else ''} found {fd} bug{'s' if fd != 1 else ''}")
            if fr: why.append(f"{fr} fix round{'s' if fr > 1 else ''} to repair them")
            if rs: why.append(f"{rs} restart{'s' if rs > 1 else ''} lost time")
            if o.get("time_unknown_runs"): why.append("some runs have no recorded end time")
            if not why: why.append("Bigger than a typical job")
        if el and a_ and el > 2 * a_ and el - a_ > 60: why.append(f"waited about {fmt_min(el - a_)} between steps (queue, review or limits)")
        return t_, "; ".join(why[:3]), fmt_tok(o["tokens_new"]) if o.get("tokens_new") else ""
    lanes_ = []
    if LAB_OK:
        for k_, name_, hint_ in lab.LAN:
            its = [(i["number"], short(i["title"])) for i in lab.lanes[k_]]
            if its: lanes_.append((name_, hint_, its))
    done_ = [(int(str(n).replace("#", "")), what) for w, n, what, why in PL if stage(n) == "Merged"]
    if done_: lanes_.append(("Done", "Merged from the plan.", done_))
    cnt = {s_: 0 for s_ in STG}; rows = []; total = 0
    for name_, hint_, its in lanes_:
        rows.append(f'<tr class=glane><td colspan=6 class=grp>{e(name_)} <span class=m>{e(hint_)}</span></td></tr>')
        for n, ttl in its:
            s_ = stage(n); cnt[s_] += 1; total += 1; w_ = why_of.get(str(n)); t_, y_, k_ = eff(n, s_)
            what_ = w_[0] if w_ else ttl
            rows.append(f'<tr class="r st-{slug(s_)}"><td>{link(n)}</td><td>{e(what_)}' + (f'<div class=m>{e(w_[1])}</div>' if w_ else '') + f'</td><td>{chip(s_)}</td><td class=m>{e(t_)}</td><td class=m>{e(y_)}</td><td class=m>{e(k_)}</td></tr>')
    keys = [slug(k) for k in STG]; EXTRA_CSS += filter_css("pf", keys, "st-")
    radios = '<input type=radio name=pf id=pf-all checked>' + "".join(f'<input type=radio name=pf id=pf-{k}>' for k in keys)
    cds = f'<div class=cards><label class=c for=pf-all><b>{total}</b>All<span class=go>show everything</span></label>' + "".join(f'<label class=c for=pf-{slug(k)}><b>{v}</b>{e(k)}<span class=go>show only these</span></label>' for k, v in cnt.items()) + '</div>'
    return (radios + cds + '<div class=m style="margin:2px 0 10px">Same order as the Prioritise tab: set priorities there, track delivery here. Actual is agent working time so far, Planned is the estimate made when the job was queued; tokens are new work.</div>'
            f'<div class="sbox wide flow pt"><table class=t><tr class=hd><th>Issue</th><th>What and why now</th><th>Stage</th><th>Actual / Planned</th><th>Why the difference</th><th>Tokens</th></tr>{"".join(rows)}</table></div>')
EP = [[x.strip() for x in l.split("|")] for l in read("roadmap.txt").splitlines() if l.strip() and not l.startswith("#")]
def epic_of(t):
    t = t.lower()
    for ep in EP:
        if any(k.strip() and k.strip() in t for k in ep[1].split(",")): return ep[0]
    return None
def optimisation():
    rows = []
    for l in read("optimisations.txt").splitlines():
        p = [x.strip() for x in l.split("|")]
        if l.startswith("#") or len(p) < 3: continue
        rows.append(f'<tr><td>{chip("Merged") if p[0] == "done" else chip("Planned")}</td><td>{e(p[1])}</td><td class=m>{e(p[2])}</td></tr>')
    return f'<div class=sbox><table class=t><tr class=hd><th></th><th>What</th><th>Measured effect or expected payoff</th></tr>{"".join(rows)}</table></div><div class=m>Green = done, grey = next in line (ranked top to bottom).</div>'
def systems():
    L = [("GitHub repo", f"https://github.com/{R}"), ("Open issues", f"https://github.com/{R}/issues"), ("Open pull requests", f"https://github.com/{R}/pulls"), ("GitHub Actions usage and budgets", "https://github.com/settings/billing"),
         ("Live operations page", "status.html")]
    addr = read("cache/serve.url").strip()
    note = (f'<div class=box style="margin-bottom:14px"><h3>Phone address (private, via Tailscale)</h3><div>{e(addr)}</div><div class=m>Open it in Safari while Tailscale is on, then Share and Add to Home Screen.</div></div>' if addr else '<div class=box style="margin-bottom:14px"><h3>Phone address</h3><div class=m>Not running yet. Start the dispatcher after installing Tailscale.</div></div>')
    try:
        fr = json.load(open(os.path.join(D, "cache", "freshness.json"))); bad = [i for i in fr["items"] if not i.get("fixed")]; fx = [i for i in fr["items"] if i.get("fixed")]
        col = "#C4281C" if fr["stale"] else ("#B25E00" if fr["review"] else "#1F8A3B")
        head = ("%d out of date, %d to review" % (fr["stale"], fr["review"])) if bad else "All %d freshness checks passed" % fr["checks"]
        rows = "".join('<li><b>%s</b> (%s): %s <span class=m>%s</span></li>' % (e(i["source"]), "out of date" if i["sev"] == "stale" else "review", e(i["what"]), e("Fix: " + i["fix"])) for i in bad)
        rows += "".join('<li class=m>Fixed automatically: %s: %s</li>' % (e(i["source"]), e(i["what"])) for i in fx)
        fresh = (f'<div class=box style="margin-bottom:14px"><h3>Data freshness</h3><div style="color:{col};font-weight:600">{e(head)}</div><div class=m>Checked {e(time.strftime("%a %d %b, %I:%M %p", time.localtime(fr["ts"])))}. '
                 f'Checks every cycle: dispatcher heartbeat, page refresh ages, waiting-for-you list, priorities, release gates, build record, targets and hand-written files. The Orchestrator reviews daily and weekly.</div>' + (f'<ul>{rows}</ul>' if rows else '') + '</div>')
    except Exception:
        fresh = '<div class=box style="margin-bottom:14px"><h3>Data freshness</h3><div class=m>No freshness report yet. It appears after the next dispatcher cycle.</div></div>'
    return fresh + note + "<ul>" + "".join(f'<li><a href="{u}">{e(n)}</a></li>' for n, u in L) + "</ul>"

import math
def targets():
    out = {}
    for l in read("targets.txt").splitlines():
        p = [x.strip() for x in l.split("|")]
        if l.startswith("#") or len(p) < 3: continue
        try: out[p[0]] = (datetime.datetime.strptime(p[1], "%Y-%m-%d").timestamp(), p[2])
        except Exception: pass
    return out
def wk0(t):
    d = datetime.datetime.fromtimestamp(t); return (d - datetime.timedelta(days=d.weekday())).date()
def lbl(x): return x["name"] if isinstance(x, dict) else x
def donut(pct, col, big, small):
    r = 44; c = 2 * math.pi * r; d = c * max(0, min(100, pct)) / 100
    return (f'<svg viewBox="0 0 120 120" width=150 height=150><circle cx=60 cy=60 r=44 fill=none stroke="#EDEDF2" stroke-width=9 />'
            f'<circle cx=60 cy=60 r=44 fill=none stroke="{col}" stroke-width=9 stroke-linecap=round stroke-dasharray="{d:.1f} {c:.1f}" transform="rotate(-90 60 60)" />'
            f'<text x=60 y=62 text-anchor=middle font-size=26 font-weight=600 fill="#1D1D1F">{big}</text><text x=60 y=79 text-anchor=middle font-size=10 fill="#6E6E73">{e(small)}</text></svg>')
def pie(parts, size=130):
    tot = sum(v for _, v, _ in parts) or 1; r = 42; c = 2 * math.pi * r; cum = 0; out = ""; many = sum(1 for _, v, _ in parts if v > 0) > 1
    for n_, v, col in parts:
        if v <= 0: continue
        L = c * v / tot; seg = max(0.5, L - (2.5 if many else 0))
        out += f'<circle cx=60 cy=60 r={r} fill=none stroke="{col}" stroke-width=12 stroke-dasharray="{seg:.1f} {c - seg:.1f}" stroke-dashoffset="{-cum:.1f}" transform="rotate(-90 60 60)" />'; cum += L
    leg = "".join(f'<div class=lg><span class=sw style="background:{col}"></span><span>{e(n_)}</span><b>{v}</b></div>' for n_, v, col in parts)
    return f'<div class=pw><svg viewBox="0 0 120 120" width={size} height={size}><circle cx=60 cy=60 r={r} fill=none stroke="#EDEDF2" stroke-width=12 />{out}<text x=60 y=66 text-anchor=middle font-size=22 font-weight=600 fill="#1D1D1F">{sum(v for _, v, _ in parts)}</text></svg><div class=lgs>{leg}</div></div>'
def bars(groups, colors, names, need=None, h=190):
    n = max(1, len(groups)); gw = 118 if n <= 10 else 64; W = gw * n + 30; mx = max([max(v) for _, v in groups] + [need or 0, 1]) * 1.15; out = f'<line x1=10 x2={W} y1={h - 24} y2={h - 24} stroke="#E5E5EA" />'
    bw = 30 if len(colors) > 1 else 44
    for k, (lab, vs) in enumerate(groups):
        x0 = 20 + k * gw + (gw - bw * len(vs) - 4 * (len(vs) - 1)) / 2
        for j, v in enumerate(vs):
            bh = max(0, (h - 54) * v / mx); x = x0 + j * (bw + 4)
            out += f'<rect x={x:.1f} y={h - 24 - bh:.1f} width={bw} height={max(bh, 0.1):.1f} fill="{colors[j]}" rx=5 />'
            if v: out += f'<text x={x + bw / 2:.1f} y={h - 29 - bh:.1f} text-anchor=middle font-size=10 font-weight=500 fill="#3A3A3C">{v}</text>'
        out += f'<text x={20 + k * gw + gw / 2:.1f} y={h - 7} text-anchor=middle font-size=10 fill="#8E8E93">{e(lab)}</text>'
    if need:
        y = h - 24 - (h - 54) * need / mx; out += f'<line x1=10 x2={W} y1={y:.1f} y2={y:.1f} stroke="#FF3B30" stroke-width=1 stroke-dasharray="3 4" /><text x={W} y={y - 5:.1f} text-anchor=end font-size=10 fill="#C4281C">Needed: {need:.0f} a week</text>'
    leg = "".join(f'<span class=lg2><span class=sw style="background:{colors[j]}"></span>{e(names[j])}</span>' for j in range(len(names)))
    return f'<svg viewBox="0 0 {W + 10} {h}" width="100%" style="max-width:{W + 10}px">{out}</svg><div class=lgrow>{leg}</div>'
def hbars(items, col="#0071E3", w=700, lw=330, linkit=False, unit=None):
    out = ""
    for k, (lab, v, t) in enumerate(items):
        pc = 0 if not t else 100 * v / t; y = 6 + k * 30; bw = w - lw - 90
        txt = lab if len(lab) <= 46 else lab[:45].rstrip() + "\u2026"
        mm = re.match(r"#(\d+)", lab)
        tx = f'<text x=0 y={y + 9} font-size=12 fill="#1D1D1F"><title>{e(lab)}</title>{e(txt)}</text>'
        if linkit and mm: tx = f'<a href="https://github.com/{R}/issues/{mm.group(1)}" target=_blank>{tx}</a>'
        out += tx + f'<rect x={lw} y={y} width={bw} height=8 rx=4 fill="#EDEDF2" /><rect x={lw} y={y} width={max(0, bw * pc / 100):.1f} height=8 rx=4 fill="{col}" /><text x={w - 6} y={y + 9} text-anchor=end font-size=12 fill="#6E6E73">{(str(v) + " " + (unit if v != 1 else unit.rstrip("s"))) if unit else str(v) + " of " + str(t)}</text>'
    return f'<svg viewBox="0 0 {w} {len(items) * 30 + 6}" width="100%" style="max-width:{w}px">{out}</svg>'
def stats():
    T = targets(); tl, tb = T.get("launch"), T.get("build")
    scope = [i for i in issues if epic_of(i["title"]) not in (None, "Quality, release and ops") and not i["title"].lower().startswith(("[note]", "backlog")) and "status:deferred" not in [lbl(x) for x in i.get("labels", [])]]
    closed = [ts(i["closedAt"]) for i in scope if i.get("closedAt") and ts(i["closedAt"])]
    opened = [ts(i["createdAt"]) for i in scope if i.get("createdAt") and ts(i["createdAt"])]
    cur = wk0(now); weeks = [cur - datetime.timedelta(days=7 * k) for k in range(7, -1, -1)]
    cnt = lambda L: [sum(1 for t in L if wk0(t) == w) for w in weeks]
    wc, wo = cnt(closed), cnt(opened); wm = cnt([ts(p["mergedAt"]) for p in merged])
    full = wc[-4:-1]; full_o = wo[-4:-1]
    cl_rate = sum(full) / max(1, len(full)); op_rate = sum(full_o) / max(1, len(full_o))
    rem = sum(1 for i in scope if i["state"] == "OPEN"); dn = len(scope) - rem
    return dict(T=T, tl=tl, tb=tb, weeks=weeks, wc=wc, wo=wo, wm=wm, cl=cl_rate, op=op_rate, net=cl_rate - op_rate, rem=rem, dn=dn, tot=len(scope))
def ms_timeline(stages, now, launch_ts):
    """Timeline to launch from the same stages as the road-to-launch cards. Ring = target date, dot = forecast (green on time, red late, blue done).
    Each milestone gets a card; cards alternate above/below the line and are pushed apart so text never overlaps."""
    st = [x for x in stages if x.get("tgt") or x.get("fin")]
    if not st: return None
    W, H, AX = 164, 54, 108
    pts = [now] + [x["tgt"] for x in st if x.get("tgt")] + [x["fin"] for x in st if x.get("fin")] + ([launch_ts] if launch_ts else [])
    t0 = min(now - 6 * 86400, min(pts) - 3 * 86400); t1 = max(pts) + 4 * 86400
    X = lambda t: 30 + 740 * max(0, min(1, (t - t0) / (t1 - t0)))
    short_ = lambda n: re.sub(r"\s*\(.*", "", n)
    items = []
    for k, x in enumerate(st):
        tg, fn_ = x.get("tgt"), x.get("fin"); pos = fn_ or tg; done = bool(x.get("done"))
        late = bool(fn_ and tg and fn_ > tg + 43200); dl = round((fn_ - tg) / 86400) if late else 0
        col, tint = ("#0071E3", "#E6F0FD") if done else (("#C4281C", "#FDECEA") if late else ("#1F8A3B", "#E8F8EE"))
        status = "done" if done else ("%d day%s late" % (dl, "" if dl == 1 else "s") if late else "on time")
        items.append(dict(k=k, name=short_(x["name"]), tg=tg, pos=pos, col=col, tint=tint, status=status, up=(k % 2 == 0), cx=X(pos)))
    lo, hi = W / 2 + 6, 800 - W / 2 - 6
    for up in (True, False):
        side = sorted([i for i in items if i["up"] == up], key=lambda i: i["cx"])
        for i in side: i["cx"] = max(lo, min(hi, i["cx"]))
        for a_, b_ in zip(side, side[1:]): b_["cx"] = max(b_["cx"], a_["cx"] + W + 8)
        for a_, b_ in zip(reversed(side[:-1]), reversed(side[1:])): a_["cx"] = min(a_["cx"], b_["cx"] - W - 8)
        for i in side: i["cx"] = max(lo, min(hi, i["cx"]))
    out = '<rect x="30" y="%d" width="740" height="6" rx="3" fill="#E5E5EA" />' % (AX - 3)
    out += '<rect x="30" y="%d" width="%.0f" height="6" rx="3" fill="#0071E3" />' % (AX - 3, max(0, X(now) - 30))
    cards = ""
    for i in items:
        xp = X(i["pos"]); top = 14 if i["up"] else AX + 40
        edge = top + H if i["up"] else top
        out += '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1.5" opacity=".55" />' % (xp, AX + (-8 if i["up"] else 8), i["cx"], edge, i["col"])
        if i["tg"] and abs(X(i["tg"]) - xp) > 3: out += '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="4" opacity=".4" />' % (X(i["tg"]), AX, xp, AX, i["col"])
        if i["tg"]: out += '<circle cx="%.1f" cy="%d" r="7" fill="#fff" stroke="%s" stroke-width="2.5" />' % (X(i["tg"]), AX, i["col"])
        out += '<circle cx="%.1f" cy="%d" r="6" fill="%s" stroke="#fff" stroke-width="2" />' % (xp, AX, i["col"])
        x0 = i["cx"] - W / 2
        cards += ('<rect x="%.1f" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s" stroke-width="1" stroke-opacity=".35" />'
                  '<text x="%.1f" y="%d" text-anchor="middle" font-size="12.5" font-weight="700" fill="#1D1D1F">%s</text>'
                  '<text x="%.1f" y="%d" text-anchor="middle" font-size="11" font-weight="600" fill="%s">%s</text>'
                  '<text x="%.1f" y="%d" text-anchor="middle" font-size="10" fill="#6E6E73">target %s</text>') % (
                  x0, top, W, H, i["tint"], i["col"], i["cx"], top + 18, e(i["name"]), i["cx"], top + 33, i["col"], e("Done: all gates met" if i["status"] == "done" else day(i["pos"]) + " · " + i["status"]), i["cx"], top + 47, e(day(i["tg"]) if i["tg"] else "n/a"))
    tx = X(now)
    out += '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#0071E3" stroke-width="2" />' % (tx, AX - 14, tx, AX + 14)
    out += cards
    out += '<rect x="%.1f" y="%d" width="118" height="20" rx="10" fill="#0071E3" /><text x="%.1f" y="%d" text-anchor="middle" font-size="10.5" font-weight="700" fill="#fff">Today %s</text>' % (max(8, min(tx - 59, 800 - 126)), AX + 16, max(8, min(tx - 59, 800 - 126)) + 59, AX + 30, e(day(now)))
    return '<svg viewBox="0 0 800 %d" width="100%%">' % (AX + 40 + H + 10) + out + '</svg>'
def overview_old(detail=False):
    S = stats(); me = [l.split("|", 1)[1] for l in read("owner_tasks.txt").splitlines() if "|" in l]
    tl, tb = S["tl"], S["tb"]; wl = max(0.1, (tl[0] - now) / (7 * 86400)) if tl else None
    need = (S["rem"] / wl + S["op"]) if wl else None; proj = None
    if S["net"] > 0: proj = now + S["rem"] / S["net"] * 7 * 86400
    if not live_issues or not tl: col, head, sub = "#8A94AD", "Waiting for GitHub data", "The verdict needs live issue history."
    elif proj and proj <= tl[0]: col, head, sub = "#2E7D32", "On track", f"At the current pace we finish launch scope around {day(proj)}, {round((tl[0] - proj) / 86400)} days before the {day(tl[0])} target."
    elif proj and proj <= tl[0] + 21 * 86400: col, head, sub = "#D9822B", "At risk", f"At the current pace we finish around {day(proj)}, {round((proj - tl[0]) / 86400)} days after the {day(tl[0])} target."
    elif proj: col, head, sub = "#C0392B", "Off track", f"At the current pace we finish around {day(proj)}, {round((proj - tl[0]) / 86400)} days after the {day(tl[0])} target."
    else: col, head, sub = "#C0392B", "Off track", "New issues are arriving as fast as we close them, so remaining scope is not shrinking."
    acts = []
    if live_issues and tl:
        if S["net"] <= 0: acts.append("Freeze new features. Only tester bugs get added until we close more than we open.")
        elif proj > tl[0]: acts.append(f"Close {need:.0f} issues a week (now {S['cl']:.0f}), or defer about {max(0, round(S['rem'] - S['net'] * wl))} issues to after launch.")
    aq = M.get("avg_qa_rounds") or 0
    if aq > 3: acts.append(f"Keep review to three rounds: the average is {aq} QA rounds per issue.")
    if len(me) >= 4: acts.append(f"Clear your {len(me)} to-dos; the clinician review and the privacy policy gate wider testing.")
    build = [r for r in PL if re.match(r"Wave [123]", r[0])]; bd = sum(1 for r in build if stage(r[1]) == "Merged"); brem = len(build) - bd
    rate_d = max(0.2, len([i for i in issues if i.get("closedAt") and now - (ts(i["closedAt"]) or 0) < 14 * 86400]) / 14) if live_issues else None
    beta = now + brem / rate_d * 86400 if rate_d else None
    if tb and beta and beta > tb[0]: acts.append(f"The next tester build is likely {day(beta)}, after the {day(tb[0])} target. Cut a wave 3 item or add a second QA pass in parallel.")
    if not acts: acts.append("Nothing needs changing. Keep the current pace and the two-round review limit.")
    # timeline
    tone = {"#2E7D32": ("#1F8A3B", "#E8F8EE"), "#D9822B": ("#B35C00", "#FFF3E0"), "#C0392B": ("#C4281C", "#FDECEA"), "#8A94AD": ("#636366", "#F2F2F7")}[col]
    t0, t1 = datetime.datetime(2026, 10, 1).timestamp(), (tl[0] if tl else now + 70 * 86400) + 12 * 86400
    X = lambda t: 20 + 760 * max(0, min(1, (t - t0) / (t1 - t0)))
    pts = sorted([(t_, c_, lab_, b_) for t_, c_, lab_, b_ in [(now, "#1D1D1F", "Today", True), (tb[0] if tb else None, "#0071E3", "Build target", False), (beta, "#34C759", "Build forecast", False), (tl[0] if tl else None, "#1D1D1F", "Launch target", False), (proj, tone[0], "Launch forecast", False)] if t_])
    rows_y = [34, 16, 80, 96]; used = {y_: [] for y_ in rows_y}; mk = ""
    for t_, c_, lab_, b_ in pts:
        txt = lab_ + " " + day(t_); half = len(txt) * 3.2 + 6; x_ = X(t_); y_pick = rows_y[-1]
        for y_ in rows_y:
            if all(x_ - half > b0 + 4 or x_ + half < a0 - 4 for a0, b0 in used[y_]): y_pick = y_; used[y_].append((x_ - half, x_ + half)); break
        ly = 50 if y_pick > 50 else 50
        mk += f'<line x1={x_:.0f} x2={x_:.0f} y1={(y_pick + 3) if y_pick < 50 else 56} y2={(46 if y_pick < 50 else y_pick - 9)} stroke="{c_}" stroke-width=1 opacity=.45 /><circle cx={x_:.0f} cy=50 r=5.5 fill="{c_}" stroke="#fff" stroke-width=2 /><text x={x_:.0f} y={y_pick} text-anchor=middle font-size=10.5 font-weight={600 if b_ else 500} fill="{c_ if c_ != "#34C759" else "#1F8A3B"}">{e(txt)}</text>'
    tlsvg = (f'<svg viewBox="0 0 800 108" width="100%"><rect x=20 y=48 width=760 height=4 rx=2 fill="#E5E5EA" /><rect x=20 y=48 width={X(now) - 20:.0f} height=4 rx=2 fill="#0071E3" />{mk}</svg>')
    try: _ms = ms_timeline(_LP[0].get("stages") or [], now, _LP[0].get("launch_ts")) if _LP else None
    except Exception: _ms = None
    pc = round(100 * S["dn"] / S["tot"]) if S["tot"] else 0; bpc = round(100 * bd / len(build)) if build else 0
    wlab = [d.strftime("%d %b") for d in S["weeks"]]
    vel = bars([(wlab[k], [S["wc"][k], S["wo"][k]]) for k in range(len(wlab))], ["#0071E3", "#C7C7CC"], ["Issues closed", "New issues opened"], need) if live_issues else "<div class=m>Needs GitHub data.</div>"
    ep = []
    for e_ in EP:
        L = [i for i in issues if epic_of(i["title"]) == e_[0] and not i["title"].lower().startswith(("[note]", "backlog"))]; ep.append((e_[0], sum(i["state"] == "CLOSED" for i in L), len(L)))
    T_ = M.get("totals", {}); tf_n = len(tf)
    bugs = pie([("Found by QA", T_.get("findings", 0), "#0071E3"), ("Reported by testers", tf_n, "#FF9500"), ("Open bug issues", len([i for i in issues if i["state"] == "OPEN" and "bug" in [lbl(x) for x in i.get("labels", [])]]), "#FF3B30")])
    tfw = sum(c for d, c in fb_days.items() if (ts(d + "T00:00:00Z") or 0) > now - 7 * 86400)
    kp = cards([("PRs merged, last 7 days (previous 7: " + str(len(mp)) + ")", len(mw), "#d-merged7"), ("Issues closed, last 7 days", "n/a" if cl is None else len(cl), "#d-closed7"), ("Open PRs", len(openprs), "#d-openprs"), ("Tester feedback, last 7 days", tfw, "#d-feedback")])
    scope_lbl = "%d of %d" % (S["dn"], S["tot"]); build_lbl = "%d of %d merged" % (bd, len(build))
    eta = ("Forecast " + day(beta)) if beta else "Forecast needs data"
    if tb: eta += " (target " + day(tb[0]) + ")"
    pace_rows = ""
    if need:
        mxp = max(round(need), round(S["cl"]), 1)
        pace_rows = hbars([("Needed a week", round(need), mxp), ("Actual a week", round(S["cl"]), mxp)], "#0071E3", 330, 120)
    acts_html = "".join("<li>" + e(a) + "</li>" for a in acts)
    me_html = "".join("<li>" + e(x) + "</li>" for x in me[:8]) or "<li>Nothing right now.</li>"
    tfg, tbg = tone
    verdict = ('<div class=hero><span class=pill style="background:' + tbg + ';color:' + tfg + '"><i style="background:' + tfg + '"></i>' + e(head) + '</span><div class=hero-h>' + e(sub) + '</div><ol class=acts>'
               + "".join('<li><span class=n>%d</span><span>%s</span></li>' % (k + 1, e(a)) for k, a in enumerate(acts)) + '</ol></div>')
    row1 = ('<div class=grid><div class=box><h3>Launch scope done</h3>' + donut(pc, "#0071E3", str(pc) + "%", scope_lbl) + '<div class=m>' + str(S["rem"]) + ' issues still open in the launch themes (ops and chores excluded).</div></div>'
            '<div class=box><h3>Next test build for testers</h3>' + donut(bpc, "#34C759", str(bpc) + "%", build_lbl) + '<div class=m>' + e(eta) + '</div></div>'
            '<div class=box><h3>Are we closing issues fast enough?</h3><div class=m>Needed: issues we must close each week to hit the launch date, counting new ones that keep arriving. Actual: what we really close each week.</div>' + pace_rows + '<div class=m>New issues opened per week: %.0f. Net burn: %+.0f a week.</div></div></div>' % (S["op"], S["net"]))
    if detail: return (kp + row1 + '<h2>Velocity: closed vs opened, per week</h2><div class=box>' + vel + '<div class=m>Green above orange means the backlog is shrinking. The red line is the weekly closing pace needed to reach the launch target.</div></div>'
            + '<h2>Timeline to launch</h2><div class=box>' + (_ms or tlsvg) + '<div class=m>Ring = target, dot = forecast: green on time, red late, blue done. Same milestones as the road above; edit them in dispatch/release.txt.</div></div>'
            + '<div class=grid2><div class=box><h3>Epics: where each theme stands</h3>' + hbars(ep, "#0071E3", 560, 270) + '</div><div class=box><h3>Bugs by source</h3>' + bugs + '<div class=m>Details in the Quality tab.</div></div></div>')
    return (verdict + kp + row1 + '<h2>Velocity: closed vs opened, per week</h2><div class=box>' + vel + '<div class=m>Green above orange means the backlog is shrinking. The red line is the weekly closing pace needed to reach the launch target.</div></div>'
            + '<h2>Timeline to launch</h2><div class=box>' + (_ms or tlsvg) + '<div class=m>Ring = target, dot = forecast: green on time, red late, blue done. Same milestones as the road above; edit them in dispatch/release.txt.</div></div>'
            + '<div class=grid2><div class=box><h3>Epics: where each theme stands</h3>' + hbars(ep, "#0071E3", 560, 270) + '</div><div class=box><h3>Bugs by source</h3>' + bugs + '<div class=m>Details in the Quality tab.</div></div></div>'
            + '<h2>Needs you</h2><ul>' + me_html + '</ul>')

def launch_parts():
    if _LP: return _LP[0]
    L = jl("cache/issues_live.json", []) or []
    owner = sorted([i for i in L if i["title"].lower().startswith("owner:") and i["state"] == "OPEN"], key=lambda i: i["number"])
    allx = [i for i in L if True]
    S = stats(); lanes = lab.lanes if LAB_OK else {}
    fb = []
    for f in sorted(tf, reverse=True)[:40]:
        b_ = os.path.basename(f); m_ = re.match(r"(\d{4}-\d{2}-\d{2})", b_); txt = ""
        try:
            for ln in open(f).read().splitlines():
                if ln.startswith("**Comment:**"): txt = ln[len("**Comment:**"):].strip(); break
            if not txt: txt = next((ln.strip() for ln in open(f).read().splitlines() if ln.strip() and not ln.startswith(("#", "- ", "**"))), "")
        except Exception: pass
        fb.append((m_.group(1) if m_ else "", "crash report" if "crash" in b_ else "tester feedback", txt or "(no text, screenshot only)"))
    lim_ = 0
    try:
        for f in os.listdir(os.path.join(D, "alerts", "sent")):
            m_ = re.match(r"(\d{8})T\d+-limit", f)
            if m_ and now - datetime.datetime.strptime(m_.group(1), "%Y%m%d").timestamp() < 14 * 86400: lim_ += 1
    except Exception: pass
    blocked_ = len(owner) + sum(1 for k_ in lanes for i_ in lanes[k_] if LAB_OK and lab.state(i_) == "Blocked")
    ctx = dict(now=now, day=day, link=link, issues=issues, all_issues=allx, M=M, lanes=lanes, ts=ts, lbl=lbl, short=short, T=S["T"], arrivals_per_week=S["op"],
               limit_hits=lim_, blocked=blocked_, tf7=sum(c for d, c in fb_days.items() if (ts(d + "T00:00:00Z") or 0) > now - 7 * 86400), tf_total=len(tf), fb_items=fb,
               open_bugs=len([i for i in issues if i["state"] == "OPEN" and "bug" in [lbl(x) for x in i.get("labels", [])]]), owner=owner)
    try: parts = launch.build(ctx)
    except Exception as ex:
        msg = '<div class=m>The launch plan could not be built: ' + e(str(ex)) + '</div>'; parts = dict(css="", hero=msg, road="", plan=msg, success=msg)
    try:
        sh = ship.compute(now, merged, openprs); parts["plan"] = ship.html_block(sh) + parts["plan"]
        parts["strip"] = '<a class=lc-strip href="#launch"><b>Next test build</b> ' + e(ship.verdict(sh)) + ' <span>Details &rsaquo;</span></a>'; parts["ship_verdict"] = ship.verdict(sh)
        json.dump(dict(parts.get("summary", {}), ship=ship.verdict(sh), ts=int(now)), open(os.path.join(D, "cache", "launch.json"), "w"))
    except Exception as ex: parts.setdefault("strip", "")
    _LP.append(parts); return parts
_LP = []
def overview():
    P_ = launch_parts(); body = overview_old(True)
    for old, tab in (("<h2>Velocity: closed vs opened, per week</h2>", "delivered"), ("<h2>Timeline to launch</h2>", "launch"),
                     ("<h3>Epics: where each theme stands</h3>", "roadmap"), ("<h3>Bugs by source</h3>", "quality"), ("<h3>Launch scope done</h3>", "roadmap"),
                     ("<h3>Next test build for testers</h3>", "pipeline"), ("<h3>Are we closing issues fast enough?</h3>", "delivered")):
        body = body.replace(old, old[:-5] + '<a class=vl href="#' + tab + '">View &rsaquo;</a>' + old[-5:], 1)
    road = P_["road"].replace("<h2>The road to launch</h2>", '<h2>The road to launch<a class=vl href="#launch">Details &rsaquo;</a></h2>', 1)
    m_ = re.search(r"<h2>Timeline to launch.*?</div></div>", body, re.S)
    tl_ = ""
    if m_: tl_ = m_.group(0); body = body.replace(tl_, "", 1)      # the timeline sits directly under the road: same milestones, one story
    return P_["css"] + P_["hero"] + road + tl_ + P_.get("mkt", "") + P_.get("strip", "") + body
def launch_tab(): P_ = launch_parts(); return P_["css"] + P_.get("mkt", "") + P_["plan"]
def success_tab(): P_ = launch_parts(); return P_["css"] + P_["success"]

def roadmap():
    cols = {}
    for ep in EP:
        L = [i for i in issues if epic_of(i["title"]) == ep[0] and not i["title"].lower().startswith(("[note]", "backlog"))]
        dn = sum(i["state"] == "CLOSED" for i in L); nxt = sum(1 for k_ in ("P0", "P1") for i_ in (lab.lanes.get(k_, []) if LAB_OK else []) if i_["state"] == "OPEN" and epic_of(i_["title"]) == ep[0])
        pc = round(100 * dn / len(L)) if L else 0; col = "#34C759" if pc >= 80 else "#0071E3" if pc >= 60 else "#FF9500"
        card = (f'<div class=box><b>{e(ep[0])}</b>{bar(dn, len(L), col)}<div class=m>{pc}% done: {dn} of {len(L)} issues closed</div>'
                f'<div class=m>{len(L) - dn} still open, {nxt} of them in Now or Next on the Prioritise tab</div></div>')
        cols.setdefault(ep[2] if len(ep) > 2 else "Other", []).append(card)
    order = ["Before wider testers", "Done for testers; polishing", "Next build", "Next 4 weeks", "Ongoing"]
    keys = [k for k in order if k in cols] + [k for k in cols if k not in order]
    body = "".join(f'<div class=colm><div class=grp style="padding:6px 8px;border-radius:6px;margin-bottom:6px">{e(k)}</div>{"".join(cols[k])}</div>' for k in keys)
    return (f'<div class=m style="margin-bottom:8px">Epics are product themes. Each column groups themes by when they must be ready, with progress across all their issues. The issue-by-issue list and the build order live in the Pipeline tab.</div><div class=cols>{body}</div>'
            '<div class=m>Themes are matched from issue titles (dispatch/roadmap.txt). Closed counts need GitHub access.</div>')
def fmt_min(m):
    if m is None: return "n/a"
    m = int(m); return f"{m}m" if m < 60 else (f"{m // 60}h {m % 60:02d}m" if m < 1440 else f"{m // 1440}d {(m % 1440) // 60}h")
def fmt_tok(n): return "n/a" if n is None else (f"{n / 1e6:.1f}M" if n >= 1e6 else f"{round(n / 1000)}k" if n >= 1000 else str(n))
def efficiency():
    T, Md = M.get("totals", {}), M.get("medians_min", {})
    if not M.get("issues"): return '<h2>Delivery efficiency per issue</h2><div class=m>Not collected yet. It fills in within 5 minutes of the dispatcher running.</div>'
    pr_of = {}
    for p in merged:
        k = iss_of(p)
        if k: pr_of[k] = max(pr_of.get(k, 0), ts(p["mergedAt"]) or 0)
    rws = ""
    for o in M["issues"]:
        n = o["issue"]; pj, ac = o["projected_min"], o["active_min"]
        pv = "-" if pj is None else f'{fmt_min(pj)} planned / {fmt_min(ac)} actual'
        st = "closed" if I.get(n, {}).get("state") == "CLOSED" else ("merged" if n in pr_of else ("running" if o["running"] else "open"))
        dl = day(pr_of[n]) if n in pr_of else ""
        rws += (f'<tr><td>{link(n)}</td><td>{e(short(title(n)) or "")[:80]}</td><td class=m>{st}{(" " + dl) if dl else ""}</td><td>{fmt_min(o["dev_min"])}</td><td>{fmt_min(o["qa_min"])}</td><td>{fmt_min(o["fix_min"])}</td>'
                f'<td>{o["qa_rounds"]} / {o["fix_rounds"]}</td><td>{o["findings"]}</td><td>{fmt_tok(o["tokens_new"])}</td><td>{fmt_min(o["elapsed_min"])}</td><td class=m>{pv}</td><td>{o["restarts"] or ""}</td></tr>')
    typ = " | ".join(f"{k} {v} min" for k, v in (("dev", Md.get("dev")), ("QA", Md.get("qa")), ("fix", Md.get("fix"))) if v)
    tk = f'{fmt_tok(T.get("tokens_new"))} across {T.get("tokens_known_for", 0)} issues' if T.get("tokens_known_for") else "being collected from now on"
    cards_ = (f'<div class=cards><div class=c><b>{T.get("issues", 0)}</b>issues worked</div><div class=c><b>{T.get("findings", 0)}</b>bugs found by QA</div><div class=c><b>{T.get("tester_issues", 0)}</b>bugs from testers</div>'
              f'<div class=c><b>{fmt_min(T.get("active_min", 0))}</b>agent working time</div><div class=c><b>{T.get("qa_rounds", 0)} / {T.get("fix_rounds", 0)}</b>QA / fix rounds</div></div>')
    return ('<h2>Delivery efficiency per issue</h2>' + cards_ + f'<div class=m style="margin:6px 0 10px">Typical run: {typ or "not enough data yet"}. Average QA rounds per issue: {M.get("avg_qa_rounds", "n/a")}. Tokens are new work, not cached re-reads: {tk}. Older runs show n/a where the end time or tokens were never recorded. Raw file: dispatch/metrics/issues.csv.</div>'
            '<div class="sbox wide"><table class=t><tr class=hd><th>Issue</th><th>What</th><th>State</th><th>Dev</th><th>QA</th><th>Fix</th><th>QA / fix rounds</th><th>Bugs found</th><th>Tokens</th><th>Calendar time</th><th>Planned / actual</th><th>Restarts</th></tr>' + rws + '</table></div>')
def delivered():
    global EXTRA_CSS
    ms = sorted(merged, key=lambda p: -ts(p["mergedAt"])); n14 = sum(1 for p in ms if now - ts(p["mergedAt"]) < 14 * 86400)
    S = stats(); wlab = [d.strftime("%d %b") for d in S["weeks"]]
    chart = bars([(wlab[k], [S["wm"][k]]) for k in range(len(wlab))], ["#0071E3"], ["PRs merged per week"])
    rows = "".join(f'<tr class="r{" rd-14" if now - ts(p["mergedAt"]) < 14 * 86400 else ""}"><td>{link(p["number"], "pull")}</td><td>{e(short(p["title"]))}</td><td class=m>{day(ts(p["mergedAt"]))}</td></tr>' for p in ms)
    EXTRA_CSS += filter_css("df", ["14"], "rd-", False)
    return ('<h2>Delivery pace</h2><div class=box>' + chart + '</div><h2>What was delivered</h2><input type=radio name=df id=df-14 checked><input type=radio name=df id=df-all>'
            f'<div class=cards><label class=c for=df-14><b>{n14}</b>Merged, last 14 days<span class=go>show only these</span></label><label class=c for=df-all><b>{len(ms)}</b>All merged<span class=go>show everything</span></label></div>'
            f'<div class="sbox pt"><table class=t><tr class=hd><th>PR</th><th>What</th><th>Merged</th></tr>{rows}</table></div><div class=m>Doubles as the source for release notes.</div>' + efficiency())
def quality():
    global EXTRA_CSS
    T = M.get("totals", {}); S = stats()
    open_bugs = [i for i in issues if i["state"] == "OPEN" and "bug" in [lbl(x) for x in i.get("labels", [])]]
    mt = {iss_of(p): ts(p["mergedAt"]) for p in merged if iss_of(p)}
    # start (first agent launch, else PR opened) to merge, merged in the last 30 days; the old figure was dev run time, which read 0.0 days
    pc = {iss_of(p): ts(p["createdAt"]) for p in merged if iss_of(p) and p.get("createdAt")}
    fs = {o["issue"]: o.get("first_ts") for o in M.get("issues", [])}
    hrs_ = sorted((mt[k] - (fs.get(k) or pc.get(k) or mt[k])) / 3600 for k in mt if mt[k] > time.time() - 30 * 86400 and mt[k] - (fs.get(k) or pc.get(k) or mt[k]) >= 0)
    med = hrs_[len(hrs_) // 2] if hrs_ else None
    med_txt = "n/a" if med is None else (f"{round(med * 60)} min" if med < 1 else f"{med:.1f} hours" if med < 48 else f"{med / 24:.1f} days")
    top = sorted(M.get("issues", []), key=lambda o: -o["findings"])[:8]; mxf = max([o["findings"] for o in top] + [1])
    qa_chart = hbars([(f'#{o["issue"]} {short(title(o["issue"]))}', o["findings"], mxf) for o in top if o["findings"]], "#0071E3", linkit=True, unit="bugs") if top else ""
    today = datetime.date.today(); fbd = {datetime.date.fromisoformat(d): c for d, c in fb_days.items()}
    qlog = [(t_, n_) for o in M.get("issues", []) for t_, n_ in (o.get("findings_log") or []) if t_]
    def per_period(p):
        if p == "d": bk = [(today - datetime.timedelta(days=k)) for k in range(13, -1, -1)]; lab = lambda d_: d_.strftime("%d %b"); key = lambda d_: d_; win = 1
        elif p == "w":
            m0 = today - datetime.timedelta(days=today.weekday()); bk = [m0 - datetime.timedelta(weeks=k) for k in range(7, -1, -1)]; lab = lambda d_: d_.strftime("%d %b"); key = lambda d_: d_ - datetime.timedelta(days=d_.weekday()); win = 7
        elif p == "m":
            bk = []; y_, m_ = today.year, today.month
            for _ in range(6): bk.append(datetime.date(y_, m_, 1)); m_ -= 1; y_ -= (m_ == 0); m_ = 12 if m_ == 0 else m_
            bk.reverse(); lab = lambda d_: d_.strftime("%b %Y"); key = lambda d_: d_.replace(day=1); win = 30
        else: bk = [datetime.date(today.year - 1, 1, 1), datetime.date(today.year, 1, 1)]; lab = lambda d_: str(d_.year); key = lambda d_: d_.replace(month=1, day=1); win = 365
        cnt = {b: 0 for b in bk}
        for d_, c in fbd.items():
            if key(d_) in cnt: cnt[key(d_)] += c
        chart = bars([(lab(b), [cnt[b]]) for b in bk], ["#FF9500"], ["Tester feedback items"])
        lo = now - win * 86400
        qa_n = sum(n_ for t_, n_ in qlog if t_ >= lo); fb_n = sum(c for d_, c in fbd.items() if (today - d_).days < win)
        ob = sum(1 for i in open_bugs if i.get("createdAt") and (ts(i["createdAt"]) or 0) >= lo)
        pie_ = pie([("Found by adversarial QA", qa_n, "#0071E3"), ("Reported by testers", fb_n, "#FF9500"), ("Open bug issues", ob, "#FF3B30")])
        if not qlog: qc = qa_chart + '<div class=m>Per-period findings fill in after the next metrics run; showing all time for now.</div>' if qa_chart else ""
        else:
            per = sorted(((sum(n_ for t_, n_ in (o.get("findings_log") or []) if t_ >= lo), o["issue"]) for o in M.get("issues", [])), reverse=True)
            per = [(c_, i_) for c_, i_ in per if c_][:8]; mx_ = max([c_ for c_, _ in per] + [1])
            qc = hbars([(f'#{i_} {short(title(i_))}', c_, mx_) for c_, i_ in per], "#0071E3", linkit=True, unit="bugs") if per else '<div class=m>No QA findings in this period.</div>'
        return pie_, chart, qc
    names = [("d", "Day", "Today"), ("w", "Week", "Last 7 days"), ("m", "Month", "Last 30 days"), ("y", "Year", "Last 12 months")]
    inputs = "".join(f'<input type=radio name=qp id=qp-{k}{" checked" if k == "m" else ""}>' for k, _, _ in names)
    seg = '<div class=seg>' + "".join(f'<label for=qp-{k}>{n}</label>' for k, n, _ in names) + '</div>'
    pies = charts = qas = ""
    for k, n, w_ in names:
        pp, cc, qc = per_period(k)
        pies += f'<div class="pv pv-{k}">{pp}<div class=m>{w_}</div></div>'; charts += f'<div class="pv pv-{k}">{cc}</div>'; qas += f'<div class="pv pv-{k}">{qc}</div>'
    EXTRA_CSS += ".seg{display:inline-flex;background:#E9E9EE;border-radius:999px;padding:3px;margin:4px 0 12px}.seg label{padding:6px 16px;border-radius:999px;font-size:13px;color:#3A3A3C;cursor:pointer}.pv{display:none}"
    for k, _, _ in names: EXTRA_CSS += f"#qp-{k}:checked~.seg label[for=qp-{k}]{{background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.14);color:#1D1D1F}}#qp-{k}:checked~.qwrap .pv-{k}{{display:block}}"
    return (cards([("Bugs found by adversarial QA", T.get("findings", 0)), ("Tester feedback items", len(tf), "#d-feedback"), ("Open bugs", len(open_bugs), "#d-openbugs"),
                   ("Typical start to merge (30 days)", med_txt), ("Average QA rounds per issue", M.get("avg_qa_rounds", "n/a"))])
            + inputs + seg + f'<div class=qwrap><div class=grid2><div class=box><h3>Where bugs come from</h3>{pies}</div><div class=box><h3>Tester feedback over time</h3>{charts}</div></div>'
            + f'<h2>Where QA found the most</h2><div class=box>{qas}<div class=m>Bugs QA found in the period selected above; bar length is relative to the issue with the most. Click an issue to read it on GitHub. Findings reported by adversarial QA agents; repeat rounds count again. Start to merge is calendar time for merged work only.</div></div></div>')

CTLCSS = """.ctl{background:#fff;border-radius:20px;padding:16px 20px;margin:0 0 14px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}
.ctl .row{display:flex;flex-wrap:wrap;align-items:center;gap:10px}.ctl .st{font-weight:600;font-size:15px;margin-right:8px}.ctl .st i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px}
.ctl button{border:0;border-radius:999px;padding:9px 18px;font:600 14px inherit;cursor:pointer;background:#F2F2F7;color:#1D1D1F}.ctl button.go{background:#34C759;color:#fff}.ctl button.pa{background:#FF9500;color:#fff}.ctl button.st2{background:#FF3B30;color:#fff}.ctl button.arm{background:#1D1D1F;color:#fff}.ctl button:disabled{opacity:.45}
.ctl .ag{display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid #F2F2F7;font-size:14px;margin-top:6px}.ctl .ag b{min-width:90px}.ctl .ag .s{flex:1;color:#6E6E73}.ctl .ag button{padding:6px 14px;font-size:13px}"""
CTLJS = """<script>(function(){var armed=null,tm=null;
function el(){return document.getElementById('ctl')}
function post(a,id){return fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/json','X-Lab':'1'},body:JSON.stringify({action:a,agent:id})}).then(function(r){return r.json()})}
function draw(s){var c=el();if(!c)return;var kk=JSON.stringify(s)+armed;if(c.__k===kk)return;c.__k=kk;var run=!s.paused,h='<div class=row><span class=st><i style="background:'+(run?'#34C759':'#FF9500')+'"></i>Development is '+(run?'ON':'PAUSED')+(s.limit?' (usage limit hit)':'')+'</span>'
+'<button class=go data-c=start'+(run&&!s.agents.some(function(a){return a.stopped})?' disabled style="opacity:.45"':'')+'>'+(run?(s.agents.some(function(a){return a.stopped})?'Resume paused agents':'Running'):'Start all')+'</button><button class=pa data-c=pause>Pause all</button><button class="st2'+(armed==='stopall'?' arm':'')+'" data-c=stopall>'+(armed==='stopall'?'Tap again to stop everything':'Stop all')+'</button></div>'
+'<div class=m style="margin-top:6px">Start lets agents run. Pause freezes running agents and holds new ones. Stop all ends every running agent (they restart on Start).</div>';
if(s.agents.length){s.agents.forEach(function(a){h+='<div class=ag><b>'+a.id+'</b><span class=s>'+(a.stopped?'Paused':'Running')+'</span><button data-c='+(a.stopped?'agent_start':'agent_pause')+' data-id="'+a.id+'" class="'+(a.stopped?'go':'pa')+'">'+(a.stopped?'Start':'Pause')+'</button></div>'})}else h+='<div class=m style="margin-top:8px">No agents running right now.</div>';
c.innerHTML=h}
function load(){var c=el();if(!c||document.hidden)return;fetch('/api/control',{cache:'no-store'}).then(function(r){return r.json()}).then(draw).catch(function(){c.innerHTML='<span class=m>Controls work from the Mac or phone address, not from a saved file.</span>'})}
document.addEventListener('click',function(ev){var b=ev.target.closest&&ev.target.closest('#ctl button[data-c]');if(!b)return;var a=b.dataset.c;
if(a==='stopall'&&armed!=='stopall'){armed='stopall';clearTimeout(tm);tm=setTimeout(function(){armed=null;load()},4000);load();return}
armed=null;b.disabled=true;post(a,b.dataset.id).then(draw).catch(function(){b.disabled=false})});
setInterval(load,4000);load()})();</script>"""
OPS_CSS = r"""body{background:#fff!important;color:#1D1D1F!important;font:14px/1.45 -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Arial,sans-serif!important;padding:22px 26px!important;-webkit-font-smoothing:antialiased}
h1{display:none!important}
h2{font-size:20px!important;font-weight:600!important;letter-spacing:-.01em!important;margin:34px 0 12px!important;color:#1D1D1F}
h3{color:#6E6E73!important;font-size:11px!important;letter-spacing:.08em!important}
.m{color:#6E6E73!important}
a{color:#0071E3!important;text-decoration:none}
.cards{gap:12px!important;flex-wrap:wrap!important}
@media(max-width:560px){.c{min-width:0!important;flex:1 1 40%!important}}
.c{background:#F5F5F7!important;border:0!important;border-radius:16px!important;padding:14px 18px!important;min-width:140px!important}
.c b{font-size:30px!important;font-weight:600!important;letter-spacing:-.02em}
.warn{background:#FDECEA!important;color:#C4281C!important}
.pause,.pause *{background:#FFF3E0!important;color:#B35C00!important;border:0!important;border-radius:14px!important;font-weight:500!important}
.sum,.shop,.lim,.box{background:#F5F5F7!important;border:0!important;border-radius:18px!important;box-shadow:none!important}
.sum{padding:8px 22px!important}.sum h3{color:#0071E3!important}
.shop{padding:20px 22px!important}
.desks{gap:14px!important}
.desk{width:172px!important;border-radius:16px!important;background:#fff!important;border:0!important;box-shadow:0 1px 2px rgba(0,0,0,.05),0 0 0 .5px rgba(0,0,0,.06)!important;opacity:1!important;padding:16px 10px 12px!important}
.desk.bad{background:#FDECEA!important}
.fig,.fig2,.kb,.zz,.dots{display:none!important}
.desks{display:grid!important;grid-template-columns:repeat(auto-fill,minmax(270px,1fr))!important;gap:10px!important}
.desk{width:auto!important;display:grid!important;grid-template-columns:12px 1fr;column-gap:12px;text-align:left!important;padding:12px 16px!important;align-items:start}
.desk>*{grid-column:2}.desk::before{width:12px!important;height:12px!important;margin:4px 0 0!important;grid-column:1!important;grid-row:1/span 4;box-shadow:none!important}
.desk .ag{font-size:10.5px!important;letter-spacing:.07em}.desk .nm{font-size:14px}.desk .sb{font-size:12.5px}
.queue{display:flex!important;flex-wrap:wrap;gap:8px;align-items:center;padding-top:12px}.qp{width:auto!important;max-width:100%;display:flex!important;gap:8px;align-items:baseline;text-align:left!important;background:#fff;border-radius:12px;padding:8px 12px;box-shadow:0 0 0 .5px rgba(0,0,0,.08)}.qp::before{width:8px!important;height:8px!important;margin:0!important;flex:none}.qp .nm{font-size:13px}.qp .sb{font-size:12px}.ql{font-size:11px;text-transform:uppercase;letter-spacing:.07em;width:100%}
.lims{display:grid!important;grid-template-columns:repeat(auto-fill,minmax(190px,1fr))!important;gap:10px!important}.lim{min-width:0!important;width:auto!important}
.desk::before{content:"";display:block;width:40px;height:40px;border-radius:50%;margin:0 auto 10px;background:#D1D1D6;box-shadow:inset 0 0 0 6px rgba(255,255,255,.55)}
.desk.on::before{background:#34C759;animation:pls 1.6s ease-in-out infinite}
.desk.on.qa::before{background:#0071E3}.desk.on.fix::before{background:#FF9500}
.desk.bad::before{background:#FF3B30}.desk.off::before{background:#D1D1D6}
.desk.ollama::before{background:#7B3FE4!important}.desk.ollama.off::before{background:#C9B3F5!important}.desk.ollama{box-shadow:0 0 0 1.5px #7B3FE4!important}.desk.ollama .ag{color:#7B3FE4!important}
@keyframes pls{0%,100%{box-shadow:0 0 0 0 rgba(52,199,89,.35)}50%{box-shadow:0 0 0 9px rgba(52,199,89,0)}}
.qp::before{content:"";display:block;width:22px;height:22px;border-radius:50%;background:#C7C7CC;margin:0 auto 6px}
.nm{font-weight:600!important}.sb,.ag,.ql,.grp,.lt{color:#6E6E73!important}
.queue{border-top:1px solid #E5E5EA!important}
.lim{padding:12px 14px!important;background:#fff!important}.lim.hot{background:#FDECEA!important}
.meter{background:#E5E5EA!important;height:5px!important}.meter i{border-radius:3px}
.scroll,.logbox{border:0!important;border-radius:16px!important;background:#fff!important;box-shadow:0 0 0 .5px rgba(0,0,0,.08)}
table{border:0!important;border-radius:16px!important;box-shadow:0 0 0 .5px rgba(0,0,0,.08)!important;background:#fff!important}
td{border-top:1px solid #F2F2F7!important;padding:11px 14px!important}
.hd th{background:#fff!important;color:#86868B!important;font-size:11px!important;letter-spacing:.08em!important;border-bottom:1px solid #F2F2F7}
.tab,.afw label,.lfw label{border:0!important;background:#F2F2F7!important;color:#3A3A3C!important;border-radius:999px!important;padding:6px 14px!important}
.tab.on,.afw input:checked+label,.lfw input:checked+label{background:#1D1D1F!important;color:#fff!important}
.b,.cat{border-radius:999px!important}
.lr{border-top:1px solid #F2F2F7!important}.lr.fail{background:#FDECEA!important}.lr.warn{background:#FFF7E6!important}
"""

def operations():
    h = read("status.html")
    if not h: return "<div class=m>The live operations page has not been generated yet.</div>"
    h = re.sub(r'<!--ATTN-->.*?<!--/ATTN-->', '', h, flags=re.S); h = re.sub(r'<div class=pause>.*?</div>', '', h, flags=re.S)   # the banner and pause notice live above the tabs / in the control panel
    h = re.sub(r'<meta http-equiv=refresh[^>]*>', '', h)   # the copy is refreshed by this page instead
    h = re.sub(r'<div class=m>Updated [^<]*</div>', '', h, count=1)
    h = re.sub(r'<a href="(?:founder|FounderStatus).html">[^<]*</a>\s*(&nbsp;)?\|?(&nbsp;)?\s*', '', h, count=1)
    h = h.replace("\u2705", "\u2713"); h = re.sub("[\U0001F300-\U0001FAFF\u2600-\u2712\u2714-\u27BF\uFE0F]", "", h)   # no emoji in the executive view
    h = h.replace('</head>', '<style>' + OPS_CSS + '</style></head>', 1)   # restyle the copy to match this page; status.html itself is untouched
    h = h.replace('<h2>The workshop</h2>', '<h2>The workshop</h2><div class=m style="margin:-6px 0 10px">Dot colour: green building, orange fixing, blue QA, grey on standby, red stuck.</div>', 1)
    for t_ in ("Pipeline to the next tester build", "Delivery metrics per issue", "Backlog: everything still to do"):   # these live in their own tabs
        h = re.sub(r"<h2>" + re.escape(t_) + r"</h2>.*?(?=<h2>|</div>\s*</body>)", "", h, flags=re.S)
    return '<div id=ctl class=ctl><span class=m>Loading controls...</span></div>' + f'<iframe class=ops scrolling=no onload="fitOps()" srcdoc="{html.escape(h, quote=True)}"></iframe><div class=m>Live agent activity only. Pipeline, backlog and delivery numbers are in their own tabs.</div>'
def groom_tab(): return lab.groom if LAB_OK else f'<div class=m>Prioritise could not be built: {e(LAB_ERR)}</div>'
def journey_tab(): return lab.journey() if LAB_OK else f'<div class=m>User journey could not be built: {e(LAB_ERR)}</div>'
def roadmap_tab(): return roadmap() + ('<h2>Explore by theme</h2>' + lab.tree() if LAB_OK else '')
LABCSS_ = lab.LABCSS if LAB_OK else ""; LABJS = lab.JS if LAB_OK else ""
EXTRA_CSS += LABCSS_ + CTLCSS
TABS = [("overview", "Overview", overview), ("launch", "Launch plan", launch_tab), ("success", "Success", success_tab), ("ops", "Operations", operations), ("groom", "Prioritise", groom_tab), ("pipeline", "Pipeline", pipeline), ("roadmap", "Roadmap", roadmap_tab), ("journey", "User journey", journey_tab), ("delivered", "Delivered", delivered),
        ("quality", "Quality", quality), ("optimisation", "Optimisation", optimisation), ("systems", "Systems", systems)]
panes = {}
for k, n, f in TABS:
    try: body = f()
    except Exception as ex: body = f'<div class=m>This tab could not be built: {e(str(ex))}</div>'
    panes[k] = f'<div class="pane{" def" if k == "overview" else ""}" id="{k}">{body}</div>'
for did, (par, ttl, body) in DET.items(): panes[did] = f'<div class=pane id="{did}"><a href="#{par}">&larr; Back</a><h2>{e(ttl)}</h2>{body}</div>'
_ids = [k for k, _, _ in TABS] + list(DET)
JSCSS = (".js .pane{display:none!important}" + "".join(f'.js[data-tab="{k}"] #{k}{{display:block!important}}' for k in _ids)
         + ",".join([f'.js[data-tab="{k}"] .bar a[href="#{k}"]' for k, _, _ in TABS] + [f'.js[data-tab="{d}"] .bar a[href="#{v[0]}"]' for d, v in DET.items()])
         + "{background:#C9B6FF!important;box-shadow:0 4px 14px rgba(124,92,250,.35)!important;color:#1B1530!important}")
HEADJS = "<script>(function(){var d=document.documentElement;d.className='js';function s(){var h=location.hash.replace('#','');if(!h){try{h=(localStorage.getItem('founderTab')||'').replace('#','')}catch(x){}}d.setAttribute('data-tab',h||'overview')}s();window.addEventListener('hashchange',s)})();</script>"
order = list(DET) + [k for k, _, _ in TABS if k != "overview"] + ["overview"]   # the default pane comes last so ":target ~ .def" can hide it
nav = "".join(f'<a href="#{k}" title="{n}">{icon(k)}<span>{n}</span></a>' for k, n, _ in TABS)
hl = "".join(f'html:not(.js) body:has(#{k}:target) .bar a[href="#{k}"],' for k, _, _ in TABS) + "".join(f'html:not(.js) body:has(#{d}:target) .bar a[href="#{v[0]}"],' for d, v in DET.items()) + 'html:not(.js) body:not(:has(.pane:target)) .bar a[href="#overview"]'
CSS = r""":root{--bg:#F5F5F7;--card:#fff;--tx:#1D1D1F;--mu:#6E6E73;--ln:#E5E5EA;--bl:#0071E3}
*{box-sizing:border-box}
html{scroll-padding-top:84px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.47 -apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display","Helvetica Neue",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
svg text{font-family:inherit}
.wrap{max-width:1180px;margin:0 auto;padding:max(28px,env(safe-area-inset-top)) max(28px,env(safe-area-inset-right)) 80px max(28px,env(safe-area-inset-left))}
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:18px}
.eyebrow{font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--mu)}
h1{font-size:40px;line-height:1.08;font-weight:700;letter-spacing:-.025em;margin:4px 0 0}
h2{font-size:24px;line-height:1.2;font-weight:600;letter-spacing:-.015em;margin:44px 0 14px}
.m{color:var(--mu);font-size:13px;margin:6px 0}
.stamp{color:var(--mu);font-size:12px;margin:0 0 14px}
.bar{position:sticky;top:10px;z-index:20;display:inline-flex;gap:2px;padding:3px;background:rgba(233,233,238,.82);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);border-radius:12px;margin:0 0 20px;max-width:100%;overflow-x:auto;scrollbar-width:none}.bar::-webkit-scrollbar{display:none}.bar.ovr{-webkit-mask-image:linear-gradient(90deg,#000 calc(100% - 34px),transparent);mask-image:linear-gradient(90deg,#000 calc(100% - 34px),transparent)}.bar.ovl{-webkit-mask-image:linear-gradient(90deg,transparent,#000 34px);mask-image:linear-gradient(90deg,transparent,#000 34px)}.bar.ovl.ovr{-webkit-mask-image:linear-gradient(90deg,transparent,#000 34px,#000 calc(100% - 34px),transparent);mask-image:linear-gradient(90deg,transparent,#000 34px,#000 calc(100% - 34px),transparent)}
.bar a{display:flex;align-items:center;gap:7px;padding:7px 14px;border-radius:9px;font-size:13.5px;font-weight:500;color:#3A3A3C;text-decoration:none;white-space:nowrap}
.bar a .ic{width:16px;height:16px}
.bar a:hover{color:var(--tx)}
@media(max-width:760px){.cards{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.c{padding:12px 14px;border-radius:14px}.it{width:28px;height:28px;margin-bottom:6px}.c b{font-size:26px}.bar a span{display:none}.bar a{padding:8px 12px}.wrap{padding:max(18px,env(safe-area-inset-top)) 14px 60px}h1{font-size:30px}}
.pane{display:none}.pane:target{display:block}.pane.def{display:block}.pane:target~.pane.def{display:none}
.back{display:inline-flex;align-items:center;font-size:13px;color:var(--bl);text-decoration:none;margin-bottom:4px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:14px 0}
.c{position:relative;display:flex;flex-direction:column;gap:2px;background:var(--card);border-radius:18px;padding:18px 20px;color:var(--tx);text-decoration:none;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05);transition:transform .15s,box-shadow .15s;cursor:pointer}
a.c:hover,label.c:hover{transform:translateY(-1px);box-shadow:0 6px 18px rgba(0,0,0,.08),0 0 0 .5px rgba(0,0,0,.05)}
.it{width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:10px}
.it .ic{width:19px;height:19px}
.c b{font-size:34px;line-height:1.1;font-weight:600;letter-spacing:-.02em}
@media(max-width:760px){.cards{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.c{padding:12px 14px;border-radius:14px}.it{width:28px;height:28px;margin-bottom:6px}.c b{font-size:26px}}
.cl{font-size:13px;color:var(--mu)}
.go{display:inline-flex;align-items:center;font-size:12px;color:var(--bl);margin-top:8px;font-weight:500}
.go .ic.s{width:12px;height:12px;margin-left:2px}
label.c .go{color:var(--mu)}
.box{background:var(--card);border-radius:20px;padding:22px 24px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}
.box h3{margin:0 0 12px;font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--mu)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px;margin:14px 0}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px;margin:14px 0}
.grid .box{display:flex;flex-direction:column;align-items:flex-start}
.hero{background:var(--card);border-radius:24px;padding:34px 38px;margin:6px 0 14px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 14px;border-radius:999px;font-size:13px;font-weight:600}
.pill i{width:8px;height:8px;border-radius:50%}
.hero-h{font-size:32px;line-height:1.18;font-weight:600;letter-spacing:-.02em;margin:16px 0 18px;max-width:900px}
.acts{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.acts li{display:flex;gap:12px;align-items:flex-start;color:#3A3A3C;font-size:15px;margin:0}
.acts .n{flex:none;width:22px;height:22px;border-radius:50%;background:#F2F2F7;color:#3A3A3C;font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:center;margin-top:1px}
table.t{border-collapse:separate;border-spacing:0;width:100%;background:var(--card);border-radius:18px;overflow:hidden;margin:8px 0;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}
.t td{padding:13px 18px;border-top:1px solid #F2F2F7;vertical-align:top}
.t tr:hover td{background:#FAFAFC}
.hd th{background:#fff;color:#86868B;font-size:11px;font-weight:600;text-align:left;padding:14px 18px 10px;text-transform:uppercase;letter-spacing:.08em}
.t tr.hd:hover td{background:none}
.grp{background:#F5F5F7!important;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:#6E6E73;padding:9px 18px!important}
.b{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:3px 10px;border-radius:999px;white-space:nowrap}
.b i{width:6px;height:6px;border-radius:50%}
.meter{height:6px;background:#EDEDF2;border-radius:3px;overflow:hidden;margin:8px 0}.meter i{display:block;height:100%;border-radius:3px}
a{color:var(--bl);text-decoration:none}a:hover{text-decoration:underline}
li{margin:5px 0}
summary{cursor:pointer;font-size:13px;color:var(--bl)}details ul{margin:6px 0;padding-left:18px;font-size:13px}
.pw{display:flex;gap:22px;align-items:center;flex-wrap:wrap}
.lgs{display:grid;gap:8px}.lg{display:flex;align-items:center;gap:8px;font-size:13px;color:#3A3A3C}.lg b{margin-left:auto;padding-left:14px;font-weight:600}
.sw{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}.lg .sw{margin:0}
.lgrow{display:flex;gap:18px;margin-top:8px}.lg2{font-size:12px;color:var(--mu);display:inline-flex;align-items:center}
.cols{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}.colm{flex:1;min-width:250px}.colm .box{margin-bottom:12px;padding:18px 20px}
.colm .grp{border-radius:8px;margin-bottom:10px}
iframe.ops{width:100%;height:900px;min-height:400px;overflow:hidden;border:0;border-radius:20px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}
"""

THEME_CSS = r"""
:root{--bg:#ECEEF3;--bl:#6B4EFF;--ac:#7C5CFA;--ink:#14121F;--rad:22px;--sh:0 1px 2px rgba(20,18,31,.04),0 8px 28px rgba(20,18,31,.06)}
body{background:var(--bg);color:var(--ink);font-family:"Inter",-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",Arial,sans-serif;letter-spacing:-.005em}
.wrap{max-width:1240px;padding-left:max(104px,env(safe-area-inset-left));padding-top:max(20px,env(safe-area-inset-top))}
/* dark floating pill navigation (left rail on desktop, bottom dock on phones) */
.bar{position:fixed;left:16px;top:16px;bottom:16px;z-index:50;display:flex;flex-direction:column;align-items:center;gap:6px;width:64px;padding:16px 0;margin:0;background:#14121F;border-radius:32px;box-shadow:0 14px 40px rgba(20,18,31,.35);overflow-y:auto;overflow-x:visible;scrollbar-width:none;backdrop-filter:none;-webkit-mask-image:none!important;mask-image:none!important}
.bar::-webkit-scrollbar{display:none}
.bar a{position:relative;width:42px;height:42px;padding:0;justify-content:center;border-radius:14px;color:#A39FB8;transition:background .15s,color .15s,transform .15s}
.bar a span{display:none}
.bar a .ic{width:19px;height:19px}
.bar a:hover{color:#fff;background:rgba(255,255,255,.1);text-decoration:none;transform:translateX(1px)}
.bar a:hover::after{content:attr(title);position:absolute;left:54px;top:50%;transform:translateY(-50%);background:#14121F;color:#fff;font-size:12px;font-weight:500;padding:6px 10px;border-radius:9px;white-space:nowrap;pointer-events:none;box-shadow:0 6px 18px rgba(20,18,31,.3)}
/* lavender banner header */
.top{position:relative;overflow:hidden;align-items:center;padding:30px 34px;margin:0 0 18px;border-radius:26px;background:radial-gradient(420px 220px at 92% 10%,rgba(255,255,255,.55),transparent 70%),radial-gradient(360px 260px at 78% 110%,rgba(150,110,255,.55),transparent 70%),linear-gradient(120deg,#D9C9FF 0%,#C4AEF8 55%,#A98BF2 100%);box-shadow:var(--sh)}
.top::after{content:"";position:absolute;right:-30px;top:-40px;width:230px;height:230px;border-radius:50%;background:conic-gradient(from 20deg,rgba(255,255,255,.0),rgba(255,255,255,.45),rgba(255,255,255,.0) 40%,rgba(255,255,255,.35) 70%,rgba(255,255,255,0));filter:blur(2px);opacity:.8;pointer-events:none}
.eyebrow{color:rgba(20,18,31,.6);letter-spacing:.16em}
h1{font-size:38px;color:var(--ink);letter-spacing:-.03em}
.stamp{display:inline-flex;align-items:center;gap:8px;background:#fff;border-radius:999px;padding:7px 14px;color:#4A4660;font-size:12px;box-shadow:var(--sh)}
.stamp::before{content:"";width:8px;height:8px;border-radius:50%;background:#2FC46B;box-shadow:0 0 0 4px rgba(47,196,107,.18)}
h2{font-size:22px;letter-spacing:-.02em;margin:38px 0 12px}
/* softer, rounder cards that lift on hover */
.c,.box,.hero,.ctl,.sbox,table.t,iframe.ops,.lc-strip{border-radius:var(--rad);background:#fff;box-shadow:var(--sh)}
.c{padding:18px 20px;transition:transform .18s ease,box-shadow .18s ease}
a.c:hover,label.c:hover,.box:hover{transform:translateY(-4px);box-shadow:0 2px 4px rgba(20,18,31,.05),0 16px 36px rgba(20,18,31,.1)}
.box{transition:transform .18s ease,box-shadow .18s ease}
.c b{font-size:34px;font-weight:700;letter-spacing:-.03em;color:var(--ink)}
.cl{color:#6B6880}
.it{border-radius:12px}
.hero{border-radius:26px;padding:30px 34px}
.hero-h{font-weight:650;letter-spacing:-.025em}
.box h3,.hd th,.grp{color:#8A87A0;letter-spacing:.09em}
.t tr:hover td{background:#F8F6FF}
.t td{border-top:1px solid #F0EEF7}
.b,.pill{box-shadow:inset 0 0 0 .5px rgba(20,18,31,.06)}
.meter{height:8px;background:#EEEAF8;border-radius:999px}.meter i{border-radius:999px}
.acts .n{background:#EFE8FF;color:#5A3FD6}
.go,.vl,.lc-strip span,summary,a{color:var(--bl)}
.seg{background:#E6E1F5!important}
.back{color:var(--bl)}
::selection{background:#D9C9FF}
@media(max-width:900px){
 .wrap{padding:max(14px,env(safe-area-inset-top)) 14px 96px}
 .bar{left:50%;right:auto;top:auto;bottom:max(12px,env(safe-area-inset-bottom));transform:translateX(-50%);flex-direction:row;width:auto;max-width:calc(100vw - 20px);height:60px;padding:0 12px;gap:2px;border-radius:30px;overflow-x:auto;overflow-y:hidden}
 .bar a{flex:none;width:42px;height:42px}
 .bar a:hover::after{display:none}
 .top{padding:22px 20px;border-radius:22px}
 h1{font-size:28px}
}
"""
page = f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name=apple-mobile-web-app-capable content=yes><meta name=mobile-web-app-capable content=yes><meta name=apple-mobile-web-app-status-bar-style content=default><meta name=apple-mobile-web-app-title content="Founder"><meta name=theme-color content="#F5F5F7"><link rel=manifest href="manifest.webmanifest"><link rel=apple-touch-icon href="icon-180.png"><noscript><meta http-equiv=refresh content=120></noscript><title>Founder view</title>{HEADJS}<style>{CSS}{EXTRA_CSS}{THEME_CSS}{JSCSS}{hl}{{background:#C9B6FF!important;box-shadow:0 4px 14px rgba(124,92,250,.35)!important;color:#1B1530!important}}</style></head><body><div class=wrap><div class=top><div><div class=eyebrow>__PROJECT__</div><h1>Founder view</h1></div></div><nav class=bar>{nav}</nav><div id=live>{attn.banner()}<div class=stamp>Updated {datetime.datetime.now().strftime("%a %d %b, %I:%M %p")}. Cards filter the list on their tab; the data refreshes in place without changing your tab.</div>{"".join(panes[k] for k in order)}</div></div>{LABJS}{CTLJS}{attn.JS}<script>(function(){{var KEY="founderTab",t;
if(!location.hash){{try{{var sv=localStorage.getItem(KEY);if(sv)location.hash=sv}}catch(x){{}}}}
window.addEventListener("hashchange",function(){{try{{localStorage.setItem(KEY,location.hash)}}catch(x){{}}arm()}});
function arm(ms){{clearTimeout(t);t=setTimeout(refresh,ms||(location.hash=="#ops"?20000:60000))}}
var lastAct=0;["scroll","wheel","touchstart","touchmove","keydown","mousedown"].forEach(function(ev){{window.addEventListener(ev,function(){{lastAct=Date.now()}},{{passive:true,capture:true}})}});
function norm(x){{return x.replace(/data-ts=\d+/g,"").replace(/Updated [A-Za-z]{{3}} \d+ [A-Za-z]{{3}}, \d+:\d+ [AP]M/g,"").replace(/Data is [^<]*/g,"")}}
function swapPane(o,n,vis){{
 var chk=[].map.call(o.querySelectorAll("input:checked"),function(i){{return i.id}}),op=[].map.call(o.querySelectorAll("details"),function(x){{return x.open}}),sb=[].map.call(o.querySelectorAll(".sbox"),function(b){{return[b.scrollTop,b.scrollLeft]}}),y=window.scrollY;
 if(vis)o.style.minHeight=o.offsetHeight+"px";
 o.innerHTML=n.innerHTML;
 chk.forEach(function(id){{var i=document.getElementById(id);if(i)i.checked=true}});
 [].forEach.call(o.querySelectorAll("details"),function(x,k){{if(op[k])x.open=true}});
 [].forEach.call(o.querySelectorAll(".sbox"),function(b,k){{if(sb[k]){{b.scrollTop=sb[k][0];b.scrollLeft=sb[k][1]}}}});
 if(vis){{window.scrollTo(0,y);setTimeout(function(){{o.style.minHeight="";window.scrollTo(0,y)}},600)}}
 if(o.id==="groom"&&window.labInit)window.labInit()}}
function swapOps(o,n){{var fo=o.querySelector("iframe.ops"),fn=n.querySelector("iframe.ops");if(!fo||!fn)return;var src=fn.getAttribute("srcdoc")||"";if(fo.__src&&norm(fo.__src)===norm(src))return;fo.__src=src;
 try{{var d=new DOMParser().parseFromString(src,"text/html"),doc=fo.contentDocument;if(!doc||!doc.body)return;doc.body.innerHTML=d.body.innerHTML;if(window.fitOps)fitOps()}}catch(x){{}}}}
function refresh(){{
 var ae=document.activeElement;if(document.hidden||Date.now()-lastAct<5000||(ae&&/^(INPUT|TEXTAREA|SELECT)$/.test(ae.tagName)&&ae.type!=="radio")){{arm(5000);return}}
 fetch(location.pathname.split("/").pop()||"FounderStatus.html",{{cache:"no-store"}}).then(function(r){{return r.text()}}).then(function(h){{
  var d=new DOMParser().parseFromString(h,"text/html"),n=d.getElementById("live"),o=document.getElementById("live");if(!n||!o)throw 0;
  var oc=o.children,nc=n.children,cur=document.documentElement.getAttribute("data-tab");
  if(oc.length!==nc.length){{swapPane(o,n,true);arm();return}}
  for(var i=0;i<oc.length;i++){{var a=oc[i],b=nc[i];
   if(a.id==="ops"){{swapOps(a,b);continue}}
   if(a.id==="groom"&&window.LABDIRTY)continue;
   if(a.id){{if(norm(a.outerHTML)!==norm(b.outerHTML))swapPane(a,b,a.id===cur||(a.id==="overview"&&(!cur||cur==="overview")))}}
   else o.replaceChild(document.importNode(b,true),a)}}
  arm()}}).catch(function(){{arm(30000)}})}}
arm()}})();
function fitBar(){{var b=document.querySelector('.bar');if(!b)return;var tb=document.documentElement.getAttribute('data-tab')||'overview',a=b.querySelector('a[href="#'+tb+'"]');if(a)b.scrollLeft=Math.max(0,a.offsetLeft-(b.clientWidth-a.offsetWidth)/2);b.classList.toggle('ovl',b.scrollLeft>4);b.classList.toggle('ovr',b.scrollLeft+b.clientWidth<b.scrollWidth-4)}}
(function(){{var b=document.querySelector('.bar');if(b)b.addEventListener('scroll',function(){{b.classList.toggle('ovl',b.scrollLeft>4);b.classList.toggle('ovr',b.scrollLeft+b.clientWidth<b.scrollWidth-4)}},{{passive:true}});window.addEventListener('hashchange',fitBar);window.addEventListener('resize',fitBar);fitBar()}})();
function fitOps(){{var f=document.querySelector('iframe.ops');try{{var h=f.contentDocument.documentElement.scrollHeight;if(h>50)f.style.height=(h+4)+'px'}}catch(x){{}}}}
setInterval(fitOps,1000);</script></body></html>"""
tmp = os.path.join(D, "FounderStatus.html.tmp"); open(tmp, "w").write(page); os.replace(tmp, os.path.join(D, "FounderStatus.html"))
