#!/bin/bash
# Claude Code status line for dispatcher agents. Zero tokens: it only reads the JSON Claude Code already hands it and saves the real plan-usage numbers
# (the same ones as Settings > Usage) to dispatch/cache/claude_usage.json, so the Founder view shows exact figures instead of an estimate.
D="$(cd "$(dirname "$0")" && pwd)"
python3 - "$D" <<'PY'
import sys, json, os, time
D = sys.argv[1]
try: j = json.load(sys.stdin)
except Exception: j = {}
r = (j.get("rate_limits") or {})
def g(k):
    x = r.get(k) or {}
    return {"pct": x.get("used_percentage"), "resets": x.get("resets_at")} if x else None
out = {"ts": int(time.time()), "five_hour": g("five_hour"), "seven_day": g("seven_day"), "source": "claude-code"}
if out["five_hour"] or out["seven_day"]:
    try:
        p = os.path.join(D, "cache", "claude_usage.json"); t = p + ".tmp"; open(t, "w").write(json.dumps(out)); os.replace(t, p)
    except Exception: pass
f, s = out["five_hour"], out["seven_day"]
print("5h %s%% | wk %s%%" % (round(f["pct"]) if f and f.get("pct") is not None else "?", round(s["pct"]) if s and s.get("pct") is not None else "?"))
PY
