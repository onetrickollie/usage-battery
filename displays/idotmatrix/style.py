#!/usr/bin/env python3
"""List, preview, or atomically select a local display style. Never sends Bluetooth data."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from styles import STYLE_IDS, metadata
from styles.runtime import DEFAULT_CONFIG, Settings, read_settings


def save_settings(path, settings):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.style-', delete=False) as f:
            name = f.name
            json.dump(asdict(settings), f, indent=2)
            f.write('\n')
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('style', nargs='?', choices=(*STYLE_IDS, 'legacy'))
    p.add_argument('--list', action='store_true', help='List styles without changing settings')
    p.add_argument('--page', help='big-jewels: 5h/week; service-spotlight: claude/codex')
    p.add_argument('--rotate', action='store_true', help='Opt into continuous page rotation (paged styles only)')
    p.add_argument('--seconds', type=float, default=3, help='Seconds per page when rotation is enabled')
    p.add_argument('--config', type=Path, default=DEFAULT_CONFIG, help='Alternate selector file, e.g. for tests')
    p.add_argument('--preview', action='store_true', help='Generate synthetic previews without selecting this style')
    p.add_argument('--output', type=Path, help='Required with --preview: destination for PNG/GIF previews')
    args = p.parse_args()
    if args.list or args.style is None:
        current, error = read_settings(args.config)
        print('Selected:', current.style)
        if error:
            print('Selector could not be read; bridge keeps its last valid selection.')
        for style in STYLE_IDS:
            print(f'  {style:20} {metadata(style)["description"]}')
        print('  legacy               Original battery layout / rollback')
        return
    pages = metadata(args.style)['pages'] if args.style != 'legacy' else []
    if args.page and args.page not in pages:
        p.error('--page must be one of: ' + (', '.join(pages) or '(this style has no pages)'))
    try:
        settings = Settings.from_dict({'style': args.style, 'page': pages.index(args.page) if args.page else 0,
                                       'rotate': args.rotate, 'seconds': args.seconds})
    except ValueError as exc:
        p.error(str(exc))
    if args.preview:
        if not args.output or args.style == 'legacy':
            p.error('--preview requires a new style and --output DIRECTORY')
        from styles.previews import export
        export(args.style, args.output)
        print('Preview saved; selection unchanged:', args.output)
        return
    if args.output:
        p.error('--output requires --preview')
    save_settings(args.config, settings)
    print(f'Selected {settings.style}. A bridge with style support picks this up at its next refresh (within 60 seconds).')
    print('Saved:', args.config)


if __name__ == '__main__':
    main()
