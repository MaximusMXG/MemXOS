#!/usr/bin/env python3
"""Crop the ME ASCII logo and block-sample a small version for fastfetch."""
import sys
from pathlib import Path

BRANDING = Path(__file__).resolve().parents[1] / 'packaging/branding'
TARGET_WIDTH = 38
DENSE, MEDIUM, SPARSE = 0.55, 0.30, 0.12


def crop(lines):
    width = max(map(len, lines))
    grid = [line.rstrip('\n').ljust(width) for line in lines]
    while grid and not grid[0].strip():
        grid.pop(0)
    while grid and not grid[-1].strip():
        grid.pop()
    left = min(len(r) - len(r.lstrip()) for r in grid if r.strip())
    right = max(len(r.rstrip()) for r in grid)
    return [r[left:right] for r in grid]


def shrink(grid, target=TARGET_WIDTH):
    factor = max(1, -(-len(grid[0]) // target))
    out = []
    for y in range(0, len(grid), factor):
        row = ''
        for x in range(0, len(grid[0]), factor):
            block = [grid[j][i] for j in range(y, min(y + factor, len(grid)))
                     for i in range(x, min(x + factor, len(grid[0])))]
            density = sum(c != ' ' for c in block) / len(block)
            row += '@' if density >= DENSE else '%' if density >= MEDIUM else '*' if density >= SPARSE else ' '
        out.append(row.rstrip())
    return out


def main():
    grid = crop((BRANDING / 'me-logo-source.txt').read_text().splitlines())
    large = '\n'.join(r.rstrip() for r in grid) + '\n'
    small = '\n'.join(shrink(grid)) + '\n'
    (BRANDING / 'memxos-logo-large.txt').write_text(large)
    (BRANDING / 'memxos-logo.txt').write_text(small)
    sys.stdout.write(large + '\n' + small)


if __name__ == '__main__':
    main()
