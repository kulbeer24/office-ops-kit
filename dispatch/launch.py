"""Launch command centre for the Founder view Overview tab. Pure functions: build(ctx) -> HTML. No network, no tokens.
Reads two editable files next to it: release.txt (the path to launch) and success.txt (what success means). Created with defaults on first run."""
import os, re, json, html, time, datetime, statistics
D = os.path.dirname(os.path.abspath(__file__)); e = html.escape

DEFAULT_RELEASE = """# stage | target date | gates (separate with ;) | what it means | buffer days after the gates are met
# A gate is #<issue number> (done when that issue is closed) or plain text. Add [x] to finish a text gate. Add ~N to say how many days it takes (default 5).
Internal build | 2026-12-01 | #1; Smoke test passes ~1 | The latest work in your own hands first. | 1
Beta | 2026-12-15 | #2; Feedback collected ~5 | A few outside users. | 3
Launch | 2027-01-15 | Release notes ready ~2 | Public release. | 1
"""
DEFAULT_SUCCESS = """# horizon | measure | why it matters | target | now (auto:plan, auto:bugs, auto:g<issue>, or type a value) | how we know
Build | Launch-plan items still open | Everything promised is built | 0 | auto:plan | Launch plan tab
Build | Open bug issues | Fewer open bugs means a calmer launch | Under 5 | auto:bugs | GitHub issues labelled bug
First weeks | Active users | Proof people want it | 100 or more | | After launch
"""
DEFAULT_MKT = """# stage | target date | gates (separate with ;) | what it means | buffer days after the gates are met
Story ready | 2026-12-01 | Name chosen ~2; Core story approved ~2 | Nothing is posted until the story is agreed. | 1
"""
WHY = [("What this is", "One page showing where the project stands, what is in flight and what needs the owner."), ("How it works", "Agents build, review and test; you decide what merges and when.")]

CSS = """<style>
.lc-hero{background:#fff;border-radius:24px;padding:26px 28px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05);display:grid;grid-template-columns:1.4fr 1fr;gap:22px;align-items:center}
.lc-pill{display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:5px 12px;font-weight:600;font-size:13px}.lc-pill i{width:8px;height:8px;border-radius:50%;display:inline-block}
.lc-h{font-size:26px;line-height:1.2;font-weight:650;letter-spacing:-.02em;margin:12px 0 6px}.lc-sub{color:#6E6E73;font-size:14.5px;line-height:1.5}
.lc-tiles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.lc-tile{background:#F5F5F7;border-radius:16px;padding:14px}.lc-tile b{display:block;font-size:28px;line-height:1.1;letter-spacing:-.02em}.lc-tile span{display:block;font-size:12px;color:#6E6E73;margin-top:4px}
.lc-path{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.lc-st{background:#fff;border-radius:18px;padding:14px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05);position:relative}.lc-st.cur{box-shadow:0 0 0 2px #0071E3}.lc-st.done{background:#F3FBF5}
.lc-st h4{margin:0 0 2px;font-size:14px;line-height:1.25}.lc-st .d{font-size:12px;color:#6E6E73}.lc-st .f{font-size:12px;margin-top:2px}.lc-st .f.late{color:#B42318;font-weight:600}.lc-st .f.ok{color:#1F8A3B}
.lc-meter{height:5px;border-radius:3px;background:#E5E5EA;margin:10px 0 8px;overflow:hidden}.lc-meter i{display:block;height:100%;background:#0071E3}.lc-st.done .lc-meter i{background:#34C759}
.lc-st ul{list-style:none;margin:0;padding:0;font-size:12.5px}.lc-st li{display:flex;gap:7px;padding:2px 0;line-height:1.35}.lc-st li:before{content:"";flex:none;width:9px;height:9px;border-radius:50%;border:1.5px solid #AEAEB2;margin-top:4px}.lc-st li.ok:before{background:#34C759;border-color:#34C759}.lc-st li.ok{color:#6E6E73}
.lc-st .w{font-size:12px;color:#6E6E73;margin-top:8px;line-height:1.4}
.lc-two{display:grid;grid-template-columns:1fr 1fr;gap:12px}.lc-card{background:#fff;border-radius:18px;padding:16px 18px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}.lc-card h3{margin:0 0 8px;font-size:15px}.lc-card ul{margin:6px 0 0;padding-left:18px;font-size:13.5px;line-height:1.5}
.lc-three{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.lc-card p{margin:0;font-size:13.5px;line-height:1.5;color:#3A3A3C}
.lc-tbl{width:100%;border-collapse:collapse;font-size:13.5px}.lc-tbl th{text-align:left;font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:#86868B;padding:10px 12px;position:sticky;top:0;background:#fff;box-shadow:0 1px 0 #EDEDF0}.lc-tbl td{padding:10px 12px;border-top:1px solid #F2F2F7;vertical-align:top}.lc-tbl .m{color:#6E6E73;font-size:12.5px}.lc-grp td{background:#F5F5F7;font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:#6E6E73;font-weight:600}
.lc-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;background:#C7C7CC}.lc-dot.g{background:#34C759}.lc-dot.a{background:#FF9500}.lc-dot.r{background:#FF3B30}
.lc-fb{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:10px}
.lc-q{padding:10px 0;border-top:1px solid #F2F2F7;font-size:13.5px;line-height:1.45}.lc-q:first-child{border-top:0}.lc-q .m{color:#6E6E73;font-size:12px}
details.lc-more{background:#fff;border-radius:18px;padding:4px 18px;box-shadow:0 0 0 .5px rgba(0,0,0,.06)}details.lc-more>summary{cursor:pointer;padding:12px 0;font-weight:600;font-size:14px}
@media(max-width:900px){.lc-hero,.lc-two,.lc-three{grid-template-columns:1fr}.lc-path{grid-template-columns:1fr}.lc-fb{grid-template-columns:1fr 1fr}.lc-h{font-size:22px}}

.lc-need{display:inline-block;margin-top:10px;font-size:13px;font-weight:600;color:#0071E3;text-decoration:none}.lc-st .g{font-size:12px;color:#6E6E73;margin-top:2px}.lc-st .w{margin-top:6px;min-height:15px}
.lc-gl{list-style:none;padding:0!important;margin:6px 0!important}.lc-gl li{display:flex;gap:7px;padding:3px 0}.lc-gl li:before{content:"";flex:none;width:9px;height:9px;border-radius:50%;border:1.5px solid #AEAEB2;margin-top:5px}.lc-gl li.ok:before{background:#34C759;border-color:#34C759}.lc-gl li.ok{color:#6E6E73}
.lc-miles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.lc-mile{background:#fff;border-radius:18px;padding:16px 18px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}
.lc-mile .mh{display:flex;flex-direction:column;margin-bottom:8px}.lc-mile h4{margin:0;font-size:16px}.lc-mile .mh span{font-size:12px;color:#6E6E73}.lc-mile ul{list-style:none;margin:0;padding:0}.lc-mile li{display:flex;align-items:baseline;gap:6px;padding:6px 0;border-top:1px solid #F2F2F7;font-size:13px;line-height:1.35}.lc-mile li:first-child{border-top:0}.lc-mile .mn{flex:1}.lc-mile li b{font-weight:600;white-space:nowrap;color:#1D1D1F}.lc-mile .nv{display:block;font-style:normal;font-size:12px;color:#6E6E73}.lc-mile .mf{margin-top:8px;font-size:12px;color:#6E6E73}
@media(max-width:900px){.lc-miles{grid-template-columns:1fr}}
</style>"""

def _read(name, default):
    p = os.path.join(D, name)
    try:
        t = open(p).read()
        if t.strip(): return t
    except Exception: pass
    try: open(p, "w").write(default)
    except Exception: pass
    return default

def _rows(text):
    return [[x.strip() for x in l.split("|")] for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]

def _fmt_h(minutes):
    return "%.0fh" % (minutes / 60.0) if minutes >= 90 else "%dm" % round(minutes)

def build(c):
    now = c["now"]; day = c["day"]; link = c["link"]; issues = c["issues"]; M = c["M"]; lanes = c["lanes"]
    ts = c["ts"]; lbl = c["lbl"]; short = c["short"]
    allx = {str(i["number"]): i for i in c["all_issues"]}
    # auto gate helpers: "@buildN" is met once last_build.txt records build N or later; "@nop01bug" once no open bug is ranked P0 or P1
    try:
        _lbl = [l for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_build.txt")) if l.strip() and not l.startswith("#")][0]
        _lb_n = int(re.search(r"build\s*(\d+)", _lbl, re.I).group(1))
    except Exception: _lb_n = 0
    try: _tiers = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "priorities.json"))).get("tiers", {})
    except Exception: _tiers = {}
    _p01_bug = [n for n, it in allx.items() if it.get("state") == "OPEN" and _tiers.get(n) in ("P0", "P1") and ("bug" in [lbl(x) for x in it.get("labels", [])] or it["title"].lower().startswith(("bug", "fix:")))]
    am = {str(m["issue"]): m for m in M.get("issues", [])}
    def klass(i):
        t = i["title"].lower(); ls = [lbl(x) for x in i.get("labels", [])]
        if "bug" in ls or t.startswith(("bug", "fix:")): return "bug"
        if any(k in t for k in ("design", "audit", "persona", "inventory", "spec")): return "design"
        if "chore" in ls or "ops" in ls: return "chore"
        return "feature"
    closed = [i for i in issues if i["state"] == "CLOSED" and (am.get(str(i["number"])) or {}).get("active_min", 0) > 0]
    by = {}
    for i in closed: by.setdefault(klass(i), []).append(am[str(i["number"])]["active_min"])
    allm = [x for v in by.values() for x in v]
    med_all = statistics.median(allm) if allm else 60
    def q75(v):
        v = sorted(v); return v[min(len(v) - 1, int(round(0.75 * (len(v) - 1))))]
    med = {k: (q75(v) if len(v) >= 3 else med_all) for k, v in by.items()}   # a cautious estimate: the 75th percentile, not the median
    def est(i):
        m = am.get(str(i["number"])) or {}
        if m.get("projected_min"): return max(10, m["projected_min"] - m.get("active_min", 0))
        base = med.get(klass(i), med_all); t = i["title"].lower()
        return base * 6 if ("design first" in t or "redesign" in t) else base   # big redesigns are split into stories later; 6x is a placeholder
    # throughput: agent-minutes finished per day over the last 14 days
    recent = [am[str(i["number"])]["active_min"] for i in closed if i.get("closedAt") and now - (ts(i["closedAt"]) or 0) < 14 * 86400]
    thr = max(60.0, sum(recent) / 14.0) if recent else 240.0
    # backlog in priority order (Now, Next, Later; Parked is not in the launch plan)
    back = []
    for k in ("P0", "P1", "P2"):
        for i in lanes.get(k, []):
            if i["state"] == "OPEN": back.append((k, i))
    cum = 0.0; plan = []
    for k, i in back:
        m = est(i); cum += m; plan.append((k, i, m, now + cum / thr * 86400))
    tot_min = cum; likely = now + tot_min / thr * 86400; early = now + tot_min / (thr * 1.25) * 86400; late = now + tot_min / (thr * 0.75) * 86400
    T = c["T"]; tl = T.get("launch"); launch_ts = tl[0] if tl else None
    arrivals = c["arrivals_per_week"]; med_item = (tot_min / len(plan)) if plan else med_all
    # release path: each stage's forecast chains on the one before it (a stage cannot finish before the stage under it)
    fin_of = {str(i["number"]): f for k, i, m, f in plan}
    DAY = 86400.0
    def _run(text, prev, floor=False):
        stages = []; _prev_done = True
        for r in _rows(text):
            if len(r) < 3: continue
            try: tgt = datetime.datetime.strptime(r[1], "%Y-%m-%d").timestamp()
            except Exception: tgt = None
            try: buf = float(r[4]) if len(r) > 4 else 0.0
            except Exception: buf = 0.0
            gl = []; ready = prev
            for g in [x.strip() for x in r[2].split(";") if x.strip()]:
                m = re.match(r"#(\d+)", g)
                if m:
                    n = m.group(1); it = allx.get(n); ok = bool(it) and it["state"] == "CLOSED"
                    if not ok and it:
                        if it["title"].lower().startswith("owner:"):
                            lead = 14 if "clinician" in it["title"].lower() else 7
                            cr = ts(it.get("createdAt") or "") or now; rdy = max(now, cr + lead * DAY)
                        elif n in fin_of: rdy = fin_of[n] + (3 * DAY if klass(it) == "design" else 0)
                        else: rdy = now + 14 * DAY
                        ready = max(ready, rdy)
                    gl.append((ok, ("#" + n + " " + short(re.sub(r"^Owner:\s*", "", it["title"]))[:58]) if it else g, n))
                else:
                    ok = g.endswith("[x]"); g2 = g.replace("[x]", "").strip(); lead = 5.0
                    mb = re.search(r"\s*@build(\d+)", g2)
                    if mb: ok = ok or _lb_n >= int(mb.group(1)); g2 = g2.replace(mb.group(0), "").strip()
                    if "@nop01bug" in g2: ok = ok or not _p01_bug; g2 = g2.replace("@nop01bug", "").strip()
                    mm = re.search(r"~(\d+)\s*$", g2)
                    if mm: lead = float(mm.group(1)); g2 = g2[:mm.start()].strip()
                    if not ok: ready = max(ready, prev + lead * DAY)
                    gl.append((ok, g2, None))
            alld = bool(gl) and all(g[0] for g in gl) and _prev_done     # a stage is only done when every earlier stage is done too
            _prev_done = alld
            fin = prev if alld else ready + buf * DAY
            if floor and tgt and not alld: fin = max(fin, tgt - 3 * DAY)   # dated activities (posts, emails) happen near their date, not as soon as the gates allow
            prev = max(prev, fin)
            stages.append(dict(name=r[0], tgt=tgt, gates=gl, done=bool(alld), fin=None if alld else fin, why=r[3] if len(r) > 3 else ""))
        return stages
    stages = _run(_read("release.txt", DEFAULT_RELEASE), now)
    try: mkt = _run(_read("marketing.txt", DEFAULT_MKT), now, True)   # parallel lane: same gate rules, its own chain
    except Exception: mkt = []
    cur = next((k for k, s_ in enumerate(stages) if not s_["done"]), None)
    # hero verdict: the launch forecast is the end of the stage chain; the work scenarios show how scope growth moves the dev part
    rc = stages[2]["tgt"] if len(stages) > 2 and stages[2]["tgt"] else launch_ts
    weeks_rc = max(1.0, ((rc or now + 28 * DAY) - now) / (7 * DAY)); extra = arrivals * weeks_rc * med_item
    best = now + tot_min / (thr * 1.25) / 1440 * DAY if False else now + tot_min / (thr * 1.25) * DAY
    likely_dev = now + (tot_min + 0.4 * extra) / thr * DAY; late_dev = now + (tot_min + 0.7 * extra) / (thr * 0.75) * DAY
    chain_end = stages[-1]["fin"] if stages and stages[-1]["fin"] else (launch_ts or now)
    if launch_ts:
        slack = (launch_ts - chain_end) / DAY
        if slack >= 14: col, head = ("#1F8A3B", "#E8F8EE"), "On track"
        elif slack >= 0: col, head = ("#B35C00", "#FFF3E0"), "Tight"
        else: col, head = ("#C4281C", "#FDECEA"), "At risk"
        left = max(0, round((launch_ts - now) / DAY))
        slack_txt = ("%d days of room" % round(slack)) if slack >= 0 else ("%d days late" % round(-slack))
        sub = ("Building what is queued takes about %s of agent time, done around %s if nothing new is added (up to %s if new work keeps arriving). The real pacing items are people and approvals: clinician review, privacy, analytics, App Store listing and review. Chaining them, we are launch-ready around %s against %s: %s." % (_fmt_h(tot_min), day(likely_dev), day(late_dev), day(chain_end), day(launch_ts), slack_txt))
    else:
        col, head, left, sub = ("#636366", "#F2F2F7"), "No launch date set", 0, "Set a launch date in dispatch/targets.txt."
    likely = likely_dev; early = best; late = late_dev
    needn = len(c["owner"])
    sub2 = ("Target %s. Build work done around %s; the long poles are people and approvals (clinician, privacy, listing, review)." % (day(launch_ts), day(likely_dev))) if launch_ts else sub
    hero = ('<div class=lc-hero><div><span class=lc-pill style="background:%s;color:%s"><i style="background:%s"></i>%s</span><div class=lc-h>%s</div><div class=lc-sub>%s</div>%s</div>'
            '<div class=lc-tiles><div class=lc-tile><b>%s</b><span>days to launch</span></div><div class=lc-tile><b>%d</b><span>items left (%s of work)</span></div><div class=lc-tile><b>%s</b><span>launch-ready</span></div></div></div>'
            % (col[1], col[0], col[0], e(head), e(("Launch-ready around %s, %s" % (day(chain_end), slack_txt)) if launch_ts else "Launch plan"), e(sub2),
               ('<a class=lc-need href="#launch">%d items need you &rarr;</a>' % needn) if needn else "", left, len(plan), _fmt_h(tot_min), e(day(chain_end))))
    # release path html
    def _cards(stages, cur):
        st_html = ""
        for k, s_ in enumerate(stages):
            n_ok = sum(1 for g in s_["gates"] if g[0]); n = len(s_["gates"]) or 1
            done = n_ok == len(s_["gates"]) and s_["gates"]
            cls = "lc-st" + (" done" if done else "") + (" cur" if k == cur else "")
            f = ""
            if s_["fin"] and s_["tgt"]:
                dl = round((s_["fin"] - s_["tgt"]) / 86400)
                f = '<div class="f %s">%s</div>' % ("late" if dl > 0 else "ok", ("%s (%d day%s late)" % (day(s_["fin"]), dl, "" if dl == 1 else "s")) if dl > 0 else "%s, on time" % day(s_["fin"]))
            elif done: f = '<div class="f ok">Done</div>'
            waits = [("#" + nn) if nn else (txt[:22] + ("..." if len(txt) > 22 else "")) for ok, txt, nn in s_["gates"] if not ok]
            wt = ("Waiting: " + ", ".join(waits[:2]) + (" +%d" % (len(waits) - 2) if len(waits) > 2 else "")) if waits else ""
            st_html += ('<div class="%s"><h4>%s</h4><div class=d>Target %s</div>%s<div class=lc-meter><i style="width:%d%%"></i></div><div class=g>%d of %d gates</div><div class=w>%s</div></div>'
                        % (cls, e(s_["name"]), e(day(s_["tgt"])) if s_["tgt"] else "no date", f, round(100 * n_ok / n), n_ok, len(s_["gates"]), e(wt)))
        return st_html
    st_html = _cards(stages, cur)
    mk_cur = next((k for k, s_ in enumerate(mkt) if not s_["done"]), None)
    mk_html = ("<h2>Marketing lane: building excitement to the trial and the New Year</h2><div class=lc-path>%s</div><div class=m style=\"margin:6px 0 4px\">Same rules as the road above. Edit stages, dates and gates in dispatch/marketing.txt; add [x] to a gate when it is done. Briefs: 01-vision/marketing-and-expansion-brief.md.</div>" % _cards(mkt, mk_cur)) if mkt else ""
    gate_rows = ""
    for s_ in stages:
        lis = "".join('<li class="%s">%s</li>' % ("ok" if ok else "", (link(nn) + e(" " + txt[len(nn) + 1:].strip()) if nn else e(txt))) for ok, txt, nn in s_["gates"])
        gate_rows += '<div class=lc-card><h3>%s</h3><ul class=lc-gl>%s</ul><div class=m>%s</div></div>' % (e(s_["name"]), lis, e(s_["why"]))
    path = '<h2>The road to launch</h2><div class=lc-path>%s</div>' % st_html
    # plan table
    gate_of = {}
    for s in stages:
        for ok, txt, nn in s["gates"]:
            if nn: gate_of.setdefault(nn, s["name"])
    rows = ""; lastk = None; names = {"P0": "Now", "P1": "Next", "P2": "Later"}
    for k, i, m, f in plan:
        if k != lastk: rows += '<tr class=lc-grp><td colspan=5>%s</td></tr>' % names[k]; lastk = k
        n = str(i["number"]); st_ = gate_of.get(n)
        late_ = st_ and next((s for s in stages if s["name"] == st_ and s["tgt"] and f > s["tgt"]), None)
        rows += '<tr><td>%s</td><td>%s%s</td><td class=m>%s</td><td class=m>%s</td><td class=m%s>%s</td></tr>' % (link(i["number"]), e(short(i["title"])[:88]), ' <span class=m>(%s)</span>' % e(klass(i)), _fmt_h(m), e(day(f)), ' style="color:#B42318;font-weight:600"' if late_ else "", (e(st_) + (" (late)" if late_ else "")) if st_ else "")
    # levers
    qa_med = (M.get("medians_min") or {}).get("qa", 23); aq = M.get("avg_qa_rounds") or 2
    p2 = [(m, i) for k, i, m, f in plan if k == "P2"]; p2m = sum(m for m, i in p2)
    save_qa = len(plan) * max(0, aq - 3) * qa_med
    levers = []
    if p2: levers.append("Move the %d Later items to after launch: saves about %s of work (%s sooner)." % (len(p2), _fmt_h(p2m), ("roughly %d days" % round(p2m / thr)) if p2m / thr >= 1 else "under a day"))
    if save_qa > 30: levers.append("Hold review to three QA rounds (it averages %.1f): saves about %s across the plan." % (aq, _fmt_h(save_qa)))
    des = [(m, i) for k, i, m, f in plan if klass(i) == "design"]
    if des: levers.append("Run the %d design-first items (%s) alongside building, not before it, so approvals do not queue behind code." % (len(des), ", ".join("#" + str(i["number"]) for m, i in des[:4])))
    blocked = c.get("blocked", 0)
    if blocked: levers.append("%d items are waiting on you (owner to-dos and approvals). Clearing them unblocks work that agents cannot do." % blocked)
    if arrivals and thr:
        burn = thr * 7 - arrivals * med_item
        levers.append("New issues arrive at about %.0f a week (about %s of work). %s" % (arrivals, _fmt_h(arrivals * med_item), "That is more than we finish, so the plan only shrinks if new items are deferred." if burn <= 0 else "We finish more than that, so the plan shrinks by about %s a week." % _fmt_h(burn)))
    titles = " ".join(i["title"].lower() for i in c["all_issues"])
    gaps = []
    for pat, label, why in ():
        hit = next((i for i in sorted(c["all_issues"], key=lambda x: x["state"] != "OPEN") if re.search(pat, i["title"].lower()) and not i["title"].lower().startswith("owner")), None)
        gaps.append((label, why, hit))
    gap_li = "".join("<li><b>%s</b>: %s %s</li>" % (e(l), e(w), (("Done in " if h["state"] == "CLOSED" else "Tracked as ") + link(h["number"]) + ".") if h else "<i>Not in the backlog yet.</i>") for l, w, h in gaps)
    plan_html = ('<h2>Plan to deploy: everything between us and launch</h2><div class=lc-two>'
                 '<div class=lc-card><h3>How fast can we go?</h3><ul><li>Recent speed: about %s of agent work finished per day (last 14 days).</li><li>Queued work done by: %s with no new scope and 25%% faster; %s if 40%% of new arrivals are also built; %s if 70%% are and we slow down 25%%.</li><li>Estimates use the 75th-percentile time of similar closed issues (cautious); big redesigns count six times that until split into stories (%s).</li></ul></div>'
                 '<div class=lc-card><h3>Ways to finish earlier</h3><ul>%s</ul></div></div>'
                 '<div class=lc-card style="margin-top:12px"><h3>What else launch needs that is not tracked yet (proposed)</h3><ul>%s</ul></div>'
                 '<div class=sbox style="margin-top:12px"><table class=lc-tbl><tr><th>Issue</th><th>What</th><th>Estimate</th><th>Expected done</th><th>Needed for</th></tr>%s</table></div>'
                 '<div class=m style="margin-top:6px">Order follows the Prioritise tab. Expected done adds each item to the ones above it at our recent speed.</div>'
                 % (_fmt_h(thr), e(day(early)), e(day(likely)), e(day(late)), ", ".join("%s %s" % (k, _fmt_h(v)) for k, v in sorted(med.items())) or "no history yet", "".join("<li>%s</li>" % e(x) for x in levers) or "<li>Nothing obvious: keep the current order.</li>", gap_li, rows))
    # success metrics by horizon
    tf7 = c["tf7"]; openbugs = c["open_bugs"]
    def auto(tok):
        if tok == "auto:tf7": return str(tf7), "g" if tf7 >= 5 else "a"
        if tok == "auto:bugs": return str(openbugs), "g" if openbugs < 5 else "a"
        if tok == "auto:plan": return str(len(plan)), "g" if not plan else "a"
        m = re.match(r"auto:g(\d+)", tok)
        if m:
            it = allx.get(m.group(1)); ok = bool(it) and it["state"] == "CLOSED"; return ("Done" if ok else "Open"), ("g" if ok else "a")
        return None
    HOR = {"Build": "Now to the next builds", "Release": "test build to App Store", "Marketing": "Pre-launch to the New Year", "First days": "Days 1 to 7", "First weeks": "Weeks 1 to 4", "First months": "Months 2 to 6", "Year 1 and beyond": "Months 7 to 36"}
    groups = {}; detail = ""
    for r in _rows(_read("success.txt", DEFAULT_SUCCESS)):
        if len(r) < 4: continue
        g, mname, why, tgt = r[0], r[1], r[2], r[3]; cur_ = r[4] if len(r) > 4 else ""; how = r[5] if len(r) > 5 else ""
        a_ = auto(cur_) if cur_.startswith("auto:") else None
        if a_: val, dot = a_
        elif cur_: val, dot = cur_, "g"
        else: val, dot = "Not measured yet", ""
        groups.setdefault(g, []).append((mname, tgt, val, dot))
        detail += '<tr><td>%s</td><td>%s</td><td class=m>%s</td><td class=m>%s</td></tr>' % (e(g), e(mname), e(why), e(how))
    cards_ = ""
    for g, L in groups.items():
        lis = "".join('<li><span class="lc-dot %s"></span><span class=mn>%s%s</span><b>%s</b></li>' % (d, e(m), ('<i class=nv>now: %s</i>' % e(v)) if d else '', e(t)) for m, t, v, d in L)
        got = sum(1 for m, t, v, d in L if d == "g")
        cards_ += '<div class=lc-mile><div class=mh><h4>%s</h4><span>%s</span></div><ul>%s</ul><div class=mf>%d of %d met</div></div>' % (e(g), e(HOR.get(g, "")), lis, got, len(L))
    why_html = '<div class=lc-three>%s</div>' % "".join('<div class=lc-card><h3>%s</h3><p>%s</p></div>' % (e(a), e(b)) for a, b in WHY)
    success_tab = ('<div class=m style="margin-bottom:10px">Grey dot means not measured yet; the targets are proposals you can edit in dispatch/success.txt.</div><div class=lc-miles>%s</div>' % cards_
                   + '<h2>Why people will want it</h2>' + why_html
                   + '<h2>Why each measure matters</h2><div class=sbox><table class=lc-tbl><tr><th>When</th><th>Measure</th><th>Why it matters</th><th>How we know</th></tr>%s</table></div>' % detail)
    fb = c["fb_items"]
    lat = "".join('<div class=lc-q>%s<div class=m>%s &middot; %s</div></div>' % (e(t[:170] + ("..." if len(t) > 170 else "")), e(d), e(kind)) for d, kind, t in fb[:6]) or '<div class=m>No feedback yet.</div>'
    fb_html = ('<h2>What testers are telling us (App Store Connect)</h2><div class=lc-fb><div class=lc-tile><b>%d</b><span>pieces of feedback, last 7 days</span></div><div class=lc-tile><b>%d</b><span>in total</span></div><div class=lc-tile><b>%d</b><span>open bug issues</span></div></div>'
               '<div class=lc-card>%s<div class=m style="margin-top:8px">Crashes, sessions and installs are not pulled in yet; that is the next addition.</div></div>' % (tf7, c["tf_total"], openbugs, lat))
    owner = c["owner"]
    need = ('<h2>Needs you</h2><div class=lc-card><ul>%s</ul><div class=m style="margin-top:8px">Finished one? Open it and close the issue on GitHub; this list clears within a minute.</div></div>'
            % ("".join("<li>%s %s</li>" % (link(i["number"]), e(re.sub(r"^Owner:\s*", "", i["title"]))) for i in owner) or "<li>Nothing right now.</li>"))
    plan_tab = need + '<h2>Gates for each stage</h2><div class=lc-two>%s</div><div class=m style="margin-top:6px">Edit stages and gates in dispatch/release.txt. An issue gate turns green by itself when the issue is closed.</div>' % gate_rows + plan_html + fb_html
    summary = dict(head=head, chain_end=day(chain_end), target=day(launch_ts) if launch_ts else '', slack=slack_txt if launch_ts else '', left=left, items=len(plan), work=_fmt_h(tot_min), need=len(c['owner']))
    stages_out = [dict(name=s_["name"], tgt=s_["tgt"], fin=s_["fin"], done=s_["done"]) for s_ in stages]
    return dict(css=CSS, hero=hero, road=path, mkt=mk_html, plan=plan_tab, success=success_tab, summary=summary, stages=stages_out, launch_ts=launch_ts)
