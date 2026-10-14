# iDotMatrix LED panel

Shows your usage batteries on a 32×32 iDotMatrix LED pixel panel (sold under several brands, including Reylax), over Bluetooth.

- **Claude at a glance**, top to bottom:
  - the Claude icon, and the **time the numbers are from** (e.g. `7:13`), colored green when current, yellow when old, red when the hub isn't answering;
  - the **5-hour** limit: percent left, **when it resets** (a time, e.g. `9:10`), and a 10-block battery;
  - the **weekly** limit: percent left, **the day it resets** (e.g. `SUN`), and a 10-block battery.
- Batteries are green, yellow or red, like every other display.
- **When the Mac sleeps,** the panel keeps the last picture; the update time tells you how old it is.
- `--all` shows every service instead (Claude, then Codex, 10 seconds each, looping on the panel by itself).

## How it works

The panel has no Wi-Fi, so it can't fetch numbers itself. A small program on the **same computer as the hub** reads `/api/display` every minute, draws a 32×32 picture, and sends it to the panel over Bluetooth (about a second). It sends whenever anything on the picture changes (the update time does, each minute), and at least every 10 minutes in case the panel was switched to another mode.

```
hub (Mac) ──► bridge.py (Mac) ──Bluetooth──► LED panel
```

The panel's own button isn't reported over Bluetooth, so the program can't use it. A short press does nothing visible while it shows the batteries; a long press turns the panel off.

## Install (macOS)

Requires the hub running on this Mac (`hub/macos/install.sh`) and the panel within Bluetooth range (about 10 m).

```bash
./displays/idotmatrix/install.sh
```

This sets up the Python packages it needs (`idotmatrix`, `bleak`, `pillow`) in `displays/idotmatrix/.venv`, then installs a background service that starts at login and restarts if it stops. The first time, it finds the panel by itself (its Bluetooth name starts with `IDM-`) and remembers it in `~/.usage-battery/idotmatrix.json`. **Close the iDotMatrix phone app** while it connects; the panel accepts one connection at a time.

| To... | Run |
|---|---|
| Check it's running | `./displays/idotmatrix/install.sh --status` |
| Watch its log | `tail -f ~/Library/Logs/usage-battery-idotmatrix.log` |
| Restart it | `./displays/idotmatrix/install.sh` |
| Remove it | `./displays/idotmatrix/install.sh --uninstall` |
| Try it once without the service | `displays/idotmatrix/.venv/bin/python displays/idotmatrix/bridge.py --once` |
| Use a different panel | delete `~/.usage-battery/idotmatrix.json`, then restart |

Options for `bridge.py`: `--all` (cycle every service), `--seconds 15` (time per screen with `--all`), `--address <id>` (a specific panel), `--hub URL --key CODE` (a hub on another computer).

## Troubleshooting

- **Panel shows something else:** the phone app took over, or the panel was turned off and on. The bridge puts the batteries back within 10 minutes, or restart it to do it now.
- **"couldn't reach the panel" in the log:** it's off, out of range, or connected to the phone app. It keeps retrying.
- **"No iDotMatrix panel found":** turn the panel on, bring it closer, close the phone app, and restart.

## Notes

- Uses the community [`idotmatrix`](https://github.com/derkalle4/python3-idotmatrix-library) library, built by studying the official app. It's archived (no longer maintained), so a panel firmware update could break it.
- Tested with a Reylax 32×32 panel (Bluetooth name `IDM-…`) on macOS.
