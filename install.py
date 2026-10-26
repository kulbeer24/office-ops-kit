#!/usr/bin/env python3
"""Agent Ops Kit installer. Two halves so Cowork and the computer can each do what they can:
  python3 install.py --prepare --project-dir <repo> --repo owner/name [--city "Sydney"] [--test-cmd "..."]   copies + configures files (no internet needed except the optional city lookup). Cowork can run this.
  python3 install.py --activate --project-dir <repo>   runs on the real computer: checks tools, GitHub login, downloads three.js, installs auto-start, starts the dispatcher.
  python3 install.py --all  (default) = prepare then activate. Safe to re-run: it upgrades scripts and never overwrites your data files."""
import argparse, json, os, platform, re, shutil, subprocess, sys, time, urllib.request, urllib.parse
KIT = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.join(KIT, "dispatch")
TEXT = (".sh", ".py", ".md", ".html", ".txt", ".json", ".conf", ".example", ".template")
DATA = {"batch.txt", "priorities.json", "owner_hold.txt", "owner_tasks.txt", "targets.txt", "release.txt", "success.txt", "ship.txt", "last_build.txt", "optimisations.txt",
        "roadmap.txt", "journey.txt", "marketing.txt", "estimates.txt", "summary.txt", "pipeline.txt", "wip.conf", "automerge.conf", "local.conf", "push.conf", "ops.conf"}
def run(cmd, **k):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=k.pop("timeout", 60), **k)
    except Exception as ex: return subprocess.CompletedProcess(cmd, 1, "", str(ex))
def sys_tz():
    try:
        p = os.path.realpath("/etc/localtime"); m = re.search(r"zoneinfo/(.+)$", p)
        if m: return m.group(1)
    except OSError: pass
    return os.environ.get("TZ", "UTC")
def geocode(city):
    try:
        u = "https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(city)
        r = json.load(urllib.request.urlopen(u, timeout=10))["results"][0]
        return r["latitude"], r["longitude"], r.get("timezone") or sys_tz(), r["name"]
    except Exception: return None
def prepare(a):
    proj = os.path.abspath(a.project_dir)
    if not os.path.isdir(os.path.join(proj, ".git")): sys.exit("ERROR: %s is not a git repository (clone your project first)." % proj)
    repo = a.repo
    if not repo:
        u = run(["git", "-C", proj, "remote", "get-url", "origin"]).stdout.strip(); m = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", u)
        repo = m.group(1) if m else sys.exit("ERROR: could not work out the GitHub repo. Pass --repo owner/name.")
    name = repo.split("/")[1]; slug = re.sub(r"[^a-z0-9-]", "-", name.lower()); project = a.project_name or re.sub(r"[-_]+", " ", name).title()
    city = a.city or ""; geo = geocode(city) if city else None
    lat, lon, tz, cityname = (geo if geo else (0, 0, sys_tz(), city or tz_city(sys_tz())))
    tok = {"__REPO__": repo, "__SLUG__": slug, "__PROJECT__": project, "__PROJECT_DIR__": proj, "__TZ__": tz, "__TZ_URL__": urllib.parse.quote(tz, safe=""), "__LAT__": str(lat), "__LON__": str(lon), "__CITY__": cityname}
    dst = os.path.join(proj, "dispatch"); os.makedirs(dst, exist_ok=True); n_new = n_up = 0
    for root, _, files in os.walk(SRC):
        for f in files:
            s = os.path.join(root, f); rel = os.path.relpath(s, SRC); d = os.path.join(dst, rel); os.makedirs(os.path.dirname(d), exist_ok=True)
            if rel in DATA and os.path.exists(d): continue          # never overwrite the user's data
            if f.endswith(TEXT):
                t = open(s, encoding="utf-8").read()
                for k, v in tok.items(): t = t.replace(k, v)
                open(d, "w", encoding="utf-8").write(t)
            else: shutil.copy2(s, d)
            if f.endswith((".sh", ".command")) or rel.startswith("tests"): os.chmod(d, 0o755)
            n_new += 1
    for d in ("started", "done", "requeue", "retries", "logs", "cache", "locks", "alerts", "fixes", "inbox", "exits", "vendor"): os.makedirs(os.path.join(dst, d), exist_ok=True)
    conf = os.path.join(dst, "ops.conf")
    if not os.path.exists(conf):
        open(conf, "w").write("# Agent Ops settings (edit freely; read every cycle)\nrepo=%s\nproject=%s\ntest_cmd=%s\nmodel=sonnet\n# headless = agents run in the background (works everywhere). terminal = one Terminal window per agent (macOS only)\nlaunch_mode=headless\n" % (repo, project, a.test_cmd or "run the project test suite described in CLAUDE.md"))
    open(os.path.join(dst, "claude_status.settings.json"), "w").write(json.dumps({"statusLine": {"type": "command", "command": os.path.join(dst, "statusline.sh")}}))
    ex = os.path.join(proj, ".git", "info", "exclude"); cur = open(ex).read() if os.path.exists(ex) else ""
    if "dispatch/" not in cur: open(ex, "a").write("\n# Agent Ops Kit (local only, never committed)\ndispatch/\n")
    cm = os.path.join(proj, "CLAUDE.md")
    if not os.path.exists(cm) and os.path.exists(os.path.join(KIT, "CLAUDE.md.template")):
        t = open(os.path.join(KIT, "CLAUDE.md.template"), encoding="utf-8").read()
        for k, v in tok.items(): t = t.replace(k, v)
        open(cm, "w", encoding="utf-8").write(t); print("Created CLAUDE.md (agents read it first). Edit the test command and rules, then commit it.")
    open(os.path.join(KIT, ".project-dir"), "w").write(proj)
    print("prepared %s (%d files) for %s; city=%s tz=%s" % (dst, n_new, repo, cityname, tz))
def tz_city(tz): return tz.split("/")[-1].replace("_", " ") if tz and "/" in tz else "Home"
def need(cmd, hint):
    ok = shutil.which(cmd) is not None; print(("  ok   " if ok else "  MISSING ") + cmd + ("" if ok else "  -> " + hint)); return ok
def activate(a):
    proj = os.path.abspath(a.project_dir); dst = os.path.join(proj, "dispatch"); me = platform.system(); wsl = "microsoft" in platform.release().lower()
    if not os.path.isdir(dst): sys.exit("Run --prepare first (dispatch/ not found in %s)." % proj)
    open(os.path.join(dst, "claude_status.settings.json"), "w").write(json.dumps({"statusLine": {"type": "command", "command": os.path.join(dst, "statusline.sh")}}))
    print("Checking tools:"); ok = True
    for c, h in (("git", "install Git"), ("gh", "install the GitHub CLI: https://cli.github.com (Mac: brew install gh)"), ("claude", "install Claude Code: https://docs.claude.com/en/docs/claude-code/setup"), ("perl", "install perl")): ok &= need(c, h)
    if not ok: sys.exit("Install the missing tools, then run this again.")
    if run(["gh", "auth", "status"]).returncode != 0:
        print("Logging in to GitHub (a browser window opens)..."); subprocess.call(["gh", "auth", "login", "-w", "-s", "repo,workflow,project"])
    if run(["gh", "auth", "status"]).returncode != 0: sys.exit("GitHub login did not complete. Run: gh auth login")
    print("GitHub: logged in.")
    print("Claude Code: if this is the first time on this computer, open a Terminal, type `claude`, and sign in once; then come back.")
    v = os.path.join(dst, "vendor", "three.min.js")
    if not os.path.exists(v) or os.path.getsize(v) < 100000:
        try: urllib.request.urlretrieve("https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js", v); print("Downloaded three.js for the 3D view.")
        except Exception as ex: print("WARNING: could not download three.js (%s). The 3D view needs dispatch/vendor/three.min.js." % ex)
    for f in os.listdir(dst):
        if f.endswith(".sh"): os.chmod(os.path.join(dst, f), 0o755)
    run(["python3", os.path.join(dst, "freshness.py")]); run(["python3", os.path.join(dst, "founder.py")]); run(["python3", os.path.join(dst, "founder3d.py")]); run(["python3", os.path.join(dst, "dashboard.py")]); run(["python3", os.path.join(dst, "inject_review.py")])
    slug = re.sub(r"[^a-z0-9]+", "-", os.path.basename(proj).lower()); loop = os.path.join(dst, "loop.sh")
    if me == "Darwin":
        la = os.path.expanduser("~/Library/LaunchAgents"); os.makedirs(la, exist_ok=True); pl = os.path.join(la, "com.agentops.%s.plist" % slug)
        path = ":".join([os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"] + [os.path.dirname(shutil.which(c)) for c in ("gh", "claude", "node") if shutil.which(c)])
        open(pl, "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>\n<key>Label</key><string>com.agentops.%s</string>\n<key>ProgramArguments</key><array><string>/bin/bash</string><string>%s</string></array>\n<key>WorkingDirectory</key><string>%s</string>\n<key>EnvironmentVariables</key><dict><key>PATH</key><string>%s</string></dict>\n<key>RunAtLoad</key><true/>\n<key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>\n<key>StandardOutPath</key><string>%s</string><key>StandardErrorPath</key><string>%s</string>\n</dict></plist>\n' % (slug, loop, proj, path, os.path.join(dst, "logs", "loop.out"), os.path.join(dst, "logs", "loop.out")))
        uid = str(os.getuid()); run(["launchctl", "bootout", "gui/" + uid, pl]); r = run(["launchctl", "bootstrap", "gui/" + uid, pl])
        print("Auto-start installed (starts at every login)." if r.returncode == 0 else "Auto-start install said: " + r.stderr.strip())
    elif shutil.which("systemctl") and run(["systemctl", "--user", "status"]).returncode in (0, 3):
        ud = os.path.expanduser("~/.config/systemd/user"); os.makedirs(ud, exist_ok=True)
        open(os.path.join(ud, "agentops-%s.service" % slug), "w").write("[Unit]\nDescription=Agent Ops loop (%s)\n[Service]\nWorkingDirectory=%s\nExecStart=/bin/bash %s\nRestart=on-failure\nEnvironment=PATH=%s\n[Install]\nWantedBy=default.target\n" % (slug, proj, loop, os.environ.get("PATH", "")))
        run(["systemctl", "--user", "daemon-reload"]); run(["systemctl", "--user", "enable", "--now", "agentops-%s.service" % slug]); print("Auto-start installed (systemd user service).")
    else:
        cur = run(["crontab", "-l"]).stdout
        if loop not in cur: subprocess.run(["crontab", "-"], input=cur + "@reboot cd %s && nohup /bin/bash %s >> %s/logs/loop.out 2>&1 &\n" % (proj, loop, dst), text=True)
        subprocess.Popen(["nohup", "/bin/bash", loop], cwd=proj, stdout=open(os.path.join(dst, "logs", "loop.out"), "a"), stderr=subprocess.STDOUT, start_new_session=True); print("Started (cron @reboot added)." + (" On Windows the .bat adds a logon task so WSL starts it at login." if wsl else ""))
    beat = os.path.join(dst, "cache", "loop.beat"); t0 = time.time()
    while time.time() - t0 < 60 and not (os.path.exists(beat) and time.time() - os.path.getmtime(beat) < 60): time.sleep(2)
    print("\nDispatcher is %s." % ("RUNNING" if os.path.exists(beat) and time.time() - os.path.getmtime(beat) < 90 else "NOT confirmed yet; check dispatch/logs/loop.out"))
    print("Open the views (the dispatcher serves them on this computer):\n  Founder view  http://localhost:8787/\n  Status view   http://localhost:8787/status.html\n  3D office     http://localhost:8787/FounderView3D.html\nPause/resume: the Start/Pause buttons on the Founder view.")
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--project-dir", default=None); ap.add_argument("--repo"); ap.add_argument("--city"); ap.add_argument("--project-name"); ap.add_argument("--test-cmd")
    ap.add_argument("--prepare", action="store_true"); ap.add_argument("--activate", action="store_true"); ap.add_argument("--all", action="store_true"); a = ap.parse_args()
    pd = os.path.join(KIT, ".project-dir")
    if not a.project_dir: a.project_dir = open(pd).read().strip() if os.path.exists(pd) else os.getcwd()
    if a.prepare or not a.activate: prepare(a)
    if a.activate or not a.prepare: activate(a)
if __name__ == "__main__": main()
