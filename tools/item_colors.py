#!/usr/bin/env python3
"""Write prototypes/y_item_colors.lua: the color of each Yuoki item, read from its icon.

Factorio items have no color of their own, and mods cannot read icon pixels while
loading, so this computes the colors from the icons ahead of time. Pass one or more
`factorio --dump-data` outputs (script-output/data-raw-dump.json) made with Yuoki
enabled, for example one with base only and one with Space Age; every Yuoki item in
any of them is listed. Rerun it when an item or its icon changes.

An icon's color is the average of its visible pixels, leaving out the darkest 30%
(outline and shading) and the brightest 5% (highlights). Clearly colored icons are
then made more saturated and at least mid-bright, so a dark brown block still reads
as brown; grey and black icons keep their color.
"""
import argparse
import colorsys
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'prototypes' / 'y_item_colors.lua'
MOD = '__Yuoki__/'
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def read_png(path):
    """Rows of (r, g, b, a) tuples from 0 to 1."""
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f'{path}: not a PNG')
    pos, idat, palette, transparency = 8, b'', None, b''
    while pos < len(data):
        (length,) = struct.unpack('>I', data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b'IHDR':
            width, height, depth, color_type, _, _, interlace = struct.unpack('>IIBBBBB', body)
        elif kind == b'PLTE':
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif kind == b'tRNS':
            transparency = body
        elif kind == b'IDAT':
            idat += body
    if interlace or depth not in (8, 16) or color_type not in CHANNELS:
        raise ValueError(f'{path}: unsupported PNG (depth {depth}, color type {color_type}, interlace {interlace})')
    channels = CHANNELS[color_type]
    step = channels * depth // 8
    stride = width * step
    raw = zlib.decompress(idat)
    rows, previous, pos = [], bytearray(stride), 0
    for _ in range(height):
        kind, line = raw[pos], bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            left = line[i - step] if i >= step else 0
            up = previous[i]
            corner = previous[i - step] if i >= step else 0
            if kind == 1:
                line[i] = (line[i] + left) & 255
            elif kind == 2:
                line[i] = (line[i] + up) & 255
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 255
            elif kind == 4:
                guess = left + up - corner
                nearest = min((abs(guess - left), 0, left), (abs(guess - up), 1, up), (abs(guess - corner), 2, corner))
                line[i] = (line[i] + nearest[2]) & 255
        previous = line
        row = []
        for x in range(width):
            values = [line[x * step + k * depth // 8] / 255 for k in range(channels)]
            if color_type == 6:
                row.append(tuple(values))
            elif color_type == 2:
                row.append((*values, 1.0))
            elif color_type == 4:
                row.append((values[0], values[0], values[0], values[1]))
            elif color_type == 0:
                row.append((values[0], values[0], values[0], 1.0))
            else:
                index = line[x]
                alpha = transparency[index] / 255 if index < len(transparency) else 1.0
                row.append((*(c / 255 for c in palette[index]), alpha))
        rows.append(row)
    return rows


def icon_color(prototype):
    layers = prototype.get('icons') or [{'icon': prototype.get('icon'), 'icon_size': prototype.get('icon_size')}]
    layer = layers[0]
    rows = read_png(ROOT / layer['icon'][len(MOD):])
    size = min(layer.get('icon_size') or prototype.get('icon_size') or 64, len(rows), len(rows[0]))
    tint = layer.get('tint') or {}
    if isinstance(tint, list):
        tint = dict(zip('rgb', tint))
    tint = [tint.get(key, 1) for key in 'rgb']
    if max(tint) > 1:
        tint = [value / 255 for value in tint]
    pixels = [
        [pixel[k] * tint[k] for k in range(3)] for row in rows[:size] for pixel in row[:size] if pixel[3] > 0.5
    ]
    if not pixels:
        return None
    pixels.sort(key=lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])
    kept = pixels[int(len(pixels) * 0.3):max(int(len(pixels) * 0.95), int(len(pixels) * 0.3) + 1)]
    average = [sum(c[k] for c in kept) / len(kept) for k in range(3)]
    hue, saturation, value = colorsys.rgb_to_hsv(*average)
    if saturation < 0.5:
        saturation += (0.5 - saturation) * min(1, max(0, (saturation - 0.12) / 0.12))
    value += max(0, 0.55 - value) * min(1, max(0, (saturation - 0.15) / 0.25))
    return colorsys.hsv_to_rgb(hue, saturation, value)


def yuoki_items(dumps):
    items = {}
    for dump in dumps:
        for prototypes in json.loads(Path(dump).read_text()).values():
            if not isinstance(prototypes, dict):
                continue
            for name, prototype in prototypes.items():
                if not isinstance(prototype, dict) or 'stack_size' not in prototype:
                    continue
                layers = prototype.get('icons') or [{'icon': prototype.get('icon') or ''}]
                if (layers[0].get('icon') or '').startswith(MOD):
                    items[name] = prototype
    return items


def render(colors):
    lines = [
        '-- Generated by tools/item_colors.py from the item icons; rerun it rather than editing by hand.',
        '-- Factorio items have no color of their own. Mods that color things by the item they carry',
        '-- (Jat\'z Distribution\'s freighters, for one) read this declaration: a mod-data prototype with',
        '-- data_type "item-colors" and data.items[item] = Color.',
        'data:extend({',
        '  {',
        '    type = "mod-data",',
        '    name = "yuoki-item-colors",',
        '    data_type = "item-colors",',
        '    data = {',
        '      items = {',
    ]
    for name in sorted(colors):
        r, g, b = colors[name]
        lines.append(f'        ["{name}"] = {{ r = {r:.2f}, g = {g:.2f}, b = {b:.2f} }},')
    lines += ['      },', '    },', '  },', '})', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('dumps', nargs='+', help='data-raw-dump.json files from factorio --dump-data with Yuoki')
    args = parser.parse_args()
    colors = {}
    for name, prototype in yuoki_items(args.dumps).items():
        color = icon_color(prototype)
        if color:
            colors[name] = color
    OUTPUT.write_text(render(colors))
    print(f'Wrote {len(colors)} item colors to {OUTPUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
