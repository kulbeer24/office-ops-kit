"""Usage meter. The Pro plan has a rolling 5-hour session limit and a weekly limit. Claude does not expose either number to us, so this ESTIMATES them:
agent token use comes from metrics/tokens_cache.json (written by metrics.py), and the session cap is calibrated from the times the limit was actually hit
(dispatch/alerts/sent/*-limit.txt). It is an estimate, labelled as one. No network, no tokens."""
import os, json, time, datetime, statistics, html, glob, re
D = os.path.dirname(os.path.abspath(__file__)); e = html.escape
def compute(now=None):
    now = now or time.time(); runs = []
    try:
        for k, v in json.load(open(os.path.join(D, "metrics", "tokens_cache.json"))).items():
            try: runs.append((int(k.split("|")[1]), float(v.get("new", 0))))
            except Exception: pass
    except Exception: pass
    ev = []
    for f in glob.glob(os.path.join(D, "alerts", "sent", "*-limit*.txt")):
        m = re.match(r"(\d{8}T\d{6})", os.path.basename(f))
        if m:
            try: ev.append(datetime.datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=datetime.timezone.utc).timestamp())
            except Exception: pass
    def win(t, secs): return sum(n for t0, n in runs if t - secs < t0 <= t)
    caps = [c for c in (win(t, 5 * 3600) for t in ev) if c > 0]
    cap5 = statistics.median(caps) if caps else None
    cur5 = win(now, 5 * 3600); wk = win(now, 7 * 86400)
    days = []
    for k in range(6, -1, -1):
        d0 = datetime.datetime.fromtimestamp(now - k * 86400).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        days.append((datetime.datetime.fromtimestamp(d0).strftime("%a"), sum(n for t0, n in runs if d0 <= t0 < d0 + 86400)))
    old = [t0 for t0, n in runs if now - 5 * 3600 < t0 <= now]
    relief = (min(old) + 5 * 3600) if old else None
    return dict(cur5=cur5, cap5=cap5, pct=(cur5 / cap5 if cap5 else None), wk=wk, days=days, relief=relief, hits=len(ev))
def real(now=None):
    """Exact plan usage written by statusline.sh (Claude Code's own rate_limits numbers). None until an agent has run with the status line."""
    now = now or time.time()
    try: j = json.load(open(os.path.join(D, "cache", "claude_usage.json")))
    except Exception: return None
    f, w = j.get("five_hour") or {}, j.get("seven_day") or {}
    out = dict(ts=j.get("ts", 0), age=now - j.get("ts", 0), src=j.get("source", ""))
    for k, x in (("s", f), ("w", w)):
        pct, rs = x.get("pct"), x.get("resets")
        if rs and rs < now: pct, rs = 0, None            # that window has already reset
        out[k + "pct"], out[k + "resets"] = pct, rs
    if out.get("wpct") and out.get("wresets"):
        el = 1 - (out["wresets"] - now) / (7 * 86400.0)
        if el > 0.02 and out["wpct"] > 0:
            start = out["wresets"] - 7 * 86400; rate = out["wpct"] / (now - start)       # percent per second so far
            t100 = now + (100 - out["wpct"]) / rate if rate > 0 else None
            out["wrun_out"] = t100 if t100 and t100 < out["wresets"] - 7200 else None   # only if it runs out 2+ hours early
    return out
def html_block(now=None):
    now = now or time.time(); r = real(now)
    if r and r["age"] < 6 * 3600:
        tfmt = lambda t: datetime.datetime.fromtimestamp(t).strftime("%a %I:%M %p").replace(" 0", " ")
        def gauge(label, pct, rs):
            if pct is None: return ""
            p = min(100, round(pct)); col = "#FF3B30" if p >= 90 else "#FF9500" if p >= 70 else "#34C759"
            return '<div class=ug><div class=ugt><b>%s</b> <span>%d%% used%s</span></div><div class=ugb><i style="width:%d%%;background:%s"></i></div></div>' % (label, p, (" &middot; resets " + tfmt(rs)) if rs else "", p, col)
        warn = ""
        if r.get("wrun_out"): warn = '<div class=ugw>At this pace the weekly limit runs out around %s, before it resets.</div>' % tfmt(r["wrun_out"])
        ag = int(r["age"] // 60)
        body = gauge("Current session (5 hours)", r["spct"], r["sresets"]) + gauge("This week", r["wpct"], r["wresets"]) + warn
        note = "Exact figures from Claude (the same as Settings > Usage), %s." % ("updated just now" if ag < 2 else "last updated %d min ago by the running agents" % ag if ag < 90 else "last updated %.1f h ago; it refreshes whenever an agent is working" % (r["age"] / 3600))
        mode = "exact"
    else:
        body = ""; mode = "est"; note = "No exact numbers yet: they appear as soon as an agent starts (the agents report Claude's own usage figures). The bars below are an estimate."
    return _card(body, mode, note, now)
def _card(body, mode, note, now):
    u = compute(now); mx = max([v for d, v in u["days"]] + [1])
    fm = lambda x: ("%.1fM" % (x / 1e6)) if x >= 1e6 else ("%dk" % round(x / 1e3))
    if mode == "exact": gauge = body; note = note
    elif u["pct"] is not None:
        p = min(100, round(100 * u["pct"])); col = "#FF3B30" if p >= 90 else "#FF9500" if p >= 70 else "#34C759"
        gauge = '<div class=ug><div class=ugb><i style="width:%d%%;background:%s"></i></div><div class=ugt><b>%d%%</b> of the usual 5-hour limit used (%s of about %s)</div></div>' % (p, col, p, fm(u["cur5"]), fm(u["cap5"]))
        rel = (" Oldest work in the window ages out around %s." % datetime.datetime.fromtimestamp(u["relief"]).strftime("%I:%M %p").lstrip("0")) if u["relief"] else ""
        note = "Estimated from the %d time%s the limit was hit.%s" % (u["hits"], "" if u["hits"] == 1 else "s", rel)
    else:
        gauge = '<div class=ugt><b>%s</b> used in the last 5 hours. The limit size is not known yet; it is learned the first time the limit is hit.</div>' % fm(u["cur5"]); note = ""
    bars = "".join('<div class=ud><i style="height:%dpx"></i><span>%s</span><em>%s</em></div>' % (max(2, round(46 * v / mx)), e(d), fm(v)) for d, v in u["days"])
    css = ("<style>.ub{background:#F5F5F7;border-radius:18px;padding:16px 20px;margin:14px 0}.ub h3{margin:0 0 8px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#6E6E73}.ugb{height:8px;border-radius:4px;background:#E5E5EA;overflow:hidden;margin:2px 0 6px}.ugb i{display:block;height:100%}"
           ".ugt{font-size:13.5px;margin-top:6px}.ugt span{color:#6E6E73}.ugw{margin-top:8px;font-size:13px;font-weight:600;color:#B42318}.udw{display:flex;gap:10px;align-items:flex-end;margin-top:12px;height:78px}.ud{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;font-size:11px;color:#6E6E73;width:44px}.ud i{display:block;width:100%;background:#0071E3;border-radius:4px 4px 0 0}.ud em{font-style:normal;font-size:10.5px}.ub .n{font-size:12px;color:#6E6E73;margin-top:8px}</style>")
    return css + '<div class=ub><h3>Claude usage%s</h3>' % ("" if mode == "exact" else " (estimate)") + gauge + '<div class=n style="margin-top:6px">%s</div><div class=udw>' % e(note) + bars + '</div><div class=n>Agent activity per day (tokens of new work), last 7 days: %s in total.</div></div>' % fm(u["wk"])
