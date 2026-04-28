"""
Generate authentic-looking tile images as PNGs using PIL.

Traditional mahjong styling:
- Man tiles: Chinese number characters (one-nine) + Wan in red
- Pin tiles: Programmatic circle pip patterns (like traditional dots/coins)
- Sou tiles: Programmatic bamboo stalk patterns
- Honor/Bonus tiles: Large CJK glyphs

Run this once (or the first time the game starts) to populate ../assets/tiles.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..game.tiles import (
    ALL_TILES, DRAGON_GLYPHS, DRAGON_NAMES, FLOWER_GLYPHS, FLOWER_NAMES,
    SEASON_GLYPHS, SEASON_NAMES, SUIT_GLYPH, Suit, Tile,
    WIND_GLYPHS, WIND_NAMES,
)

# palette
IVORY       = (248, 238, 212)
IVORY_DARK  = (225, 210, 175)
IVORY_LIGHT = (255, 252, 238)
BACK_GREEN  = (22, 98, 58)

RED    = (180, 20, 20)
BLACK  = (28, 22, 22)
GREEN  = (28, 128, 48)
BLUE   = (30, 60, 160)

PIN_OUTER     = (15, 95, 35)
PIN_FILL      = (55, 158, 70)
PIN_RED_OUTER = (140, 15, 15)
PIN_RED_FILL  = (210, 50, 50)

BAM_OUTER = (10,  80, 20)
BAM_FILL  = (45, 140, 55)
BAM_LIGHT = (90, 195, 85)
BAM_NODE  = (155, 215, 105)

# sizing
TILE_W   = 96
TILE_H   = 128
BEVEL    = 6
CORNER_R = 10

_CX = 2 + TILE_W // 2   # 50
_CY = 2 + TILE_H // 2   # 66

MAN_CHARS = ["\u4e00", "\u4e8c", "\u4e09", "\u56db", "\u4e94",
             "\u516d", "\u4e03", "\u516b", "\u4e5d"]

_PIN_PIPS = {
    1: ([(0,   0)],                                                               24),
    2: ([(0, -25),  (0,  25)],                                                    17),
    3: ([(0, -27),  (0,   0),  (0,  27)],                                         14),
    4: ([(-19, -20), (19, -20), (-19, 20), ( 19,  20)],                           14),
    5: ([(-20, -22), (20, -22), (  0,  0), (-20,  22), ( 20,  22)],              12),
    6: ([(-20, -26), (20, -26), (-20,  0), ( 20,   0), (-20,  26), (20, 26)],    12),
    7: ([(0, -36), (-20, -16), (20, -16), (0, 2), (-20, 20), (20, 20), (0, 38)], 10),
    8: ([(-20, -36), (20, -36), (-20, -12), (20, -12),
         (-20,  12), (20,  12), (-20,  36), (20,  36)],                           10),
    9: ([(-26, -34), (0, -34), (26, -34),
         (-26,   0), (0,   0), (26,   0),
         (-26,  34), (0,  34), (26,  34)],                                         9),
}

_SOU_STALK = {
    1: (22, 52), 2: (17, 44), 3: (15, 38),
    4: (14, 32), 5: (13, 28), 6: (12, 26),
    7: (11, 24), 8: (10, 22), 9: (10, 20),
}


def _font_has_cjk(font):
    try:
        bbox = font.getbbox("\u842c")
        return bbox[2] - bbox[0] > 2
    except Exception:
        return False


def _find_cjk_font(size):
    cjk_candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for p in cjk_candidates:
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                if _font_has_cjk(f):
                    return f, True
            except Exception:
                continue

    latin_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for p in latin_candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size), False
            except Exception:
                continue
    return ImageFont.load_default(), False


def _cjk_font(size):
    return _find_cjk_font(size)[0]


def _tile_base():
    shadow = Image.new("RGBA", (TILE_W + 8, TILE_H + 8), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (4, 4, TILE_W + 4, TILE_H + 4),
        radius=CORNER_R, fill=(0, 0, 0, 110),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))

    final = Image.new("RGBA", (TILE_W + 8, TILE_H + 8), (0, 0, 0, 0))
    final.alpha_composite(shadow, (0, 0))

    body = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    db = ImageDraw.Draw(body)
    db.rounded_rectangle((0, 0, TILE_W, TILE_H), radius=CORNER_R, fill=IVORY)
    db.rounded_rectangle(
        (BEVEL, BEVEL, TILE_W - BEVEL, TILE_H - BEVEL),
        radius=CORNER_R - 2, outline=IVORY_DARK, width=1,
    )
    db.line(
        [(BEVEL + 2, BEVEL + 1), (TILE_W - BEVEL - 2, BEVEL + 1)],
        fill=IVORY_LIGHT, width=1,
    )
    final.alpha_composite(body, (2, 2))
    return final


def _center_text(img, text, font, fill, dy=0):
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (img.width - w) // 2 - bbox[0]
    y = (img.height - h) // 2 - bbox[1] + dy
    d.text((x, y), text, font=font, fill=fill)


def _draw_pip_circle(d, cx, cy, r, outer, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=outer)
    ir = max(2, r - 3)
    d.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], fill=fill)
    hr = max(1, r // 5)
    hx = cx - ir // 3
    hy = cy - ir // 3
    d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=(230, 248, 225))


def _draw_bamboo_stalk(d, cx, cy, w, h, red_cap=False):
    x0, y0 = cx - w // 2, cy - h // 2
    x1, y1 = cx + w // 2, cy + h // 2
    r = max(3, w // 3)
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=BAM_FILL)
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=BAM_OUTER, width=1)
    sw = max(2, w // 3)
    d.rounded_rectangle([x0 + 2, y0 + 3, x0 + sw + 1, y1 - 3],
                        radius=r // 2, fill=BAM_LIGHT)
    n1 = y0 + h // 3
    n2 = y0 + 2 * h // 3
    d.line([(x0 + 1, n1), (x1 - 1, n1)], fill=BAM_NODE, width=1)
    d.line([(x0 + 1, n2), (x1 - 1, n2)], fill=BAM_NODE, width=1)
    if red_cap:
        cr = max(4, w // 2)
        cap_y = cy - h // 2
        d.ellipse([cx - cr, cap_y - cr, cx + cr, cap_y + cr],
                  fill=(195, 35, 35))


def _render_man(img, tile):
    font_big, has_cjk = _find_cjk_font(52)
    font_small, _ = _find_cjk_font(28)
    if has_cjk:
        numeral = MAN_CHARS[tile.value - 1]
        _center_text(img, numeral, font_big, RED, dy=-20)
        _center_text(img, "\u842c", font_small, RED, dy=28)
    else:
        font_num, _ = _find_cjk_font(58)
        _center_text(img, str(tile.value), font_num, RED, dy=-22)
        _center_text(img, "Wan", font_small, RED, dy=30)


def _render_pin(img, tile):
    d = ImageDraw.Draw(img)
    positions, radius = _PIN_PIPS[tile.value]
    for i, (dx, dy) in enumerate(positions):
        cx, cy = _CX + dx, _CY + dy
        if tile.value == 1 or (tile.value == 5 and i == 2):
            outer, fill = PIN_RED_OUTER, PIN_RED_FILL
        else:
            outer, fill = PIN_OUTER, PIN_FILL
        _draw_pip_circle(d, cx, cy, radius, outer, fill)


def _render_sou(img, tile):
    d = ImageDraw.Draw(img)
    positions, _ = _PIN_PIPS[tile.value]
    sw, sh = _SOU_STALK[tile.value]
    for i, (dx, dy) in enumerate(positions):
        cx, cy = _CX + dx, _CY + dy
        _draw_bamboo_stalk(d, cx, cy, sw, sh, red_cap=(tile.value == 1 and i == 0))


def _render_honor(img, tile):
    font_big, has_cjk = _find_cjk_font(68)
    font_small, _ = _find_cjk_font(30)
    if tile.suit == Suit.WIND:
        glyph = WIND_GLYPHS[tile.value] if has_cjk else WIND_NAMES[tile.value][0]
        color = BLACK
    elif tile.suit == Suit.DRAGON:
        glyph = DRAGON_GLYPHS[tile.value] if has_cjk else DRAGON_NAMES[tile.value][0] + "D"
        color = RED if tile.value == 0 else GREEN if tile.value == 1 else BLACK
    elif tile.suit == Suit.FLOWER:
        glyph = FLOWER_GLYPHS[tile.value] if has_cjk else "F"
        color = GREEN
        _center_text(img, glyph, font_big, color, dy=-6)
        _center_text(img, str(tile.value + 1), font_small, BLACK, dy=40)
        return
    elif tile.suit == Suit.SEASON:
        glyph = SEASON_GLYPHS[tile.value] if has_cjk else "S"
        color = BLUE
        _center_text(img, glyph, font_big, color, dy=-6)
        _center_text(img, str(tile.value + 1), font_small, BLACK, dy=40)
        return
    else:
        glyph = "?"
        color = BLACK
    _center_text(img, glyph, font_big, color, dy=0)


def render_tile(tile):
    img = _tile_base()
    if tile.suit == Suit.MAN:
        _render_man(img, tile)
    elif tile.suit == Suit.PIN:
        _render_pin(img, tile)
    elif tile.suit == Suit.SOU:
        _render_sou(img, tile)
    else:
        _render_honor(img, tile)
    return img


def render_tile_back():
    shadow = Image.new("RGBA", (TILE_W + 8, TILE_H + 8), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((4, 4, TILE_W + 4, TILE_H + 4),
                          radius=CORNER_R, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))

    img = Image.new("RGBA", (TILE_W + 8, TILE_H + 8), (0, 0, 0, 0))
    img.alpha_composite(shadow, (0, 0))

    body = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    db = ImageDraw.Draw(body)
    db.rounded_rectangle((0, 0, TILE_W, TILE_H), radius=CORNER_R, fill=BACK_GREEN)
    for y in range(12, TILE_H - 12, 20):
        for x in range(12, TILE_W - 12, 20):
            db.polygon(
                [(x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y)],
                outline=(255, 255, 255, 70),
            )
    img.alpha_composite(body, (2, 2))
    return img


def generate_all(out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    seen = set()
    for t in ALL_TILES:
        key = (t.suit, t.value)
        if key in seen:
            continue
        seen.add(key)
        img = render_tile(t)
        img.save(out_dir / "{}.png".format(t.to_id().replace(":", "_")))
    render_tile_back().save(out_dir / "back.png")
    print("wrote {} tile images to {}".format(len(seen) + 1, out_dir))


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent
    generate_all(here / "assets" / "tiles")
