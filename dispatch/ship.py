"""Release readiness for the next test build. Reads local caches only. Editable files: last_build.txt (when the last build went out) and ship.txt (manual checklist)."""
import os, json, time, datetime, html, re
D = os.path.dirname(os.path.abspath(__file__)); e = html.escape; R = "__REPO__"
def _jl(p, d):
    try: return json.load(open(os.path.join(D, p)))
    except Exception: return d
def _read(name, default):
    p = os.path.join(D, name)
    try:
        t = open(p).read()
        if t.strip(): return t
    except Exception: pass
    try: open(p, "w").write(default)
    except Exception: pass
    return default
LAST = "# when the last test build build went out (UTC) | build label. Edit this after each upload; the page counts merges since then.\n2026-10-20T13:00:00Z | build 2\n"
CHECK = "# manual steps for each build. Put [x] at the end when done; clear them after each upload.\nTest suite passes\nVersion bumped\nRelease built and uploaded\nRelease notes written\n"
def _ts(s):
    try: return datetime.datetime.fromisoformat(s.strip().replace("Z", "+00:00")).timestamp()
    except Exception: return None
def compute(now=None, merged_list=None, open_list=None):
    now = now or time.time()
    row = [l for l in _read("last_build.txt", LAST).splitlines() if l.strip() and not l.startswith("#")][:1]
    p = [x.strip() for x in row[0].split("|")] if row else ["", ""]
    since = _ts(p[0]) or now - 7 * 86400; label = p[1] if len(p) > 1 else "last build"
    src = merged_list if merged_list is not None else _jl("cache/prs_all.json", [])
    merged = sorted([dict(x, url=x.get("url") or "https://github.com/%s/pull/%s" % (R, x["number"])) for x in src if x.get("mergedAt") and (_ts(x["mergedAt"]) or 0) > since], key=lambda x: x["mergedAt"])
    openprs = open_list if open_list is not None else _jl("cache/prs.json", [])
    issues = _jl("cache/issues_live.json", []); pri = _jl("priorities.json", {}) or {}
    tiers = pri.get("tiers", {})
    p0 = [i for i in issues if i.get("state") == "OPEN" and tiers.get(str(i["number"])) == "P0" and "bug" in [(l["name"] if isinstance(l, dict) else l) for l in i.get("labels", [])]]
    running = [n for n in os.listdir(os.path.join(D, "started")) if " " not in n and not os.path.exists(os.path.join(D, "done", n))] if os.path.isdir(os.path.join(D, "started")) else []
    why = []
    if not merged: why.append("nothing new has merged since " + label)
    if openprs: why.append("%d PR%s still in review or QA" % (len(openprs), "" if len(openprs) == 1 else "s"))
    if p0: why.append("%d open P0 bug%s" % (len(p0), "" if len(p0) == 1 else "s"))
    if running: why.append("%d agent%s still working" % (len(running), "" if len(running) == 1 else "s"))
    ready = not why
    chk = []
    for l in _read("ship.txt", CHECK).splitlines():
        if l.strip() and not l.startswith("#"): chk.append((l.rstrip().endswith("[x]"), l.replace("[x]", "").strip()))
    return dict(label=label, merged=merged, openprs=openprs, p0=p0, running=running, why=why, ready=ready, check=chk)
def verdict(s):
    if s["ready"]: return "Good time to ship: %d merged since %s and nothing in review." % (len(s["merged"]), s["label"])
    return "Not yet: " + "; ".join(s["why"]) + "."
def html_block(s=None):
    s = s or compute(); col = ("#1F8A3B", "#E8F8EE") if s["ready"] else ("#B35C00", "#FFF3E0")
    mer = "".join('<li><a href="%s">#%d</a> %s</li>' % (e(x.get("url", "")), x["number"], e(re.sub(r"^(feat|fix|chore|docs|test)(\([^)]*\))?: ", "", x["title"])[:80])) for x in reversed(s["merged"][-8:])) or "<li>None yet.</li>"
    chk = "".join('<li class="%s">%s</li>' % ("ok" if ok else "", e(t)) for ok, t in s["check"])
    return ('<div class=lc-card style="margin-bottom:12px"><h3>Next test build</h3><span class=lc-pill style="background:%s;color:%s"><i style="background:%s"></i>%s</span>'
            '<div class=lc-two style="margin-top:12px"><div><div class=m>Merged since %s (%d)</div><ul>%s</ul></div><div><div class=m>Before you upload</div><ul class=lc-gl>%s</ul><div class=m style="margin-top:6px">Edit dispatch/ship.txt and last_build.txt after each upload.</div></div></div></div>'
            % (col[1], col[0], col[0], e(verdict(s)), e(s["label"]), len(s["merged"]), mer, chk))
