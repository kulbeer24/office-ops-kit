"""Shared 'needs attention' banner for status.html and FounderStatus.html. Reads cache/health.json (written by health.py every cycle).
The data-age text is updated by the browser, so if the dispatcher stops, the page turns red by itself instead of quietly showing old numbers."""
import json, os, html, time
D = os.path.dirname(os.path.abspath(__file__)); e = html.escape
CSS = ("<style>.at{border:1px solid #E5E5EA;border-radius:14px;background:#fff;padding:10px 14px;margin:10px 0;font-size:13px;line-height:1.45}"
       ".at-top{display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;color:#3A3A3C}.at-fresh{font-weight:600}.at-stale{color:#B42318}"
       ".at.stale{border-color:#F1B5AE;background:#FEF3F2}.at ul{margin:6px 0 0;padding-left:18px}.at li{margin:2px 0}"
       ".at li.crit{color:#B42318;font-weight:600}.at li.warn{color:#8A5A00}.at li.info{color:#6B7280}.at a{color:inherit;text-decoration:underline}</style>")
JS = ("<script>(function(){if(window.__atTick)return;window.__atTick=1;function t(){var n=Math.floor(Date.now()/1000);"
      "document.querySelectorAll('.at-fresh').forEach(function(el){var ts=+el.getAttribute('data-ts'),a=n-ts,box=el.closest('.at');"
      "var s=a<90?a+'s':(a<5400?Math.round(a/60)+'m':(a/3600).toFixed(1)+'h');"
      "if(a>180){el.textContent='Data is '+s+' old. The dispatcher may have stopped; restart it.';el.classList.add('at-stale');if(box)box.classList.add('stale')}"
      "else{el.textContent='Data is '+s+' old';el.classList.remove('at-stale');if(box)box.classList.remove('stale')}})}t();setInterval(t,5000)})();</script>")
def clip(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0].rstrip(",.;:- ") + "…"
def banner():
    try: h = json.load(open(os.path.join(D, "cache", "health.json")))
    except Exception: h = None
    ts = int(h["ts"]) if h else int(time.time()); c = (h or {}).get("counts", {}); items = (h or {}).get("items", [])
    def nm(n): return ("#" + n) if str(n).isdigit() else str(n)
    run = ", ".join(nm(n) for n in c.get("running", [])) or "none"
    nxt = ("Next up: %s (%s)" % (nm(c["next"]), e(c.get("next_why", "")))) if c.get("next") else "Nothing waiting"
    top = ("<span class=at-fresh data-ts=%d>Data is fresh</span><span>Running %d of 3: %s</span><span>%s</span><span>Open PRs %s</span><span>%s</span>"
           % (ts, c.get("slots", 0), e(run), nxt, c.get("open_prs", "?"), "Dev paused" if c.get("paused") else "Dev on"))
    lis = "".join("<li class=%s>%s%s</li>" % (i["sev"], e(i["text"]), (' <a href="%s">Open</a>' % e(i["link"])) if i.get("link") else "") for i in items)
    return CSS + "<div class=at><div class=at-top>" + top + "</div>" + ("<ul>" + lis + "</ul>" if lis else "") + "</div>"
