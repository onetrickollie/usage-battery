# Whisplay HAT display

Shows your usage batteries on a Raspberry Pi with a [PiSugar Whisplay HAT](https://www.pisugar.com/products/whisplay-hat-for-pi-zero-2w-audio-display): a 1.69" screen, one button and an RGB LED.

- **Pixel-art screens.** A built-in 5×7 pixel font and batteries made of 10 power blocks (one per 10%). No extra fonts needed.
- **One service per screen.** Press the button to cycle through them: Claude → ChatGPT / Codex → Claude. Services with no data are skipped.
- **The LED** glows dim green, yellow or red for the lowest battery on the current screen.
- **Refreshes every minute** from the hub on your computer, and shows "EMPTY IN 1H 40M" under a battery when you're on pace to run out before it resets.
- **Says how fresh the numbers are.** "UPDATED 4:10 PM" when current, "DATA 25M OLD" when the hub's numbers are stale (Codex only updates when you run `codex`), and "OFFLINE 25M AGO" when the hub can't be reached. While offline, a battery refills when its reset time passes.

## What you need

- A Raspberry Pi with a 40-pin header (tested on a **Pi 5** with Raspberry Pi OS trixie), with the Whisplay HAT attached.
- The [Whisplay driver](https://github.com/PiSugar/Whisplay) installed:
  ```bash
  git clone https://github.com/PiSugar/Whisplay.git --depth 1 ~/Whisplay
  cd ~/Whisplay && sudo bash install_driver.sh && sudo reboot
  ```
- The hub running on your computer **with `--lan`**, on the same Wi-Fi as the Pi:
  ```bash
  python3 hub/battery.py --lan
  ```
  It prints the address and passcode the Pi needs.

## Install

On the Pi:

```bash
git clone https://github.com/onetrickollie/usage-battery.git
cd usage-battery/displays/whisplay
./install.sh
```

It asks for the hub address and passcode, saves them to `~/.config/usage-battery/env` (readable only by you), and installs a systemd user service that starts the display at boot and restarts it if it crashes.

To install without questions: `./install.sh --hub http://my-mac.local:8765 --key <passcode>`

If the installer says it can't enable start-at-boot, run `sudo loginctl enable-linger $USER` once.

## Everyday use

| To... | Run on the Pi |
|---|---|
| See what it's doing | `journalctl --user -u usage-battery-display -f` |
| Restart it | `systemctl --user restart usage-battery-display` |
| Change the hub or passcode | `./install.sh --hub URL --key CODE` |
| Remove it | `./install.sh --uninstall` |

## Preview without the hardware

`display.py --preview` renders each screen to a PNG on any computer with Pillow:

```bash
python3 display.py --preview --hub http://127.0.0.1:8765
```

## Troubleshooting

- **"Wrong passcode"**: the passcode changed or was mistyped. Rerun `./install.sh --hub ... --key ...` with the one `battery.py --lan` prints.
- **"OFFLINE … AGO"**: the hub isn't running with `--lan`, the computer is asleep, or the two are on different networks. On macOS, `hub/macos/install.sh` keeps the hub running; allow Python to accept incoming connections if asked.
- **Blank screen**: check the log (above). Make sure the Whisplay driver's own test works (`python3 ~/Whisplay/example/test.py`) and nothing else is using the screen.
