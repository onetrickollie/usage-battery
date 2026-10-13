#!/usr/bin/env python3
"""Usage Battery display for a Raspberry Pi with a PiSugar Whisplay HAT.

Every 60 seconds it asks the hub (battery.py --lan on your computer) for your usage
and draws one service per screen. Press the button to cycle through services
(e.g. Claude -> ChatGPT / Codex -> Claude). The RGB LED shows the lowest battery
on the current screen: green, yellow or red.

Run on the Pi:
  python3 display.py --hub http://MacBook-Pro-180.local:8765 --key <passcode>
Preview the screens on any computer (writes PNGs, no hardware needed):
  python3 display.py --preview --hub http://127.0.0.1:8765
"""
import argparse, json, os, sys, threading, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

W, H = 240, 280
REFRESH_SECONDS = 60
BG, FG, MUTED, TRACK = (14, 14, 16), (240, 240, 236), (150, 148, 140), (52, 52, 56)
LEVEL_COLORS = {"ok": (52, 199, 89), "low": (255, 196, 0), "critical": (255, 69, 58)}
LED_COLORS = {"ok": (0, 40, 0), "low": (60, 30, 0), "critical": (60, 0, 0)}  # kept dim
FONT_PATHS = {
    False: ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"],
    True: ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
}


def font(size, bold=False):
    for path in FONT_PATHS[bold]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_TITLE, F_LABEL, F_PCT, F_SMALL = font(21, True), font(15), font(24, True), font(12)


class Usage:
    """Fetches /api/display from the hub and remembers the last good answer."""

    def __init__(self, hub, key):
        self.url = hub.rstrip("/") + "/api/display"
        self.key = key
        self.data = None          # last good payload
        self.last_ok = None       # time.time() of last good fetch
        self.error = "Connecting to your computer..."

    def fetch(self):
        req = urllib.request.Request(self.url, headers={"X-Battery-Key": self.key} if self.key else {})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.data = json.load(resp)
            self.last_ok, self.error = time.time(), None
        except urllib.error.HTTPError as e:
            self.error = "Wrong passcode" if e.code == 401 else f"Hub error {e.code}"
        except Exception:
            self.error = "Computer offline"

    @property
    def services(self):
        return (self.data or {}).get("services") or []


def draw_battery(d, x, y, w, h, left, color):
    d.rounded_rectangle([x, y, x + w, y + h], radius=6, outline=FG, width=2)
    d.rounded_rectangle([x + w + 2, y + h // 2 - 5, x + w + 6, y + h // 2 + 5], radius=2, fill=FG)
    inner = w - 8
    fill = round(inner * left / 100)
    d.rounded_rectangle([x + 4, y + 4, x + w - 4, y + h - 4], radius=3, fill=TRACK)
    if fill > 0:
        d.rounded_rectangle([x + 4, y + 4, x + 4 + fill, y + h - 4], radius=3, fill=color)


def render(usage, index):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    services = usage.services

    if not services:
        d.text((W // 2, 120), "Usage Battery", font=F_TITLE, fill=FG, anchor="mm")
        d.text((W // 2, 152), usage.error or "No services set up yet", font=F_SMALL, fill=MUTED, anchor="mm")
        return img, None

    svc = services[index % len(services)]
    # Header: service name and page dots
    n = len(services)
    title_font, room = F_TITLE, W - 18 - (n * 14 + 20)  # leave space for the page dots
    for size in (21, 19, 17, 15):
        title_font = font(size, True)
        if d.textlength(svc["name"], font=title_font) <= room:
            break
    d.text((18, 22), svc["name"], font=title_font, fill=FG, anchor="lm")
    for i in range(n):
        cx = W - 22 - (n - 1 - i) * 14
        d.ellipse([cx - 4, 18, cx + 4, 26], fill=FG if i == index % n else TRACK)

    # Meters
    meters = svc["meters"][:3]
    top, slot = 52, (196 if len(meters) <= 2 else 210) // max(1, len(meters))
    worst = None
    for i, m in enumerate(meters):
        y = top + i * slot
        color = LEVEL_COLORS.get(m["level"], FG)
        d.text((18, y + 10), m["label"], font=F_LABEL, fill=FG, anchor="lm")
        d.text((W - 18, y + 10), f"{m['left']}%", font=F_PCT, fill=color, anchor="rm")
        draw_battery(d, 18, y + 28, W - 46, 26, m["left"], color)
        if m.get("resets"):
            d.text((18, y + 70), f"Recharges {m['resets']}", font=F_SMALL, fill=MUTED, anchor="lm")
        order = ["critical", "low", "ok"]
        if worst is None or order.index(m["level"]) < order.index(worst):
            worst = m["level"]

    # Footer: freshness
    if usage.error:
        since = time.strftime("%-I:%M %p", time.localtime(usage.last_ok)) if usage.last_ok else "never"
        footer, color = f"{usage.error} · last {since}", LEVEL_COLORS["low"]
    else:
        footer, color = f"Updated {usage.data.get('updated_text', '')}", MUTED
    d.text((W // 2, H - 22), footer, font=F_SMALL, fill=color, anchor="mm")
    return img, (None if usage.error else worst)


def rgb565(img):
    try:
        import numpy as np
        a = np.asarray(img.convert("RGB"), dtype=np.uint16)
        v = ((a[..., 0] & 0xF8) << 8) | ((a[..., 1] & 0xFC) << 3) | (a[..., 2] >> 3)
        return v.astype(">u2").tobytes()
    except ImportError:
        out = bytearray()
        for r, g, b in img.convert("RGB").getdata():
            v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out += bytes((v >> 8, v & 0xFF))
        return bytes(out)


def run_preview(usage, outdir):
    usage.fetch()
    os.makedirs(outdir, exist_ok=True)
    count = max(1, len(usage.services))
    for i in range(count):
        img, _ = render(usage, i)
        path = os.path.join(outdir, f"screen-{i + 1}.png")
        img.save(path)
        print("wrote", path)


def run_device(usage, whisplay_dir):
    sys.path.insert(0, whisplay_dir)
    from whisplay import WhisplayBoard  # PiSugar driver: runtime/whisplay.py

    board = WhisplayBoard()
    board.set_backlight(80)
    state = {"index": 0, "last_press": 0.0}
    lock = threading.Lock()

    def show():
        with lock:
            img, level = render(usage, state["index"])
            board.draw_image(0, 0, W, H, rgb565(img))
            board.set_rgb(*(LED_COLORS[level] if level else (0, 0, 0)))

    def on_press():
        now = time.time()
        if now - state["last_press"] < 0.25:  # ignore switch bounce
            return
        state["last_press"] = now
        state["index"] = (state["index"] + 1) % max(1, len(usage.services))
        show()

    board.on_button_press(on_press)
    try:
        while True:
            usage.fetch()
            show()
            time.sleep(REFRESH_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        board.set_rgb(0, 0, 0)
        board.cleanup()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hub", default=os.environ.get("BATTERY_HUB", "http://MacBook-Pro-180.local:8765"),
                   help="address of battery.py --lan on your computer")
    p.add_argument("--key", default=os.environ.get("BATTERY_KEY", ""), help="passcode printed by battery.py --lan")
    p.add_argument("--whisplay-dir", default=os.environ.get("WHISPLAY_DIR", os.path.expanduser("~/Whisplay/runtime")),
                   help="folder containing the PiSugar whisplay.py driver")
    p.add_argument("--preview", action="store_true", help="write PNG previews instead of using the HAT")
    p.add_argument("--out", default="preview", help="folder for --preview images")
    args = p.parse_args()

    usage = Usage(args.hub, args.key)
    if args.preview:
        run_preview(usage, args.out)
    else:
        run_device(usage, args.whisplay_dir)


if __name__ == "__main__":
    main()
