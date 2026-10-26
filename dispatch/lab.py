#!/usr/bin/env python3
"""Founder Lab (side page, does not touch FounderStatus.html or status.html): writes dispatch/FounderLab.html with three tabs:
Groom (rank and prioritise open issues; saves to priorities.json through the phone server), Roadmap tree (app > themes > issues, click to expand),
User journey (steps a runner takes, mapped to the backlog, with gaps). Reads local caches only (no network). Called from run_batch.sh every loop."""
import os, re, json, time, ast, html, datetime
D = os.path.dirname(os.path.abspath(__file__)); now = time.time(); e = html.escape; R = "__REPO__"
def read(p, d=""):
    try: return open(os.path.join(D, p)).read()
    except Exception: return d
def jl(p, d):
    try: return json.load(open(os.path.join(D, p)))
    except Exception: return d
def ts(s):
    try: return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception: return None
# reuse the look of the founder page (CSS and icons) without importing or changing it
src = ast.parse(read("founder.py")); CSS = ""; ICONS = {}
for n in src.body:
    if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ("CSS", "ICONS"):
        v = ast.literal_eval(n.value);
        if n.targets[0].id == "CSS": CSS = v
        else: ICONS = v
ICONS.update({"up": '<path d="M6 15l6-6 6 6"/>', "down": '<path d="M6 9l6 6 6-6"/>'})
def icon(k, cls="ic"): return f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{ICONS.get(k, ICONS.get("chart", ""))}</svg>'

# ---------- data ----------
issues = jl("cache/issues_live.json", None)
if not issues:
    openn = {x["number"] for x in jl("cache/open_issues.json", [])}
    issues = [{"number": x["number"], "title": x["title"], "labels": [], "state": "OPEN" if x["number"] in openn else "CLOSED", "createdAt": "", "closedAt": ""} for x in jl("cache/issues.json", [])]
prs = jl("cache/prs_live.json", None) or jl("cache/prs.json", [])
lbl = lambda x: x["name"] if isinstance(x, dict) else x
started = set(os.listdir(os.path.join(D, "started"))) if os.path.isdir(os.path.join(D, "started")) else set()
donef = set(os.listdir(os.path.join(D, "done"))) if os.path.isdir(os.path.join(D, "done")) else set()
batch = {l.strip() for l in read("batch.txt").splitlines() if l.strip() and not l.startswith("#")}
inpr = {m.group(1) for p in prs if p.get("state", "OPEN") == "OPEN" for m in [re.match(r"(\d+)-", p.get("headRefName", ""))] if m}
# last result line the dev agent for an issue wrote to status.md (used to spot "finished but blocked")
_res = {}
for _ln in read("status.md").splitlines():
    _m = re.match(r"- #(\d+) DONE: (.*)", _ln)
    if _m: _res[_m.group(1)] = _m.group(2)
def blocked_reason(n):
    r = _res.get(str(n), "")
    return re.sub(r"^BLOCKED:?\s*", "", r)[:150] if r.upper().startswith("BLOCKED") else ""
def state(i):
    n = str(i["number"])
    if i["state"] == "CLOSED": return "Done"
    if n in inpr: return "In review"
    if n in started and n not in donef: return "Running"
    if n in donef and blocked_reason(n): return "Blocked"
    if n in batch and n not in started: return "Queued"
    return "Open"
SC = {"Done": ("#1F8A3B", "#E8F8EE"), "In review": ("#0A60C2", "#E8F1FD"), "Running": ("#B35C00", "#FFF3E0"), "Blocked": ("#C4281C", "#FDECEA"), "Queued": ("#3A3A3C", "#E9E9EE"), "Open": ("#636366", "#F2F2F7")}
def chip(s, t=None): fg, bg = SC.get(s, SC["Open"]); return f'<span class=b style="background:{bg};color:{fg}"><i style="background:{fg}"></i>{e(t or s)}</span>'
def link(n): return f'<a href="https://github.com/{R}/issues/{n}" target=_blank>#{n}</a>'
EP = [[x.strip() for x in l.split("|")] for l in read("roadmap.txt").splitlines() if l.strip() and not l.startswith("#")]
def epic_of(t):
    t = t.lower()
    for ep in EP:
        if any(k.strip() and k.strip() in t for k in ep[1].split(",")): return ep[0]
    return None
real = [i for i in issues if not i["title"].lower().startswith(("[note]", "owner:"))]

# ---------- Groom ----------
PL = []
for l in read("pipeline.txt").splitlines():
    p = [x.strip() for x in l.split("|")]
    if not l.startswith("#") and len(p) >= 4: PL.append(p)
wave_of = {p[1]: p[0] for p in PL}
cand = [i for i in real if i["state"] == "OPEN" and not any(lbl(x).startswith("epic:") for x in i.get("labels", []))]
pri = jl("priorities.json", {}); tiers = pri.get("tiers", {}); rank = {str(n): k for k, n in enumerate(pri.get("order", []))}
def default_tier(i):
    n = str(i["number"]); t = i["title"].lower()
    if state(i) in ("Running", "Queued", "In review", "Blocked"): return "P0"
    w = wave_of.get(n, "")
    if w.startswith(("Wave 1", "Wave 2", "Wave 3")): return "P0"
    if w.startswith("Wave 4"): return "P1"
    if t.startswith("backlog") or "status:deferred" in [lbl(x) for x in i.get("labels", [])]: return "Parked"
    return "P2"
pl_idx = {p[1]: k for k, p in enumerate(PL)}
def sortkey(i):
    n = str(i["number"]); return (rank.get(n, 10 ** 6), pl_idx.get(n, 10 ** 5), -i["number"])
LAN = [("P0", "Now", "Agents work on these first, automatically. Keep it to about three."), ("P1", "Next", "Picked up as soon as Now has room."), ("P2", "Later", "Not scheduled. Move up when it matters."), ("Parked", "Parked", "Deliberately not doing for now.")]
lanes = {k: [] for k, _, _ in LAN}
for i in sorted(cand, key=sortkey): lanes[tiers.get(str(i["number"])) if tiers.get(str(i["number"])) in lanes else default_tier(i)].append(i)
TF_RE = re.compile(r"\s*\(test build feedback[^)]*\)")
def row(i):
    n = i["number"]; ep = epic_of(i["title"]); age = round((now - ts(i["createdAt"])) / 86400) if ts(i.get("createdAt", "")) else None
    tag = '<span class=tg>Tester feedback</span>' if "testflight feedback" in i["title"].lower() or "tester" in i["title"].lower() else ""
    st = state(i); tier_ = tiers.get(str(n)) if tiers.get(str(n)) in ("P0", "P1", "P2", "Parked") else default_tier(i)
    stc = (chip(st, "Running early (spare slot)") if st == "Running" and tier_ != "P0" else chip(st)) if st != "Open" else ""
    why_ = f'<div class=m style="color:#C4281C;margin-top:4px">Needs you: {e(blocked_reason(n))}</div>' if st == "Blocked" else ""
    ttl = e(TF_RE.sub("", i["title"])[:120])
    return (f'<li class=gr data-n="{n}"><div class=gm><div class=gt>{link(n)} {ttl}</div>'
            f'<div class=gs>{stc}{tag}{"<span class=tg>" + e(ep) + "</span>" if ep else ""}{"<span class=m>" + str(age) + " days old</span>" if age is not None else ""}</div>{why_}</div>'
            f'<div class=gc><button type=button data-a=up title="Move up">{icon("up")}</button><button type=button data-a=down title="Move down">{icon("down")}</button>'
            + "".join(f'<button type=button class=tb data-t="{k}">{lab}</button>' for k, lab in (("P0", "Now"), ("P1", "Next"), ("P2", "Later"), ("Parked", "Park"))) + '</div></li>')
lane_html = "".join(f'<section class=lane data-tier="{k}"><div class=lh><h3>{e(name)}</h3><span class=lc>{len(lanes[k])}</span></div><div class=m>{e(hint)}</div><ul>{"".join(row(i) for i in lanes[k])}</ul></section>' for k, name, hint in LAN)
saved = pri.get("saved", "")
groom = (f'<div class=m style="margin-bottom:10px">Rank what matters. Agents pick up the top of <b>Now</b>, then <b>Next</b>, on their own while dev is on. Use the arrows to reorder and the buttons to move an issue between lanes, then Save.</div>'
         f'<div class=lstick><div class=savebar><button type=button id=save class=btn>Save priorities</button><span id=sv class=m>{("Last saved " + e(saved[:16].replace("T", " "))) if saved else "Nothing saved yet. Defaults come from the build pipeline."}</span></div>'
         f'<div class=lj id=lj>' + "".join(f'<button type=button data-j="{k}">{e(name)} <i>{len(lanes[k])}</i></button>' for k, name, hint in LAN) + '</div></div>'
         f'<div id=gl>{lane_html}</div>')

# ---------- Roadmap tree ----------
def tree():
    out = []
    for ep in EP:
        L = sorted([i for i in real if epic_of(i["title"]) == ep[0] and not i["title"].lower().startswith("backlog")], key=lambda i: (i["state"] == "CLOSED", -i["number"]))
        dn = sum(i["state"] == "CLOSED" for i in L); pc = round(100 * dn / len(L)) if L else 0
        act = [i for i in L if i["state"] == "OPEN" and state(i) != "Open"]; opn = [i for i in L if i["state"] == "OPEN" and state(i) == "Open"]; cl = [i for i in L if i["state"] == "CLOSED"]
        def items(xs): return "".join(f'<li class=lf>{chip(state(i))} {link(i["number"])} <span>{e(i["title"][:100])}</span></li>' for i in xs)
        grp = ""
        if act: grp += f'<div class=tg2>In flight ({len(act)})</div><ul class=lv>{items(act)}</ul>'
        if opn: grp += f'<div class=tg2>Open ({len(opn)})</div><ul class=lv>{items(opn)}</ul>'
        if cl: grp += f'<details class=dn><summary>Done ({len(cl)})</summary><ul class=lv>{items(cl)}</ul></details>'
        col = "#34C759" if pc >= 80 else "#0071E3" if pc >= 60 else "#FF9500"
        out.append(f'<li class=ep><details><summary><span class=en>{e(ep[0])}</span><span class=eb><span class=meter><i style="width:{pc}%;background:{col}"></i></span></span><span class=ec>{dn} of {len(L)}</span></summary><div class=eg>{grp or "<div class=m>No issues yet.</div>"}</div></details></li>')
    return f'<div class=m style="margin-bottom:10px">Click a theme to open its issues. Later this links each theme to the screens and the user journey it delivers.</div><div class=tree><div class=root>{icon("overview")}<b>__PROJECT__</b><span class=m>the app we are building</span></div><ul class=eps>{"".join(out)}</ul></div>'

# ---------- User journey ----------
steps = []
for l in read("journey.txt").splitlines():
    p = [x.strip() for x in l.split("|")]
    if l.startswith("#") or len(p) < 5: continue
    kws = [k.strip().lower() for k in p[4].split(",") if k.strip()]
    L = [i for i in real if any(k in i["title"].lower() for k in kws)]
    dn = sum(i["state"] == "CLOSED" for i in L); act = sum(1 for i in L if i["state"] == "OPEN" and state(i) != "Open")
    st = "Gap" if not L else "Done" if dn == len(L) else "In progress" if act or dn else "Planned"
    steps.append(dict(stage=p[0], step=p[1], what=p[2], screen=p[3], L=L, dn=dn, st=st))
JC = {"Done": ("#1F8A3B", "#E8F8EE"), "In progress": ("#0A60C2", "#E8F1FD"), "Planned": ("#636366", "#F2F2F7"), "Gap": ("#C4281C", "#FDECEA")}
def journey():
    cnt = {k: sum(1 for s in steps if s["st"] == k) for k in JC}; tot = max(1, len(steps))
    top = "".join(f'<div class=c><span class=it style="background:{JC[k][1]};color:{JC[k][0]}">{icon("check" if k == "Done" else "repeat" if k == "In progress" else "clock" if k == "Planned" else "bug")}</span><b>{cnt[k]}</b><span class=cl>{k} steps</span></div>' for k in JC)
    stages = []; cur = None
    for s in steps:
        if s["stage"] != cur: stages.append((s["stage"], [])); cur = s["stage"]
        stages[-1][1].append(s)
    out = ""
    for name, ss in stages:
        cards = ""
        for k, s in enumerate(ss):
            fg, bg = JC[s["st"]]; pc = round(100 * s["dn"] / len(s["L"])) if s["L"] else 0
            lst = "".join(f'<li>{chip(state(i))} {link(i["number"])} {e(i["title"][:90])}</li>' for i in sorted(s["L"], key=lambda i: (i["state"] == "CLOSED", -i["number"]))) or '<li class=m>Nothing in the backlog covers this step yet. This is a gap to decide on.</li>'
            cards += (f'<details class=step><summary><span class=sn style="background:{bg};color:{fg}">{k + 1}</span><span class=sname>{e(s["step"])}</span><span class=ssc>{e(s["screen"])}</span>'
                      f'<span class=meter><i style="width:{pc}%;background:{fg}"></i></span><span class=sst style="color:{fg}">{e(s["st"])}{(" · " + str(s["dn"]) + " of " + str(len(s["L"]))) if s["L"] else ""}</span></summary><div class=sd><div class=m>{e(s["what"])}</div><ul>{lst}</ul></div></details>')
        out += f'<div class=stage><div class=stn>{e(name)}</div><div class=stp>{cards}</div></div>'
    return (f'<div class=m style="margin-bottom:6px">A simple runner journey, mapped to the backlog. Click a step to see the issues behind it. Screenshots come once the flow is agreed.</div><div class=cards>{top}</div><div class=flow>{out}</div>')

TABS = [("groom", "Groom", "pipeline", lambda: groom), ("tree", "Roadmap tree", "roadmap", tree), ("journey", "User journey", "delivered", journey)]
panes = {k: f'<div class="pane{" def" if k == "groom" else ""}" id="{k}">{f()}</div>' for k, _, _, f in TABS}
order = [k for k, *_ in TABS if k != "groom"] + ["groom"]
nav = "".join(f'<a href="#{k}" title="{n}">{icon(ic)}<span>{n}</span></a>' for k, n, ic, _ in TABS)
hl = "".join(f'body:has(#{k}:target) .bar a[href="#{k}"],' for k, *_ in TABS) + 'body:not(:has(.pane:target)) .bar a[href="#groom"]'
LABCSS = """
.savebar{display:flex;align-items:center;gap:14px;margin:6px 0 14px}.btn{background:#0071E3;color:#fff;border:0;border-radius:999px;padding:9px 20px;font:600 14px inherit;cursor:pointer}.btn:disabled{background:#C7C7CC}
.lane{background:#fff;border-radius:18px;padding:16px 18px;margin:0 0 14px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}.lane ul{list-style:none;margin:8px 0 0;padding:0}.lh{display:flex;align-items:center;gap:10px}.lh h3{margin:0;font-size:17px;font-weight:600;color:#1D1D1F;text-transform:none;letter-spacing:0}.lc{background:#F2F2F7;border-radius:999px;font-size:12px;padding:1px 9px;color:#6E6E73}
.lane[data-tier=P0]{box-shadow:0 0 0 2px #0071E3}.gr{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:11px 0;border-top:1px solid #F2F2F7}.gr:first-child{border-top:0}.gm{min-width:0}.gt{font-size:14px}.gs{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:4px}
.tg{font-size:11px;background:#F2F2F7;color:#3A3A3C;border-radius:999px;padding:2px 9px}.gc{display:flex;gap:5px;flex:none;align-items:center;flex-wrap:wrap;justify-content:flex-end}.gc button{border:0;background:#F2F2F7;color:#3A3A3C;border-radius:8px;padding:5px 8px;font:500 12px inherit;cursor:pointer;display:flex;align-items:center}.gc button .ic{width:14px;height:14px}.gc .tb.on{background:#1D1D1F;color:#fff}
.dirty .btn{box-shadow:0 0 0 3px rgba(0,113,227,.25)}
.tree{background:#fff;border-radius:20px;padding:20px 24px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}.root{display:flex;align-items:center;gap:10px;font-size:17px}.root .ic{width:22px;height:22px;color:#0071E3}
.eps{list-style:none;margin:12px 0 0 11px;padding:0 0 0 22px;border-left:2px solid #E5E5EA}.ep{position:relative;margin:10px 0}.ep::before{content:"";position:absolute;left:-22px;top:19px;width:18px;border-top:2px solid #E5E5EA}
.ep>details>summary{display:flex;align-items:center;gap:14px;list-style:none;cursor:pointer;background:#F5F5F7;border-radius:12px;padding:10px 14px;color:#1D1D1F;font-size:14px}.ep>details[open]>summary{background:#EAF3FE}.en{font-weight:600;min-width:220px}.eb{flex:1;min-width:80px}.eb .meter{margin:0}.ec{color:#6E6E73;font-size:12px;min-width:56px;text-align:right}
.eg{margin:8px 0 4px 18px;padding-left:16px;border-left:2px solid #E5E5EA}.tg2{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:#86868B;margin:10px 0 4px}.lv{list-style:none;margin:0;padding:0}.lf{display:flex;gap:8px;align-items:center;padding:5px 0;font-size:13px}.lf span:last-child{color:#3A3A3C}.dn summary{font-size:12px}
.flow{display:grid;gap:18px;margin-top:10px}.stage{background:#fff;border-radius:20px;padding:18px 20px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 0 0 .5px rgba(0,0,0,.05)}.stn{font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#6E6E73;margin-bottom:10px}
.stp{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}.step{background:#F5F5F7;border-radius:14px;padding:12px 14px}.step summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:28px 1fr;gap:2px 10px;align-items:center;color:#1D1D1F}.sn{grid-row:span 2;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600}.sname{font-weight:600;font-size:14px}.ssc{font-size:11px;color:#6E6E73}.step .meter{grid-column:1/3;margin:8px 0 2px}.sst{grid-column:1/3;font-size:12px;font-weight:600}.sd{margin-top:8px;font-size:13px}.sd ul{list-style:none;padding:0;margin:6px 0 0}.sd li{display:flex;gap:6px;align-items:baseline;flex-wrap:wrap}
.lstick{position:sticky;top:60px;z-index:15;background:rgba(245,245,247,.92);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);padding:6px 0 4px;margin:0 0 10px}.lstick .savebar{margin:0 0 6px}
.lj{display:flex;gap:6px;flex-wrap:wrap}.lj button{border:0;border-radius:999px;background:#fff;box-shadow:0 0 0 .5px rgba(0,0,0,.08);padding:6px 12px;font:600 13px inherit;color:#1D1D1F;cursor:pointer}.lj button i{font-style:normal;color:#6E6E73;font-weight:500;margin-left:3px}
.lane{scroll-margin-top:120px}.lane .lh{cursor:pointer}.lane .lh:after{content:"";margin-left:auto;width:8px;height:8px;border-right:2px solid #8E8E93;border-bottom:2px solid #8E8E93;transform:rotate(45deg);transition:transform .15s}.lane.col .lh:after{transform:rotate(-45deg)}.lane.col ul,.lane.col>.m{display:none}
"""
JS = """<script>(function(){if(window.labInit)return;var g=function(){return document.getElementById('gl')};
window.LABDIRTY=false;
function mark(){window.LABDIRTY=true;document.body.classList.add('dirty');var sv=document.getElementById('sv');if(sv)sv.textContent='Unsaved changes'}
function lab(){var G=g();if(!G)return;var st={};try{st=JSON.parse(localStorage.getItem('labCol')||'{}')}catch(x){}G.querySelectorAll('.lane').forEach(function(l){if(l.dataset.ci)return;l.dataset.ci=1;var k=l.dataset.tier;l.classList.toggle('col',(k in st)?st[k]:(k==='P2'||k==='Parked'))});var lj=document.getElementById('lj');if(lj)lj.querySelectorAll('button').forEach(function(b){var l=G.querySelector('.lane[data-tier="'+b.dataset.j+'"]');if(l)b.querySelector('i').textContent=l.querySelectorAll('li').length});G.querySelectorAll('.lane').forEach(function(l){l.querySelector('.lc').textContent=l.querySelectorAll('li').length;l.querySelectorAll('li').forEach(function(li){li.querySelectorAll('.tb').forEach(function(b){b.classList.toggle('on',b.dataset.t===l.dataset.tier)})})})}
window.labInit=lab;
function setCol(l,c){l.classList.toggle('col',c);var st={};try{st=JSON.parse(localStorage.getItem('labCol')||'{}')}catch(x){}st[l.dataset.tier]=c;try{localStorage.setItem('labCol',JSON.stringify(st))}catch(x){}}
document.addEventListener('click',function(ev){var t=ev.target;if(!t.closest)return;var j=t.closest('#lj button');if(j){var l=document.querySelector('#gl .lane[data-tier="'+j.dataset.j+'"]');if(l){if(l.classList.contains('col'))setCol(l,false);l.scrollIntoView({behavior:'smooth',block:'start'})}return}
var h=t.closest('#gl .lh');if(h&&!t.closest('button')){var l2=h.closest('.lane');setCol(l2,!l2.classList.contains('col'))}});
document.addEventListener('click',function(ev){var G=g();var b=ev.target.closest&&ev.target.closest('button');if(!b||!G)return;
if(b.id==='save'){var order=[],tiers={},sv=document.getElementById('sv');G.querySelectorAll('.lane').forEach(function(l){l.querySelectorAll('li').forEach(function(li){order.push(+li.dataset.n);tiers[li.dataset.n]=l.dataset.tier})});
fetch('/api/priorities',{method:'POST',headers:{'Content-Type':'application/json','X-Lab':'1'},body:JSON.stringify({order:order,tiers:tiers})}).then(function(r){return r.json()}).then(function(j){if(j.ok){window.LABDIRTY=false;document.body.classList.remove('dirty');sv.textContent='Saved. Agents pick up from the top of Now, then Next.'}else throw 0}).catch(function(){sv.textContent=location.protocol==='file:'?'Open this page at http://localhost:8787/ on this Mac (or the phone address) to save.':'Could not save. Is the dispatcher running?'});return}
var li=b.closest('li');if(!li||!G.contains(li))return;
if(b.dataset.a==='up'&&li.previousElementSibling)li.parentNode.insertBefore(li,li.previousElementSibling);
else if(b.dataset.a==='down'&&li.nextElementSibling)li.parentNode.insertBefore(li.nextElementSibling,li);
else if(b.dataset.t){G.querySelector('.lane[data-tier="'+b.dataset.t+'"] ul').appendChild(li)}else return;mark();lab()});
window.addEventListener('beforeunload',function(ev){if(window.LABDIRTY){ev.preventDefault();ev.returnValue=''}});lab()})();</script>"""
if __name__ == '__main__':
    page = ('<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Founder Lab</title><style>' + CSS + LABCSS
            + hl + '{background:#fff!important;box-shadow:0 1px 3px rgba(0,0,0,.14),0 0 0 .5px rgba(0,0,0,.04)!important;color:#1D1D1F!important}</style></head><body><div class=wrap><div class=top><div><div class=eyebrow>__PROJECT__ &middot; Lab (preview)</div><h1>Prioritise and plan</h1></div></div>'
            + '<nav class=bar>' + nav + '</nav><div class=stamp>Generated ' + datetime.datetime.now().strftime("%a %d %b, %I:%M %p") + '. Reload to refresh. This is a side preview; the Founder Status page is unchanged.</div>'
            + "".join(panes[k] for k in order) + '</div>' + JS + '</body></html>')
    tmp = os.path.join(D, "FounderLab.html.tmp"); open(tmp, "w").write(page); os.replace(tmp, os.path.join(D, "FounderLab.html"))
