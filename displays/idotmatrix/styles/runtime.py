"""Validated style selection and presentation plans. No Bluetooth or account access."""
from dataclasses import dataclass
import json
from pathlib import Path
from styles import STYLE_IDS, renderer

DEFAULT_CONFIG = Path.home() / '.usage-battery' / 'idotmatrix-style.json'
PAGED = ('big-jewels', 'service-spotlight')


@dataclass(frozen=True)
class Settings:
    style: str = 'legacy'
    page: int = 0
    rotate: bool = False
    seconds: float = 3.0

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError('Style settings must be an object')
        style = data.get('style', 'legacy')
        if style not in (*STYLE_IDS, 'legacy'):
            raise ValueError('Unknown style; keeping previous selection')
        page = data.get('page', 0)
        rotate = data.get('rotate', False)
        seconds = data.get('seconds', 3)
        if type(page) is not int or page not in (0, 1):
            raise ValueError('page must be 0 or 1')
        if type(rotate) is not bool:
            raise ValueError('rotate must be true or false')
        if type(seconds) not in (float, int) or not 1 <= seconds <= 60:
            raise ValueError('seconds must be between 1 and 60')
        if style not in PAGED and (page != 0 or rotate):
            raise ValueError('Only big-jewels and service-spotlight have multiple pages')
        return cls(style, page, rotate, float(seconds))


def read_settings(path=DEFAULT_CONFIG, fallback=Settings()):
    try:
        return Settings.from_dict(json.loads(Path(path).read_text())), None
    except FileNotFoundError:
        return Settings(), None  # deleting the selector restores legacy
    except (OSError, ValueError, TypeError) as exc:
        return fallback, str(exc)


@dataclass
class Presentation:
    frames: list
    durations_ms: list
    loop: bool = False
    # A transient GIF must be replaced by this PNG, even if firmware ignores GIF loop metadata.
    settle: object = None

    @property
    def seconds(self):
        return sum(self.durations_ms)/1000


class StyleSession:
    def __init__(self):
        self.previous = None
        self.settings = None

    def plan(self, snapshot, settings):
        render = renderer(settings.style)
        previous = self.previous if settings == self.settings else None
        self.previous, self.settings = snapshot, settings
        final = render(snapshot, page=settings.page)
        if settings.rotate:
            return Presentation([render(snapshot, page=i) for i in (0, 1)],
                                [round(settings.seconds*1000)]*2, loop=True)
        if settings.style == 'baby-mochi' and previous and snapshot.fresh_claude and previous.fresh_claude:
            old = previous.services[0].limits[0]
            new = snapshot.services[0].limits[0]
            if old is not None and new is not None and old != new:
                # 0.84 s nibble on decreases; 0.60 s refill on increases/reset.
                count, motion = (14, 'eat') if new < old else (10, 'refill')
                frames = [render(snapshot, amount=old+(new-old)*i/(count-1), motion=motion, tick=i)
                          for i in range(count)]
                return Presentation(frames, [60]*count, settle=final)
        return Presentation([final], [0])
