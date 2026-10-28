"""Baby Mochi: Claude 5H mascot, persistent four-value table.

No timers or I/O here. runtime.py supplies a short transition only on fresh
Claude-5H changes; the bridge always restores the final still PNG afterward.
"""
import math
from PIL import Image, ImageDraw
from styles.common import canvas, text, centered, logo, word, color, finish

YELLOW = (255, 210, 48)
HOLE = (65, 38, 7)
CREAM = (255, 239, 207)
FUR = (225, 205, 170)
PINK = (250, 155, 185)
INK = (25, 29, 39)
WEDGE = [(x, y) for y in range(6, 19) for x in range(4, 29) if abs(x-16) <= y-6]
ORDER = sorted(WEDGE, key=lambda q: (q[1]+.4*math.cos((q[0]-16)*math.pi/3), q[0]))
WEDGE_SET = set(WEDGE)
HOLES = [(16, 9, 1), (12, 14, 1), (20, 15, 1), (8, 17, .7), (16, 17, 1)]


def scene(amount, motion='hold', tick=0):
    im = canvas()
    px = im.load()
    sprite = canvas()
    d = ImageDraw.Draw(sprite)
    d.ellipse((11, 14, 21, 18), fill=FUR)
    for x in (9, 18):
        d.ellipse((x, 8, x+5, 13), fill=CREAM)
        d.ellipse((x+1, 9, x+4, 12), fill=(255, 173, 195))
    d.ellipse((10, 11, 22, 18), fill=CREAM)
    for x in (13, 18):
        d.rectangle((x, 12, x+1, 14), fill=INK)
        d.point((x, 12), fill=(255, 255, 248))
    d.point((16, 15), fill=(255, 150, 179))
    d.line([(11, 15), (12, 15)], fill=(248, 175, 169))
    d.line([(20, 15), (21, 15)], fill=(248, 175, 169))
    d.rectangle((15, 16, 17, 16), fill=INK)
    d.point((16, 17 if motion == 'eat' and tick % 4 < 2 else 16), fill=(255, 255, 248))
    for x in (11, 19):
        d.ellipse((x, 17, x+2, 18), fill=(255, 245, 224))
        d.point((x+1, 18), fill=(245, 192, 182))
    count = round(len(ORDER)*max(0, min(100, amount))/100)
    remaining = ORDER[len(ORDER)-count:] if count else []
    edge_y = min((y for x, y in remaining), default=19)
    for y in range(6, 19):
        for x in range(4, 29):
            c = sprite.getpixel((x, y))
            if c != (0, 0, 0) and (y < edge_y or (x, y) in WEDGE_SET):
                px[x, y] = c
    for x, y in remaining:
        px[x, y] = YELLOW
        for hx, hy, r in HOLES:
            if (x-hx)**2+(y-hy)**2 <= r*r:
                px[x, y] = HOLE
    if motion == 'eat' and tick % 3 and amount < 99:
        for x, y in ((5, 10), (26, 12)):
            px[x+tick % 2, y] = YELLOW
    return im.crop((4, 6, 29, 19))


def render(snapshot, page=0, amount=None, motion='hold', tick=0):
    im = canvas()
    px = im.load()
    claude = snapshot.services[0]
    amount = claude.limits[0] if amount is None else amount
    if amount is None:
        centered(px, 19, 4, '?', (94, 110, 133))
    else:
        art = scene(amount, motion, tick)
        if claude.stale:
            art = art.point(lambda v: int(v*.45))
        im.paste(art, (7, 0))
    logo(px, 2, 0, 0, claude.dim)
    text(px, 0, 7, '5H', (132, 151, 178))
    for k, cx in enumerate((13, 26)):
        logo(px, cx, 15, k, snapshot.services[k].dim)
    for row, (label, y) in enumerate((('5H', 19), ('WK', 26))):
        text(px, 0, y, label, (105, 123, 148))
        for k, cx in enumerate((13, 26)):
            svc = snapshot.services[k]
            centered(px, cx, y, word(svc, row), color(svc, row))
    for x in (12, 13, 14):
        px[x, 24] = (154, 175, 202)
    return finish(im, snapshot)
