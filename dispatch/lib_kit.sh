#!/bin/bash
# Kit helpers shared by run_batch.sh and agent.sh: config, portable notifications, headless agent launch. Source after setting REPO_DIR.
# ocfg <key> [default]: reads dispatch/ops.conf (key=value lines, # comments).
ocfg() { local v; v=$(grep -E "^$1=" "$REPO_DIR/dispatch/ops.conf" 2>/dev/null | head -1 | cut -d= -f2-); echo "${v:-$2}"; }
# notify_user <title> <message>: desktop notification where the OS offers one; silent no-op otherwise.
notify_user() {
  local t="${1//\"/}" m="${2//\"/}"
  if command -v osascript >/dev/null 2>&1; then osascript -e "display notification \"$m\" with title \"$t\"" >/dev/null 2>&1
  elif command -v notify-send >/dev/null 2>&1; then notify-send "$t" "$m" >/dev/null 2>&1
  elif command -v powershell.exe >/dev/null 2>&1; then powershell.exe -NoProfile -Command "[void][reflection.assembly]::LoadWithPartialName('System.Windows.Forms');\$n=New-Object System.Windows.Forms.NotifyIcon;\$n.Icon=[System.Drawing.SystemIcons]::Information;\$n.Visible=\$true;\$n.ShowBalloonTip(5000,'$t','$m','Info')" >/dev/null 2>&1; fi
  return 0
}
# launch_agent <name> <local-only-flag>: starts agent.sh for one job. Default is headless (no window, works on Mac, Linux and WSL).
# launch_mode=terminal (macOS only) opens a Terminal window per agent instead, so you can watch it.
launch_agent() {
  local N="$1" EXTRA="${2:-0}" LOG="$REPO_DIR/dispatch/logs/$1.term.log"
  if [ "$(ocfg launch_mode headless)" = terminal ] && command -v osascript >/dev/null 2>&1; then
    osascript -e "tell application \"Terminal\" to do script \"script -q '$LOG' env LOCAL_ONLY=$EXTRA HEADLESS=0 '$REPO_DIR/dispatch/agent.sh' $N; exit\"" >/dev/null 2>&1
  else
    nohup env LOCAL_ONLY="$EXTRA" HEADLESS=1 bash "$REPO_DIR/dispatch/agent.sh" "$N" >"$LOG" 2>&1 </dev/null &
  fi
}
# run_claude <prompt> [claude flags...]: interactive in terminal mode, print mode (-p) when headless. Prompt first: the tool lists are variadic.
run_claude() {
  local P="$1"; shift
  if [ "${HEADLESS:-1}" = 1 ]; then claude -p "$P" "$@"; else claude "$P" "$@"; fi
}
