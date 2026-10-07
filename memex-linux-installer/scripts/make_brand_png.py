#!/usr/bin/env python3
"""Dev-only: derive brand PNGs from packaging/branding/mepc-logo-source.png (needs Pillow)."""
import statistics
from pathlib import Path

from PIL import Image

BRANDING = Path(__file__).resolve().parents[1] / 'packaging/branding'
SOURCE = BRANDING / 'mepc-logo-source.png'
FRAME = 6          # px of grey frame to drop on every side
PAD = 6
SIZE = 256


def is_gold(p):
    r, g, b = p[:3]
    return r > 150 and g > 100 and b < 120 and r - b > 100


def sample_gold(img):
    data = img.tobytes()
    px = [q for q in zip(data[0::3], data[1::3], data[2::3]) if is_gold(q)]
    return tuple(int(statistics.median(c[i] for c in px)) for i in range(3))


def with_alpha(img, gold):
    """Alpha = distance from black relative to the brightest channel (smooth edges); colour kept."""
    out = Image.new('RGBA', img.size)
    src, dst = img.convert('RGB').load(), out.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = src[x, y]
            a = min(255, round(max(r, g, b) * 255 / max(gold)))
            if a < 12:
                continue
            dst[x, y] = (min(255, r * 255 // a), min(255, g * 255 // a), min(255, b * 255 // a), a)
    return out


def main():
    img = Image.open(SOURCE).convert('RGB')
    w, h = img.size
    img = img.crop((FRAME, FRAME, w - FRAME, h - FRAME))
    gold = sample_gold(img)
    print('gold: #%02x%02x%02x  (38;2;%d;%d;%d)' % (*gold, *gold))
    rgba = with_alpha(img, gold)

    # emblem: bbox of gold pixels
    xs, ys = [], []
    for y in range(img.height):
        for x in range(img.width):
            if is_gold(img.getpixel((x, y))):
                xs.append(x); ys.append(y)
    box = (max(min(xs) - PAD, 0), max(min(ys) - PAD, 0),
           min(max(xs) + PAD + 1, img.width), min(max(ys) + PAD + 1, img.height))
    emblem = rgba.crop(box)
    side = max(emblem.size)
    canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    canvas.paste(emblem, ((side - emblem.width) // 2, (side - emblem.height) // 2))
    canvas.resize((SIZE, SIZE), Image.LANCZOS).save(BRANDING / 'memxos-logo.png', optimize=True)


if __name__ == '__main__':
    main()
