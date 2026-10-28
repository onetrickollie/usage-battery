"""Allowlisted local renderers, not arbitrary executable paths from configuration."""
from functools import lru_cache
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STYLE_IDS = ('spectrum', 'diamonds', 'broken-arcs', 'big-jewels', 'service-spotlight', 'baby-mochi')


def metadata(style):
    if style not in STYLE_IDS:
        raise ValueError('Unknown style')
    return json.loads((ROOT / style / 'style.json').read_text())


@lru_cache(maxsize=6)
def renderer(style):
    if style not in STYLE_IDS:
        raise ValueError('Unknown style')
    spec = importlib.util.spec_from_file_location('styles._' + style.replace('-', '_'), ROOT / style / 'render.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render
