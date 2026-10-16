# iDotMatrix LED panel

Shows your usage batteries on a 32×32 iDotMatrix LED pixel panel (sold under several brands, including Reylax), over Bluetooth.

- **Claude and Codex on one screen**, each with its logo (Claude's orange starburst, Codex's blue knot):
  - next to the logo: **5-hour** percent left, then **weekly** percent left;
  - below: a 10-block battery for each, 5-hour first;
  - in the top-right corner: the **time the numbers are from** (e.g. `11:47`), cool white when current, yellow when old, red when the hub isn't answering;
  - in the top-left corner: a **gold coin and `CR`** when Codex says your account has credits (so Codex can keep working after its 5-hour window runs out). OpenAI doesn't report a credit amount for every plan, so this is on/off rather than a battery.
- A service whose numbers are **old is drawn dimmer**. Both Claude and Codex are checked live every minute, so this only happens if a check fails.
- Batteries are green, yellow or red, like every other display.
- **When the Mac sleeps,** the panel keeps the last picture; the update time tells you how old it is.
- Other layouts: `--claude` (Claude only, with reset times) or `--all` (each service full-screen, cycling every 10 seconds).

## How it works

The panel has no Wi-Fi, so it can't fetch numbers itself. A small program on the **same computer as the hub** reads `/api/display` every minute, draws a 32×32 picture, and sends it to the panel over Bluetooth. It sends whenever anything on the picture changes (the update time does, each minute), and at least every 10 minutes in case the panel was switched to another mode.

It **keeps the Bluetooth connection open** between updates. The panel briefly shows its own "connected" screen whenever a new connection starts, so staying connected means you only see that once (after login, or after the panel loses power), not every minute. While connected, the iDotMatrix phone app can't connect; use `--pause` to free the panel.

```
hub (Mac) ──► bridge.py (Mac) ──Bluetooth──► LED panel
```

The panel has two buttons. The **power button** turns it on and off. The **mode button** switches to the panel's own screens (clock, animations) for a moment; the batteries come back with the next update, within a minute. Neither press is reported over Bluetooth that we've found, so the program doesn't react to them.

## Install (macOS)

Requires the hub running on this Mac (`hub/macos/install.sh`) and the panel within Bluetooth range (about 10 m).

```bash
./displays/idotmatrix/install.sh
```

This sets up the Python packages it needs (`idotmatrix`, `bleak`, `pillow`) in `displays/idotmatrix/.venv`, then installs a background service that starts at login and restarts if it stops. The first time, it finds the panel by itself (its Bluetooth name starts with `IDM-`) and remembers it in `~/.usage-battery/idotmatrix.json`. **Close the iDotMatrix phone app** while it connects; the panel accepts one connection at a time.

| To... | Run |
|---|---|
| Check it's running | `./displays/idotmatrix/install.sh --status` |
| Use the iDotMatrix phone app | `./displays/idotmatrix/install.sh --pause`, then `--resume` when done |
| Watch its log | `tail -f ~/Library/Logs/usage-battery-idotmatrix.log` |
| Restart it | `./displays/idotmatrix/install.sh` |
| Remove it | `./displays/idotmatrix/install.sh --uninstall` |
| Try it once without the service | `displays/idotmatrix/.venv/bin/python displays/idotmatrix/bridge.py --once` |
| Use a different panel | delete `~/.usage-battery/idotmatrix.json`, then restart |

Options for `bridge.py`: `--claude` (Claude only, with reset times), `--all` (cycle each service full-screen), `--seconds 15` (time per screen with `--all`), `--address <id>` (a specific panel), `--hub URL --key CODE` (a hub on another computer).

## Troubleshooting

- **Panel shows something else:** the mode button was pressed, the phone app took over, or the panel was turned off and on. The bridge switches it back to the batteries with the next update, within a minute.
- **"couldn't reach the panel" in the log:** it's off, out of range, or connected to the phone app (a connected panel stops announcing itself over Bluetooth, so close the app fully, or `--pause` the program before using the app). It keeps retrying and recovers by itself, including after the panel is unplugged and plugged back in.
- **"No iDotMatrix panel found":** turn the panel on, bring it closer, close the phone app, and restart.

## Notes

- Uses the community [`idotmatrix`](https://github.com/derkalle4/python3-idotmatrix-library) library, built by studying the official app. It's archived (no longer maintained), so a panel firmware update could break it.
- Tested with a Reylax 32×32 panel (Bluetooth name `IDM-…`) on macOS.
