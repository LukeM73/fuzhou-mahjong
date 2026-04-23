"""
Generate authentic-looking tile images as PNGs using PIL.

Styling: ivory body with rounded corners, a subtle beveled inset,
red/black/green CJK characters matching traditional mahjong conventions.

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


# ---------------------------------------------------------------- colours
IVORY = (248, 238, 212)           # warm off-white tile face
IVORY_DARK = (225, 210, 175)      # shading on the bevel
IVORY_LIGHT = (255, 252, 238)     # highlight
BACK_GREEN = (22, 98, 58)         # tile back / mahjong felt colour

RED = (180, 20, 20)
BLACK = (28, 22, 22)
GREEN = (28, 128, 48)
BLUE = (30, 60, 160)

# ---------------------------------------------------------------- sizing
TILE_W = 96
TILE_H = 128
BEVEL = 6
CORNER_R = 10


def _font_has_cjk(font: ImageFont.FreeTypeFont) -> bool:
    """Cheap probe: does this font have glyphs for the tile-face characters?"""
    try:
        bbox = font.getbbox("萬")
        # Missing glyphs in truetype tend to bbox=0 width.
        return bbox[2] - bbox[0] > 2
    except Exception:
        return False


def _find_cjk_font(size: int) -> Tuple[ImageFont.FreeTypeFont, bool]:
    """Pick any CJK-capable font the system happens to have.

    Returns (font, has_cjk).  When no CJK font is available we still return a
    Latin font so tiles can be rendered with romanized labels as a fallback.
    """
    cjk_candidates = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        # Windows
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

    # Fallback: any Latin TTF we can find.
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


def _cjk_font(size: int) -> ImageFont.FreeTypeFont:
    """Back-compat shim for callers that just want a font."""
    return _find_cjk_font(size)[0]


def _tile_base() -> Image.Image:
    """Blank tile face with rounded corners + gentle beveled edge."""
    img = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Outer shadow.
    shadow = Image.new("RGBA", (TILE_W + 8, TILE_H + 8), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (4, 4, TILE_W + 4, TILE_H + 4),
        radius=CORNER_R, fill=(0, 0, 0, 110),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))

    final = Image.new("RGBA", (TILE_W + 8, TILE_H + 8), (0, 0, 0, 0))
    final.alpha_composite(shadow, (0, 0))

    # Body.
    body = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    db = ImageDraw.Draw(body)
    db.rounded_rectangle((0, 0, TILE_W, TILE_H), radius=CORNER_R, fill=IVORY)
    # Inset bevel.
    db.rounded_rectangle(
        (BEVEL, BEVEL, TILE_W - BEVEL, TILE_H - BEVEL),
        radius=CORNER_R - 2, outline=IVORY_DARK, width=1,
    )
    # Top highlight
    db.line([(BEVEL + 2, BEVEL + 1), (TILE_W - BEVEL - 2, BEVEL + 1)],
            fill=IVORY_LIGHT, width=1)
    final.alpha_composite(body, (2, 2))
    return final


def _center_text(img: Image.Image, text: str, font: ImageFont.FreeTypeFont,
                 fill: Tuple[int, int, int], dy: int = 0) -> None:
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (img.width - w) // 2 - bbox[0]
    y = (img.height - h) // 2 - bbox[1] + dy
    d.text((x, y), text, font=font, fill=fill)


def _render_suit_pips(img: Image.Image, tile: Tile) -> None:
    """For number suits, draw the number on top and the suit glyph on bottom."""
    top_color = RED if tile.suit == Suit.MAN and tile.value in (1, 5, 9) else BLACK
    if tile.suit == Suit.PIN:
        top_color = BLUE if tile.value == 5 else BLACK
    if tile.suit == Suit.SOU:
        # 1-sou traditionally a red bird, 5-sou central red.  We keep it
        # simple: red on 1 and 5, green otherwise.
        top_color = RED if tile.value in (1, 5) else GREEN

    font_number, _ = _find_cjk_font(56)
    font_suit, has_cjk = _find_cjk_font(34)

    # Top: the value as an Arabic or kanji-style number.
    label = str(tile.value)
    _center_text(img, label, font_number, top_color, dy=-28)

    # Bottom: suit glyph (romanized fallback if no CJK font).
    suit_label = SUIT_GLYPH[tile.suit] if has_cjk else {
        Suit.MAN: "M", Suit.PIN: "P", Suit.SOU: "S",
    }[tile.suit]
    _center_text(img, suit_label, font_suit,
                 BLACK if tile.suit != Suit.MAN else RED, dy=30)


def _render_honor(img: Image.Image, tile: Tile) -> None:
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


def render_tile(tile: Tile) -> Image.Image:
    img = _tile_base()
    if tile.is_numbered:
        _render_suit_pips(img, tile)
    else:
        _render_honor(img, tile)
    return img


def render_tile_back() -> Image.Image:
    """Face-down tile (what other players' hidden tiles look like)."""
    img = Image.new("RGBA", (TILE_W + 8, TILE_H + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    shadow = Image.new("RGBA", (TILE_W + 8, TILE_H + 8), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((4, 4, TILE_W + 4, TILE_H + 4), radius=CORNER_R,
                         fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    img.alpha_composite(shadow, (0, 0))

    body = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    db = ImageDraw.Draw(body)
    db.rounded_rectangle((0, 0, TILE_W, TILE_H), radius=CORNER_R, fill=BACK_GREEN)
    # Decorative inset diamond pattern.
    for y in range(12, TILE_H - 12, 20):
        for x in range(12, TILE_W - 12, 20):
            db.polygon(
                [(x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y)],
                outline=(255, 255, 255, 70),
            )
    img.alpha_composite(body, (2, 2))
    return img


# ---------------------------------------------------------------- batch


def generate_all(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Unique tile identities (one image per distinct face).
    seen = set()
    for t in ALL_TILES:
        key = (t.suit, t.value)
        if key in seen:
            continue
        seen.add(key)
        img = render_tile(t)
        img.save(out_dir / f"{t.to_id().replace(':', '_')}.png")
    render_tile_back().save(out_dir / "back.png")
    print(f"wrote {len(seen) + 1} tile images to {out_dir}")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent
    generate_all(here / "assets" / "tiles")
