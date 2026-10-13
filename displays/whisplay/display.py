#!/usr/bin/env python3
"""Usage Battery display for a Raspberry Pi with a PiSugar Whisplay HAT.

Every 60 seconds it asks the hub (battery.py --lan on your computer) for your usage
and draws one service per screen in a pixel-art style:
each battery is 10 power blocks, one per 10%. Press the button to cycle through services
(e.g. Claude -> ChatGPT / Codex -> Claude). The RGB LED shows the lowest battery
on the current screen: green, yellow or red.

Run on the Pi:
  python3 display.py --hub http://MacBook-Pro-180.local:8765 --key <passcode>
Preview the screens on any computer (writes PNGs, no hardware needed):
  python3 display.py --preview --hub http://127.0.0.1:8765
"""
import argparse, json, os, sys, threading, time, urllib.request
from PIL import Image, ImageDraw

W, H = 240, 280
LW, LH, SCALE = 120, 140, 2  # draw with 120x140 "big pixels", shown at 240x280
REFRESH_SECONDS = 60
BG, FG, MUTED, EMPTY = (16, 16, 28), (236, 236, 228), (122, 122, 146), (44, 44, 64)
LEVEL_COLORS = {"ok": (62, 224, 122), "low": (255, 210, 63), "critical": (255, 77, 77)}
LED_COLORS = {"ok": (0, 40, 0), "low": (60, 30, 0), "critical": (60, 0, 0)}  # kept dim

class Usage:
    """Fetches /api/display from the hub and remembers the last good answer."""

    def __init__(self, hub, key):
        self.url = hub.rstrip("/") + "/api/display"
        self.key = key
        self.data = None          # last good payload
        self.last_ok = None       # time.time() of last good fetch
        self.error = "Connecting..."

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


# 5x7 pixel font. Text is drawn in capitals; unknown characters show as "?".
GLYPHS = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    "%": "11000 11001 00010 00100 01000 10011 00011", ":": "00000 01100 01100 00000 01100 01100 00000",
    "/": "00000 00001 00010 00100 01000 10000 00000", ".": "00000 00000 00000 00000 00000 01100 01100",
    "-": "00000 00000 00000 11111 00000 00000 00000", "(": "00010 00100 01000 01000 01000 00100 00010",
    ")": "01000 00100 00010 00010 00010 00100 01000", " ": "00000 00000 00000 00000 00000 00000 00000",
    "!": "00100 00100 00100 00100 00100 00000 00100", "?": "01110 10001 00001 00010 00100 00000 00100",
    "'": "00100 00100 01000 00000 00000 00000 00000", ",": "00000 00000 00000 00000 01100 00100 01000",
}


def text_width(s, size=1):
    return max(0, len(s) * 6 - 1) * size


def text(d, x, y, s, color, size=1):
    for ch in s.upper():
        for r, row in enumerate(GLYPHS.get(ch, GLYPHS["?"]).split()):
            for c, bit in enumerate(row):
                if bit == "1":
                    d.rectangle([x + c * size, y + r * size, x + (c + 1) * size - 1, y + (r + 1) * size - 1], fill=color)
        x += 6 * size


def centered(d, y, s, color, size=1):
    max_chars = (LW - 8) // (6 * size)
    s = s if len(s) <= max_chars else s[:max_chars - 1] + "."
    text(d, (LW - text_width(s, size)) // 2, y, s, color, size)


def battery(d, x, y, left, color):
    """95x14 outline with a tip; 10 power blocks inside, one per 10%."""
    w, h = 95, 14
    d.rectangle([x, y, x + w - 1, y + h - 1], outline=FG)
    d.rectangle([x + w, y + 4, x + w + 2, y + h - 5], fill=FG)
    lit = round(left / 10)
    for i in range(10):
        bx = x + 3 + i * 9
        d.rectangle([bx, y + 3, bx + 7, y + h - 4], fill=color if i < lit else EMPTY)


def short_label(label):
    low = label.lower()
    if low.startswith("5-hour"):
        return "5-HOUR"
    if low.startswith("weekly"):
        scope = label[label.find("(") + 1:label.find(")")] if "(" in label else ""
        return "WEEKLY" if not scope or scope.lower() == "all models" else f"WEEKLY {scope}"[:12]
    return label[:12]


def render(usage, index):
    """Draw one service at 120x140 and scale it up with hard pixel edges."""
    img = Image.new("RGB", (LW, LH), BG)
    d = ImageDraw.Draw(img)
    services = usage.services

    if not services:
        centered(d, 52, "USAGE", FG, 2)
        centered(d, 70, "BATTERY", FG, 2)
        centered(d, 96, usage.error or "NO SERVICES YET", MUTED)
        return img.resize((W, H), Image.NEAREST), None

    n = len(services)
    svc = services[index % n]
    title = svc["name"]
    big = text_width(title, 2) <= LW - 16 - n * 5
    text(d, 8, 6 if big else 10, title, FG, 2 if big else 1)
    for i in range(n):  # page markers
        px = LW - 8 - (n - i) * 5 + 1
        d.rectangle([px, 10, px + 2, 12], fill=FG if i == index % n else EMPTY)
    for x in range(8, LW - 8, 2):
        d.point((x, 24), fill=EMPTY)

    meters = svc["meters"][:3]
    slot = 47 if len(meters) <= 2 else 33
    order, worst = ["critical", "low", "ok"], None
    for i, m in enumerate(meters):
        y = 30 + i * slot
        color = LEVEL_COLORS.get(m["level"], FG)
        text(d, 8, y + 4, short_label(m["label"]), FG)
        pct = f"{m['left']}%"
        text(d, LW - 8 - text_width(pct, 2) + 1, y, pct, color, 2)
        battery(d, 8, y + 17, m["left"], color)
        if m.get("resets") and len(meters) <= 2:
            text(d, 8, y + 35, "RESETS " + m["resets"].replace(":00", ""), MUTED)
        if worst is None or order.index(m["level"]) < order.index(worst):
            worst = m["level"]

    if usage.error:
        since = time.strftime("%-I:%M %p", time.localtime(usage.last_ok)) if usage.last_ok else ""
        label = "WRONG PASSCODE" if "passcode" in usage.error.lower() else f"OFFLINE {since}".strip()
        centered(d, LH - 11, label, LEVEL_COLORS["low"])
    else:
        centered(d, LH - 11, f"UPDATED {usage.data.get('updated_text', '')}", MUTED)
    return img.resize((W, H), Image.NEAREST), (None if usage.error else worst)


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
