#!/bin/bash
# The dispatcher loop. Starts by itself at login (see "Start Dispatcher.command" and install_autostart.sh); you never type it again.
# Dev ON  = dispatch/PAUSED does not exist.  Dev OFF = dispatch/PAUSED exists (the architect creates/removes it when we agree).
# dispatch/STOP (file) ends this loop for good. Only one copy runs at a time; a second copy exits quietly.
cd "$(dirname "$0")/.." || exit 1
mkdir -p dispatch/locks dispatch/cache
L=dispatch/locks/loop.lock
if ! mkdir "$L" 2>/dev/null; then
  op=$(cat "$L/pid" 2>/dev/null)
  if [ -n "$op" ] && kill -0 "$op" 2>/dev/null; then echo "Dispatcher already running (pid $op)."; exit 0; fi
  rm -rf "$L"; mkdir "$L" || exit 1
fi
echo $$ > "$L/pid"; SRV=""; trap 'rm -rf "$L"; [ -n "$SRV" ] && kill "$SRV" 2>/dev/null' EXIT
rm -f dispatch/STOP
# private phone access over Tailscale (serves only the founder page); waits quietly until Tailscale is up
mkdir -p dispatch/logs
if ! pgrep -f "dispatch/serve.py" >/dev/null; then python3 dispatch/serve.py >> dispatch/logs/serve.log 2>&1 & SRV=$!; fi
echo "Dispatcher running (pid $$). Dev is ON unless dispatch/PAUSED exists. You can minimise this window."
while true; do
  [ -f dispatch/STOP ] && { echo "STOP file found, ending."; break; }
  date +%s > dispatch/cache/loop.beat
  # keep the Mac awake only while dev is ON
  [ -f dispatch/PAUSED ] || { command -v caffeinate >/dev/null 2>&1 && caffeinate -i -t 60 >/dev/null 2>&1 & }
  # watchdog: a hung gh/osascript/network call used to freeze the whole loop; kill this pass after 10 min and carry on with the next one
  perl -e 'alarm 600; exec @ARGV' bash ./dispatch/run_batch.sh || echo "- run_batch pass ended abnormally (exit $?, maybe a hung call) $(date -u +%FT%TZ)" >> dispatch/status.md
  sleep 20
done
