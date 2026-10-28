"""Reproducible, synthetic GitHub previews. No live usage, credentials, or Bluetooth."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from styles import STYLE_IDS, metadata, renderer
from styles.common import normalize, led_preview
from styles.runtime import Settings, StyleSession


def sample(cf=65, cw=23, xf=54, xw=82, credits=False):
    return normalize([
        {'name': 'Claude', 'age_seconds': 0, 'meters': [
            {'label': '5-hour session', 'left': cf}, {'label': 'Weekly (all models)', 'left': cw}]},
        {'name': 'ChatGPT / Codex', 'age_seconds': 0, 'credits': {'available': credits}, 'meters': [
            {'label': '5-hour session', 'left': xf}, {'label': 'Weekly', 'left': xw}]}])


def export(style, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    render = renderer(style)
    still = render(sample(cf=35))
    still.save(directory / 'preview-32.png')
    led_preview(still).save(directory / 'preview.png')
    frames, times = [], []
    if style == 'baby-mochi':
        session = StyleSession()
        settings = Settings(style)
        for snap in (sample(100, 92), sample(72, 89), sample(72, 86, 48, 79),
                     sample(35, 80, 43, 77), sample(5, 74, 35, 76), sample(0, 72, 35, 76), sample(100, 72, 35, 76)):
            plan = session.plan(snap, settings)
            if plan.settle:
                frames.extend(plan.frames)
                times.extend(plan.durations_ms)
                frames.append(plan.settle)
                times.append(1600)
            else:
                frames.extend(plan.frames)
                times.extend([1800]*len(plan.frames))
    elif metadata(style)['pages']:
        frames = [render(sample(), page=i) for i in (0, 1)]
        times = [3000, 3000]
    else:
        frames = [render(snap) for snap in (sample(), sample(100, 57, 0, 54, True), sample(1, 23, 54, 82))]
        times = [2000]*3
    enlarged = [led_preview(frame, 8) for frame in frames]
    enlarged[0].save(directory / 'demo.gif', save_all=True, append_images=enlarged[1:],
                     duration=times, loop=0, disposal=2)
    return still


def export_all(root=None):
    root = Path(root) if root else Path(__file__).resolve().parent
    images = [export(style, root/style) for style in STYLE_IDS]
    # Pillow's bundled font keeps generation portable (no macOS font dependency).
    font = ImageFont.load_default(size=18)
    small = ImageFont.load_default(size=13)
    gallery = Image.new('RGB', (936, 746), (15, 18, 23))
    d = ImageDraw.Draw(gallery)
    d.text((24, 18), 'Usage Battery / six switchable styles', fill=(235, 240, 248), font=font)
    d.text((24, 48), 'Synthetic examples. Baby Mochi follows Claude 5H; all four readings remain visible.', fill=(150, 170, 192), font=small)
    for i, (style, im) in enumerate(zip(STYLE_IDS, images)):
        x, y = 24+(i % 3)*304, 88+(i//3)*324
        d.text((x, y), metadata(style)['title'], fill=(235, 220, 170) if style == 'baby-mochi' else (220, 232, 246), font=font)
        gallery.paste(led_preview(im, 8), (x, y+30))
    gallery.save(root/'gallery.png')
