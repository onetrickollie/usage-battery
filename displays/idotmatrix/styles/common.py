"""Shared hub-data normalization and pixel drawing; never accesses accounts or Bluetooth."""
from dataclasses import dataclass, field
import math
from PIL import Image
from render import text, text_width, shade, fade, led_preview

LABEL = (94, 110, 133)
TRACK = (23, 29, 39)
LOGOS = (("101 010 101", (230, 125, 90)), ("111 101 111", (100, 160, 255)))
NAMES = ("Claude", "ChatGPT / Codex")


@dataclass(frozen=True)
class Service:
    # Fixed ordering: 5-hour, weekly (all models). None means unknown, never zero.
    limits: tuple = (None, None)
    credits: bool = False
    stale: bool = False
    present: bool = False

    @property
    def dim(self):
        return .45 if self.stale else 1.0


@dataclass(frozen=True)
class Snapshot:
    services: tuple = field(default_factory=lambda: (Service(), Service()))
    offline: bool = False

    @property
    def fresh_claude(self):
        return self.services[0].present and not self.services[0].stale and not self.offline


def percent(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        return None
    return round(max(0, min(100, value)))


def normalize(services, stale_names=(), offline=False):
    """Always reserve Claude's left slot and Codex's right slot, even if one is absent."""
    out = []
    for index, name in enumerate(NAMES):
        svc = next((s for s in services if isinstance(s, dict) and
                    (s.get('name') == name or (index == 1 and 'codex' in str(s.get('name', '')).lower()))), None)
        if svc is None:
            out.append(Service())
            continue
        meters = [m for m in (svc.get('meters') or []) if isinstance(m, dict)]
        five = next((m for m in meters if str(m.get('label', '')).lower().startswith('5-hour')), {})
        weekly = [m for m in meters if str(m.get('label', '')).lower().startswith('weekly')]
        week = next((m for m in weekly if '(' not in m['label'] or 'all models' in m['label'].lower()), {})
        # Never silently substitute an Opus/Sonnet-specific limit for the all-model weekly value.
        credits = svc.get('credits') or {}
        age = svc.get('age_seconds')
        stale = svc.get('name') in stale_names or (isinstance(age, (int, float)) and age > 180)
        out.append(Service((percent(five.get('left')), percent(week.get('left'))),
                           index == 1 and bool(credits.get('available')), stale, True))
    return Snapshot(tuple(out), offline)


def canvas():
    return Image.new('RGB', (32, 32))


def centered(px, cx, y, word, color):
    word = str(word)
    width = text_width(word)
    x = cx - (width - 1) // 2
    if x < 0 or x + width > 32 or y < 0 or y + 5 > 32:
        raise ValueError('Text exceeds the 32x32 display')
    text(px, x, y, word, color)


def word(service, row):
    n = service.limits[row]
    return '?' if n is None else 'CR' if n == 0 and service.credits else str(n)


def color(service, row):
    n = service.limits[row]
    return shade(LABEL if n is None else fade(n / 100), service.dim)


def logo(px, cx, y, index, dim=1.0):
    pattern, col = LOGOS[index]
    for r, line in enumerate(pattern.split()):
        for c, bit in enumerate(line):
            if bit == '1':
                px[cx - 1 + c, y + r] = shade(col, dim)


def finish(im, snapshot):
    """Reserved top-right 2x2 indicator: yellow = old; red = hub offline."""
    col = (255, 40, 30) if snapshot.offline else (255, 175, 0) if any(s.stale for s in snapshot.services) else None
    if col:
        for x, y in ((30, 0), (31, 0), (30, 1), (31, 1)):
            im.putpixel((x, y), col)
    return im


def gauge(px, cx, cy, service, row, index, kind='ring', radius=4.5):
    n = service.limits[row]
    for y in range(max(0, math.floor(cy-radius)), min(32, math.ceil(cy+radius)+1)):
        for x in range(max(0, math.floor(cx-radius)), min(32, math.ceil(cx+radius)+1)):
            dx, dy = x-cx, y-cy
            r = math.hypot(dx, dy)
            turn = math.atan2(dx, -dy) % (2*math.pi) / (2*math.pi)
            inside = radius-1.5 <= abs(dx)+abs(dy) <= radius if kind == 'diamond' else radius-1.8 <= r <= radius
            if kind == 'dashed' and min(abs(dx), abs(dy)) == 0:
                inside = False
            if inside:
                px[x, y] = shade(fade(turn) if n is not None and turn < n/100 else TRACK, service.dim)
    logo(px, cx, cy-1, index, service.dim)


def four(snapshot, kind):
    im = canvas()
    px = im.load()
    for row, name in enumerate(('5H', 'WK')):
        text(px, 0, 3+16*row, name, LABEL)
        for k, cx in enumerate((13, 26)):
            svc = snapshot.services[k]
            gauge(px, cx, 5+16*row, svc, row, k, kind, 5 if kind == 'diamond' else 4.5)
            centered(px, cx, 11+16*row, word(svc, row), color(svc, row))
    return finish(im, snapshot)
