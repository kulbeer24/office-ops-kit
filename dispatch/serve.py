#!/usr/bin/env python3
"""Private phone access to the founder page. Serves ONLY the allow-listed files below (no directory listing, nothing else in this folder),
and only on the Tailscale address of this Mac, so it is reachable from your own devices and nobody else. Started by loop.sh.
If Tailscale is not up yet it waits and retries. Address is written to dispatch/cache/serve.url."""
import http.server, json, os, shutil, socketserver, subprocess, sys, time
D = os.path.dirname(os.path.abspath(__file__)); PORT = int(os.environ.get("FOUNDER_PORT", "8787"))
ALLOW = {"/": ("FounderStatus.html", "text/html; charset=utf-8"), "/FounderStatus.html": ("FounderStatus.html", "text/html; charset=utf-8"),
         "/status.html": ("status.html", "text/html; charset=utf-8"), "/FounderLab.html": ("FounderStatus.html", "text/html; charset=utf-8"), "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
         "/FounderView3D.html": ("FounderView3D.html", "text/html; charset=utf-8"), "/icon-180.png": ("icon-180.png", "image/png"), "/icon-512.png": ("icon-512.png", "image/png")}
def ts_ip():
    if os.environ.get("TS_IP_OVERRIDE"): return os.environ["TS_IP_OVERRIDE"]
    for exe in (shutil.which("tailscale"), "/Applications/Tailscale.app/Contents/MacOS/Tailscale", "/usr/local/bin/tailscale", "/opt/homebrew/bin/tailscale"):
        if exe and os.path.exists(exe):
            try:
                out = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=8).stdout.split()
                if out: return out[0]
            except Exception: pass
    return None
# ---- development controls (used by the Operations tab) -------------------------------------------------------
import re, signal
def _procs():
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,stat=,command="], capture_output=True, text=True).stdout; rows = []
    for ln in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(.*)", ln)
        if m: rows.append((int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)))
    return rows
def _agents():
    rows = _procs(); by = {}
    for pid, ppid, stat, cmd in rows:
        m = re.search(r"AGENT-ID-([A-Za-z0-9-]+)\.", cmd)
        if m and not re.match(r"(pgrep|grep|ps|pkill)\b", cmd.split("/")[-1] if cmd.startswith("/") else cmd): by.setdefault(m.group(1), []).append((pid, stat))
    kids = {}
    for pid, ppid, stat, cmd in rows: kids.setdefault(ppid, []).append(pid)
    out = {}
    for a, lst in by.items():
        pids = {p for p, _ in lst}; todo = list(pids)
        while todo:
            for c in kids.get(todo.pop(), []):
                if c not in pids: pids.add(c); todo.append(c)
        out[a] = {"pids": sorted(pids), "stopped": any(st.startswith("T") for _, st in lst)}
    return out
def _sig(a, sig):
    n = 0
    for p in _agents().get(a, {}).get("pids", []):
        try: os.kill(p, sig); n += 1
        except Exception: pass
    return n
def _flag(name, on):
    f = os.path.join(D, name)
    if on: open(f, "a").close()
    else:
        try: os.remove(f)
        except FileNotFoundError: pass
def _note(t):
    try: open(os.path.join(D, "status.md"), "a").write(f"- {t} {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
    except Exception: pass
def _alive(lock):
    try: p = int(open(os.path.join(D, "locks", lock)).read().strip()); os.kill(p, 0); return True
    except Exception: return False
def _age(rel):
    try: return int(time.time() - os.path.getmtime(os.path.join(D, rel)))
    except Exception: return None
def review_state():
    return {"architect": {"running": _alive("architect.pid"), "last_age": _age("cache/architect.run")}, "orchestrator": {"running": _alive("orch.pid"), "last_age": _age("cache/orch.run")}}
def _spawn(*cmd):
    subprocess.Popen(list(cmd), cwd=os.path.dirname(D), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
def control_state():
    ag = _agents()
    return {"review": review_state(), "paused": os.path.exists(os.path.join(D, "PAUSED")), "limit": os.path.exists(os.path.join(D, "LIMIT_HIT")), "agents": [{"id": a, "stopped": v["stopped"]} for a, v in sorted(ag.items())]}
def control(action, agent=None):
    if action == "pause":
        _flag("PAUSED", True)
        for a in _agents(): _sig(a, signal.SIGSTOP)
        _note("dev PAUSED from the Founder view (running agents frozen)")
    elif action == "start":
        _pt = os.path.getmtime(os.path.join(D, "PAUSED")) if os.path.exists(os.path.join(D, "PAUSED")) else None
        _flag("PAUSED", False); _flag("pause_at", False)
        for a in _agents():
            _sig(a, signal.SIGCONT)
            if _pt:   # frozen time is not run time: push the start marker forward so "running for Xh" excludes the pause
                try: _m = os.path.join(D, "started", a); _t = os.path.getmtime(_m); os.utime(_m, (time.time(), min(time.time(), _t + max(0, time.time() - max(_pt, _t)))))
                except Exception: pass
        _note("dev STARTED from the Founder view")
    elif action == "stopall":
        _flag("PAUSED", True)
        for a in _agents(): _sig(a, signal.SIGCONT); _sig(a, signal.SIGTERM)
        _note("dev STOPPED from the Founder view (all running agents ended; they restart when you press Start)")
    elif action == "review_architect":
        if not _alive("architect.pid"): _spawn("bash", "dispatch/architect.sh", "force"); _note("architect review FORCED from a dashboard")
    elif action == "review_orchestrator":
        if not _alive("orch.pid"): _spawn("bash", "dispatch/orchestrator_review.sh"); _note("orchestrator ad-hoc review FORCED from a dashboard")
    elif action in ("agent_pause", "agent_start") and agent and re.fullmatch(r"[A-Za-z0-9-]+", agent) and agent in _agents():
        _sig(agent, signal.SIGSTOP if action == "agent_pause" else signal.SIGCONT); _note(f"agent {agent} {'paused' if action == 'agent_pause' else 'started'} from the Founder view")
    else: raise ValueError("bad action")
    return control_state()
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = self.path.split("?")[0].split("#")[0]
        if p == "/api/control": return self._json(200, control_state())
        if p == "/api/priorities":
            try: return self._json(200, json.load(open(os.path.join(D, "priorities.json"))))
            except Exception: return self._json(200, {})
        hit = ALLOW.get(p) or next((v for k, v in ALLOW.items() if k.lower() == p.lower()), None)   # phones lower-case what you type
        f = os.path.join(D, hit[0]) if hit else None
        if not f or not os.path.isfile(f): self.send_response(404); self.end_headers(); self.wfile.write(b"not found"); return
        b = open(f, "rb").read(); self.send_response(200); self.send_header("Content-Type", hit[1]); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
    do_HEAD = do_GET
    def _json(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        # The grooming tab saves the priority list here. A custom header is required, so other websites cannot post to this address from a browser.
        if self.path.split("?")[0] == "/api/control" and self.headers.get("X-Lab") == "1":
            try:
                n = int(self.headers.get("Content-Length", "0")); d = json.loads(self.rfile.read(n)) if 0 < n < 2000 else {}
                st = control(d.get("action", ""), d.get("agent")); return self._json(200, {"ok": True, **st})
            except Exception: return self._json(400, {"ok": False, "error": "bad request"})
        if self.path.split("?")[0] != "/api/priorities" or self.headers.get("X-Lab") != "1": return self._json(404, {"ok": False})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > 200000: raise ValueError("size")
            d = json.loads(self.rfile.read(n)); order = [int(x) for x in d["order"]]; tiers = {str(int(k)): v for k, v in d["tiers"].items()}
            if any(v not in ("P0", "P1", "P2", "Parked") for v in tiers.values()): raise ValueError("tier")
        except Exception: return self._json(400, {"ok": False, "error": "bad request"})
        out = {"order": order, "tiers": tiers, "saved": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        tmp = os.path.join(D, "priorities.json.tmp"); open(tmp, "w").write(json.dumps(out)); os.replace(tmp, os.path.join(D, "priorities.json"))
        return self._json(200, {"ok": True, "saved": out["saved"]})
class S(http.server.ThreadingHTTPServer): daemon_threads = True; allow_reuse_address = True
import threading
os.makedirs(os.path.join(D, "cache"), exist_ok=True)
# 1) this Mac, always: http://localhost:PORT/ (works without Tailscale, so saving from the laptop never depends on it)
try: local = S(("127.0.0.1", PORT), H)
except OSError as ex: print("could not start:", ex, flush=True); sys.exit(1)
threading.Thread(target=local.serve_forever, daemon=True).start()
open(os.path.join(D, "cache", "serve.local"), "w").write(f"http://localhost:{PORT}/")
print("laptop address http://localhost:%d/" % PORT, flush=True)
# 2) phone: only on the Tailscale address, started as soon as Tailscale is up
while True:
    ip = ts_ip()
    if ip: break
    time.sleep(15)
try: srv = S((ip, PORT), H)
except OSError as ex: print("tailscale bind failed:", ex, flush=True); time.sleep(10**6); sys.exit(1)
open(os.path.join(D, "cache", "serve.url"), "w").write(f"http://{ip}:{PORT}/")
print("phone address", f"http://{ip}:{PORT}/", flush=True); srv.serve_forever()
