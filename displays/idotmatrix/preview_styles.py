#!/usr/bin/env python3
"""Regenerate all six synthetic previews without contacting the hub or panel."""
import argparse
from styles.previews import export_all

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', help='Optional alternate output folder; default: styles/')
    args = p.parse_args()
    export_all(args.output)
    print('Generated six style previews and gallery.png from synthetic data.')
