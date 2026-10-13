#!/usr/bin/env bash
# Install the Usage Battery display on a Raspberry Pi with a PiSugar Whisplay HAT.
# It runs as a systemd user service, so it starts at boot and restarts if it crashes.
#
#   ./install.sh                         # asks for the hub address and passcode
#   ./install.sh --hub URL --key CODE    # no questions
#   ./install.sh --uninstall
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/.local/share/usage-battery"
CONF_DIR="$HOME/.config/usage-battery"
ENV_FILE="$CONF_DIR/env"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT=usage-battery-display.service
HUB="" KEY="" WHISPLAY_DIR="${WHISPLAY_DIR:-$HOME/Whisplay/runtime}"

while [ $# -gt 0 ]; do
  case "$1" in
    --hub) HUB="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --whisplay-dir) WHISPLAY_DIR="$2"; shift 2 ;;
    --uninstall)
      systemctl --user disable --now "$UNIT" 2>/dev/null || true
      rm -f "$UNIT_DIR/$UNIT"; systemctl --user daemon-reload
      rm -rf "$APP_DIR"
      echo "Removed the display service. Your settings are still in $CONF_DIR (delete it to forget the passcode)."
      exit 0 ;;
    -h|--help) sed -n 2,8p "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

echo "== Checking requirements"
if [ ! -f "$WHISPLAY_DIR/whisplay.py" ]; then
  echo "Whisplay driver not found in $WHISPLAY_DIR."
  echo "Install it first:  git clone https://github.com/PiSugar/Whisplay.git --depth 1 ~/Whisplay"
  echo "                   cd ~/Whisplay && sudo bash install_driver.sh && sudo reboot"
  echo "(Or pass --whisplay-dir if it lives somewhere else.)"
  exit 1
fi
python3 -c "import PIL" 2>/dev/null || { echo "Pillow is missing:  sudo apt install python3-pil"; exit 1; }
python3 -c "import numpy" 2>/dev/null || echo "(Optional) numpy makes redraws faster:  sudo apt install python3-numpy"
id -nG | grep -qw gpio && id -nG | grep -qw spi || echo "Warning: $USER should be in the gpio and spi groups (sudo usermod -aG gpio,spi $USER)."

echo "== Settings"
mkdir -p "$CONF_DIR"; chmod 700 "$CONF_DIR"
if [ -f "$ENV_FILE" ] && [ -z "$HUB$KEY" ]; then
  echo "Using existing settings in $ENV_FILE"
else
  if [ -z "$HUB" ]; then
    read -r -p "Hub address (shown by 'python3 battery.py --lan', e.g. http://my-mac.local:8765): " HUB
  fi
  if [ -z "$KEY" ]; then
    read -r -s -p "Passcode (also shown by battery.py --lan): " KEY; echo
  fi
  [ -n "$HUB" ] && [ -n "$KEY" ] || { echo "Both a hub address and a passcode are needed." >&2; exit 1; }
  ( umask 077; printf 'BATTERY_HUB=%s\nBATTERY_KEY=%s\nWHISPLAY_DIR=%s\n' "$HUB" "$KEY" "$WHISPLAY_DIR" > "$ENV_FILE" )
  echo "Saved to $ENV_FILE (readable only by you)"
fi
grep -q '^WHISPLAY_DIR=' "$ENV_FILE" || echo "WHISPLAY_DIR=$WHISPLAY_DIR" >> "$ENV_FILE"

echo "== Installing"
mkdir -p "$APP_DIR" "$UNIT_DIR"
install -m 644 "$HERE/display.py" "$APP_DIR/display.py"
install -m 644 "$HERE/$UNIT" "$UNIT_DIR/$UNIT"
systemctl --user daemon-reload
systemctl --user enable "$UNIT" >/dev/null
systemctl --user restart "$UNIT"

# Start at boot even before anyone logs in.
if ! loginctl show-user "$USER" -p Linger 2>/dev/null | grep -q yes; then
  loginctl enable-linger "$USER" 2>/dev/null \
    || echo "To start the display at boot without logging in, run once:  sudo loginctl enable-linger $USER"
fi

sleep 3
if systemctl --user is-active --quiet "$UNIT"; then
  echo "== Done. The display is running and will start automatically at boot."
else
  echo "== The service didn't start. Recent log:"
  journalctl --user -u "$UNIT" -n 20 --no-pager || true
  exit 1
fi
echo "Logs:      journalctl --user -u $UNIT -f"
echo "Restart:   systemctl --user restart $UNIT"
echo "Uninstall: $HERE/install.sh --uninstall"
