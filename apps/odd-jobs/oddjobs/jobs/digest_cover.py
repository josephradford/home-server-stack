"""Generated cover for the reading-digest EPUB, so each issue stands out on the shelf."""
from __future__ import annotations

import datetime
import io

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 1800  # 2:3, the usual ebook cover ratio
INK = (250, 247, 240)
# One background per weekday, so consecutive issues are easy to tell apart.
PALETTE = [
    (176, 58, 46),    # Mon
    (183, 110, 0),    # Tue
    (35, 105, 79),    # Wed
    (31, 97, 141),    # Thu
    (91, 63, 140),    # Fri
    (120, 66, 18),    # Sat
    (52, 73, 94),     # Sun
]
FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_PATHS if bold else FONT_PATHS[1:]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)  # Pillow's bundled scalable font


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and draw.textlength(trial, font=font) > max_width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def make_cover(day: datetime.date, sources: list[str], post_count: int) -> bytes:
    """Render the cover as JPEG bytes: title, date, counts and the feeds included."""
    img = Image.new("RGB", (WIDTH, HEIGHT), PALETTE[day.weekday()])
    draw = ImageDraw.Draw(img)
    margin = 100
    inner = WIDTH - 2 * margin

    draw.rectangle([margin // 2, margin // 2, WIDTH - margin // 2, HEIGHT - margin // 2], outline=INK, width=6)

    y = 260
    for line in ("Reading", "List"):
        draw.text((margin, y), line, font=_font(240), fill=INK)
        y += 270

    y += 40
    draw.line([margin, y, margin + 220, y], fill=INK, width=8)
    y += 60
    draw.text((margin, y), day.strftime("%A"), font=_font(70, bold=False), fill=INK)
    y += 100
    draw.text((margin, y), day.strftime("%-d %B %Y"), font=_font(70), fill=INK)
    y += 140

    plural = "post" if post_count == 1 else "posts"
    draw.text((margin, y), f"{post_count} {plural} · {len(sources)} feed{'s' if len(sources) != 1 else ''}",
              font=_font(48, bold=False), fill=INK)
    y += 100

    small = _font(44, bold=False)
    for src in sorted(sources):
        for line in _wrap(draw, src, small, inner)[:2]:
            if y > HEIGHT - 200:
                break
            draw.text((margin, y), line, font=small, fill=INK)
            y += 62
        y += 12

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue()
