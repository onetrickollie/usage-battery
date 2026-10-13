#!/usr/bin/env bash
# Run the Usage Battery hub in the background on macOS.
# It starts when you log in, restarts if it stops, and keeps the Mac awake while
# it's plugged in (on battery, the Mac sleeps normally).
#
#   ./install.sh               # install and start, reachable by displays on your Wi-Fi (--lan)
#   ./install.sh --local-only  # only this Mac can see it
#   ./install.sh --status      # is it running? where are the logs?
#   ./install.sh --uninstall
set -euo pipefail

LABEL=com.usage-battery.hub
HUB_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/usage-battery-hub.log"
DOMAIN="gui/$(id -u)"
LAN_ARG="--lan"

status() {
  if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
    echo "Running in the background ($LABEL)."
  else
    echo "Not running."
  fi
  echo "Log: $LOG"
}

case "${1:-}" in
  --uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Stopped and removed the background hub. Your saved data in ~/.usage-battery is kept."
    exit 0 ;;
  --status) status; exit 0 ;;
  --local-only) LAN_ARG="" ;;
  "") ;;
  -h|--help) sed -n 2,10p "$0"; exit 0 ;;
  *) echo "Unknown option: $1" >&2; exit 1 ;;
esac

PYTHON="$(command -v python3 || true)"
CLAUDE="$(command -v claude || true)"
[ -n "$PYTHON" ] || { echo "python3 not found." >&2; exit 1; }
[ -n "$CLAUDE" ] || echo "Warning: Claude Code ('claude') isn't on your PATH; Claude usage won't refresh until it is."

if lsof -nP -iTCP:8765 -sTCP:LISTEN >/dev/null 2>&1 && ! launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  echo "Port 8765 is in use: the hub is probably running in a Terminal window. Stop it (Ctrl+C) and run this again." >&2
  exit 1
fi

# launchd starts programs with a minimal PATH, so pass along where python3 and claude live.
SEARCH_PATH="$(dirname "$PYTHON")"
[ -n "$CLAUDE" ] && SEARCH_PATH="$SEARCH_PATH:$(dirname "$CLAUDE")"
SEARCH_PATH="$SEARCH_PATH:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
touch "$LOG" && chmod 600 "$LOG"  # it includes the display passcode
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/caffeinate</string>
    <string>-s</string>
    <string>$PYTHON</string>
    <string>-u</string>
    <string>$HUB_DIR/battery.py</string>
$( [ -n "$LAN_ARG" ] && echo "    <string>$LAN_ARG</string>" )
  </array>
  <key>WorkingDirectory</key><string>$HUB_DIR</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$SEARCH_PATH</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"

for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -s -o /dev/null http://127.0.0.1:8765/ && break
  sleep 1
done
if curl -s -o /dev/null http://127.0.0.1:8765/; then
  echo "The hub is running in the background and starts automatically when you log in."
  echo "Open: http://127.0.0.1:8765"
  if [ -n "$LAN_ARG" ]; then
    grep -E "^(Other devices|Passcode)" "$LOG" | tail -2 || true
    echo "If macOS asks whether Python may accept incoming connections, click Allow."
  fi
else
  echo "The hub didn't answer yet. Recent log:"; tail -20 "$LOG"; exit 1
fi
status
