"""Draw one service as a 32x32 pixel picture for an iDotMatrix LED panel.

Layout (rows from the top):
   1-5   service icon, and the time the numbers were last updated (green / yellow / red = fresh / old / hub offline)
   8-12  5-hour: percent left, and when it resets (a time, e.g. 8:30)
  14-18  a 10-block battery
  21-25  weekly: percent left, and when it resets (a day, e.g. SUN)
  27-31  a 10-block battery
"""
from PIL import Image

SIZE = 32
OFF = (0, 0, 0)
LABEL = (90, 110, 150)     # soft blue-grey for 5H / WK
FRAME = (120, 120, 112)    # battery outline
EMPTY = (28, 28, 38)       # unlit battery blocks
LEVEL = {"ok": (40, 210, 90), "low": (255, 175, 0), "critical": (255, 40, 30)}
FRESH = {"fresh": (40, 210, 90), "stale": (255, 175, 0), "offline": (255, 40, 30)}

# 3x5 pixel font: digits, %, and the letters service names and labels need.
GLYPHS = {
    "0": "111 101 101 101 111", "1": "010 110 010 010 111", "2": "111 001 111 100 111",
    "3": "111 001 111 001 111", "4": "101 101 111 001 001", "5": "111 100 111 001 111",
    "6": "111 100 111 101 111", "7": "111 001 010 010 010", "8": "111 101 111 101 111",
    "9": "111 101 111 001 111", "%": "101 001 010 100 101", " ": "000 000 000 000 000",
    ":": "0 1 0 1 0",
    "A": "010 101 111 101 101", "C": "011 100 100 100 011", "D": "110 101 101 101 110",
    "E": "111 100 110 100 111", "H": "101 101 111 101 101", "K": "101 110 100 110 101",
    "L": "100 100 100 100 111", "O": "010 101 101 101 010", "P": "110 101 110 100 100",
    "T": "111 010 010 010 010", "U": "101 101 101 101 111", "W": "101 101 111 111 101",
    "X": "101 101 010 101 101", "?": "111 001 010 000 010",
    "F": "111 100 110 100 100", "I": "111 010 010 010 111", "M": "101 111 111 101 101",
    "N": "111 101 101 101 101", "R": "110 101 110 101 101", "S": "011 100 010 001 110",
}

# 5x5 service icons and their colors.
ICONS = {
    "Claude": ("10101 01110 11111 01110 10101", (217, 119, 87)),        # starburst, Claude orange
    "ChatGPT / Codex": ("01110 11011 10001 11011 01110", (110, 170, 255)),  # knot, Codex blue
}
NAMES = {"Claude": "CLAUDE", "ChatGPT / Codex": "CODEX"}


def text(px, x, y, s, color):
    for ch in s.upper():
        rows = GLYPHS.get(ch, GLYPHS["?"]).split()
        for r, row in enumerate(rows):
            for c, bit in enumerate(row):
                if bit == "1" and 0 <= x + c < SIZE:
                    px[x + c, y + r] = color
        x += len(rows[0]) + 1


def text_width(s):
    return sum(len(GLYPHS.get(ch, GLYPHS["?"]).split()[0]) + 1 for ch in s.upper()) - 1


def reset_word(resets):
    """'8:30 PM' -> '8:30', 'Sun 4:00 AM' -> 'SUN', '' -> ''."""
    if not resets:
        return ""
    first = resets.split()[0]
    return first.upper()[:3] if first[:1].isalpha() else first


def shade(color, factor):
    return tuple(min(255, int(v * factor)) for v in color)


def battery(px, y, left, color):
    """31x5 outline at columns 0-30 plus a tip at 31; 10 shaded blocks of 2x3, one per 10%."""
    for x in range(31):
        px[x, y] = px[x, y + 4] = FRAME
    for yy in range(y, y + 5):
        px[0, yy] = px[30, yy] = FRAME
    px[31, y + 1] = px[31, y + 2] = px[31, y + 3] = FRAME
    lit = round(left / 10)
    for i in range(10):
        x0 = 1 + i * 3
        for dx in range(2):
            if i < lit:
                px[x0 + dx, y + 1] = shade(color, 1.35)   # bright top edge
                px[x0 + dx, y + 2] = color
                px[x0 + dx, y + 3] = shade(color, 0.6)    # darker bottom edge
            else:
                for dy in (1, 2, 3):
                    px[x0 + dx, y + dy] = EMPTY


def short(label):
    low = label.lower()
    return "5H" if low.startswith("5-hour") else "WK" if low.startswith("weekly") else label[:2].upper()


def render(service, freshness="fresh", updated=""):
    """service: one entry of /api/display's `services`.
    freshness: fresh | stale | offline (colors the updated time). updated: e.g. '7:05'."""
    img = Image.new("RGB", (SIZE, SIZE), OFF)
    px = img.load()

    icon, icon_color = ICONS.get(service["name"], ("11111 10001 10001 10001 11111", LABEL))
    for r, row in enumerate(icon.split()):
        for c, bit in enumerate(row):
            if bit == "1":
                px[c, 1 + r] = icon_color
    if updated:
        text(px, SIZE - text_width(updated), 1, updated, FRESH[freshness])

    for i, m in enumerate(service["meters"][:2]):
        y = 8 + i * 13
        color = LEVEL.get(m["level"], LABEL)
        text(px, 0, y, f"{m['left']}%", color)
        word = reset_word(m.get("resets", ""))
        if word and text_width(f"{m['left']}%") + 3 + text_width(word) <= SIZE:
            text(px, SIZE - text_width(word), y, word, LABEL)
        battery(px, y + 6, m["left"], color)
    return img


def led_preview(img, scale=12):
    """Upscale with dark gaps between pixels so a preview looks like the LED panel."""
    out = Image.new("RGB", (SIZE * scale, SIZE * scale), (8, 8, 10))
    src, dst = img.load(), out.load()
    for y in range(SIZE):
        for x in range(SIZE):
            c = src[x, y] if src[x, y] != OFF else (18, 18, 22)
            for dy in range(1, scale - 1):
                for dx in range(1, scale - 1):
                    dst[x * scale + dx, y * scale + dy] = c
    return out


# --- Both services on one screen ---------------------------------------------------------
#
#   rows  0-4   Claude icon, 5-hour % left, weekly % left
#   rows  6-7   Claude 5-hour battery (10 blocks)
#   rows  9-10  Claude weekly battery
#   rows 13-17  Codex icon, 5-hour %, weekly %
#   rows 19-20  Codex 5-hour battery
#   rows 22-23  Codex weekly battery
#   rows 26-30  time the numbers are from (green / yellow / red = fresh / old / hub offline)
# A service whose numbers are old (Codex until you run `codex`) is drawn dimmer.

def thin_battery(px, y, left, color, dim=1.0):
    """10 blocks of 2x2 pixels with 1-pixel gaps (29 px wide), brighter top row."""
    lit = round(left / 10)
    for i in range(10):
        x0 = 1 + i * 3
        for dx in range(2):
            if i < lit:
                px[x0 + dx, y] = shade(color, 1.3 * dim)
                px[x0 + dx, y + 1] = shade(color, 0.75 * dim)
            else:
                px[x0 + dx, y] = px[x0 + dx, y + 1] = EMPTY


def service_block(px, y, service, dim=1.0):
    icon, icon_color = ICONS.get(service["name"], ("11111 10001 10001 10001 11111", LABEL))
    for r, row in enumerate(icon.split()):
        for c, bit in enumerate(row):
            if bit == "1":
                px[c, y + r] = shade(icon_color, dim)
    meters = service["meters"][:2]
    words = [f"{m['left']}%" for m in meters]
    if len(words) == 2 and 7 + text_width(words[0]) + 3 + text_width(words[1]) > SIZE:
        words = [w.rstrip("%") for w in words]  # e.g. 63 / 100: drop the % signs so both fit
    if words:
        text(px, 7, y, words[0], shade(LEVEL.get(meters[0]["level"], LABEL), dim))
    if len(words) > 1:
        text(px, SIZE - text_width(words[1]), y, words[1], shade(LEVEL.get(meters[1]["level"], LABEL), dim))
    for i, m in enumerate(meters):
        thin_battery(px, y + 6 + i * 3, m["left"], LEVEL.get(m["level"], LABEL), dim)


def render_both(services, stale_names=(), freshness="fresh", updated=""):
    """services: up to two /api/display services (Claude first). stale_names are drawn dimmer."""
    img = Image.new("RGB", (SIZE, SIZE), OFF)
    px = img.load()
    for i, svc in enumerate(services[:2]):
        service_block(px, i * 13, svc, 0.45 if svc["name"] in stale_names else 1.0)
    if updated:
        text(px, SIZE - text_width(updated), 26, updated, FRESH[freshness])
    return img
