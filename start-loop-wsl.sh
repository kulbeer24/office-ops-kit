#!/bin/bash
# Starts the dispatcher loop for the project this kit was set up for (used by the Windows logon task, and handy on Linux). Stays in the foreground.
K="$(cd "$(dirname "$0")" && pwd)"; PD="$(cat "$K/.project-dir" 2>/dev/null)"
[ -d "$PD/dispatch" ] || { echo "Not set up yet: run Finish Setup first."; exit 1; }
cd "$PD" && exec bash dispatch/loop.sh
