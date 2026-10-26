#!/bin/bash
# push.sh "Title" "Message" [alert-file-name]   Sends a phone push if dispatch/push.conf says so. Silent no-op otherwise. Never blocks the loop for long.
D="$(cd "$(dirname "$0")" && pwd)"; CONF="$D/push.conf"; [ -f "$CONF" ] || exit 0
cfg() { grep -E "^$1=" "$CONF" | head -1 | cut -d= -f2-; }
CH=$(cfg channel); [ -z "$CH" ] || [ "$CH" = none ] && exit 0
T="$1"; M="$2"; F="${3:-attn}"; FILT=$(cfg filter); [ -n "$FILT" ] && { echo "$F" | grep -Eq "$FILT" || exit 0; }
case "$CH" in
  ntfy) TOP=$(cfg ntfy_topic); [ -n "$TOP" ] && curl -s -m 10 -H "Title: __PROJECT__: $T" -H "Priority: default" -d "$M" "https://ntfy.sh/$TOP" >/dev/null 2>&1 ;;
  imessage) TO=$(cfg imessage_to); [ -n "$TO" ] && { export MSG="__PROJECT__: ${T//\"/} - ${M//\"/}"
    send() { osascript -e 'tell application "Messages"' -e "set svc to 1st service whose service type = $1" -e "set b to buddy \"$TO\" of svc" -e 'send (system attribute "MSG") to b' -e 'end tell' 2>&1; }
    OUT=$(send iMessage); RC=$?; [ $RC -ne 0 ] && { OUT="$OUT | iMessage failed, trying SMS: $(send SMS)"; RC=$?; }
    mkdir -p "$D/cache"; echo "$(date '+%F %T') to=$TO rc=$RC $OUT" >> "$D/cache/push.log"; } ;;
esac
exit 0
