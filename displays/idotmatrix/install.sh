#!/usr/bin/env bash
# Run the iDotMatrix panel bridge in the background on macOS (same computer as the hub).
# It starts when you log in and restarts if it stops.
#
#   ./install.sh               # set up and start
#   ./install.sh --status      # is it running? where is the log?
#   ./install.sh --pause       # let go of the panel (e.g. to use the iDotMatrix phone app)
#   ./install.sh --resume      # take it back
#   ./install.sh --uninstall
set -euo pipefail

LABEL=com.usage-battery.idotmatrix
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HERE/.venv"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/usage-battery-idotmatrix.log"
DOMAIN="gui/$(id -u)"

case "${1:-}" in
  --uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Stopped and removed the panel bridge."
    exit 0 ;;
  --pause)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    echo "Paused: the panel is free for the phone app. Run ./install.sh --resume (or log in again) to take it back."
    exit 0 ;;
  --resume)
    [ -f "$PLIST" ] || { echo "Not installed yet: run ./install.sh" >&2; exit 1; }
    launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null || true
    echo "Resumed."
    exit 0 ;;
  --status)
    launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 && echo "Running in the background ($LABEL)." || echo "Not running."
    echo "Log: $LOG"; tail -5 "$LOG" 2>/dev/null || true
    exit 0 ;;
  "") ;;
  -h|--help) sed -n 2,10p "$0"; exit 0 ;;
  *) echo "Unknown option: $1" >&2; exit 1 ;;
esac

if [ ! -x "$VENV/bin/python" ]; then
  echo "== Setting up Python packages (idotmatrix, bleak, pillow)"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check idotmatrix bleak pillow
fi

mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV/bin/python</string>
    <string>-u</string>
    <string>$HERE/bridge.py</string>
  </array>
  <key>WorkingDirectory</key><string>$HERE</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
for _ in 1 2 3 4 5 6 7 8 9 10; do  # wait for the old copy to stop before starting the new one
  launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 || break
  sleep 1
done
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Started. It finds the panel by itself the first time (close the iDotMatrix phone app)."
echo "Log: $LOG"
