"""达人推广海报合成：竖版 9:16 背景 + 小程序码。"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parent / 'assets' / 'referral' / 'poster_template.png'
POSTER_BRAND_NAME = os.environ.get('POSTER_BRAND_NAME', '智愿填报')
POSTER_TAGLINE = os.environ.get('POSTER_TAGLINE', '志愿填报专家')
POSTER_WIDTH = int(os.environ.get('POSTER_WIDTH', '1080'))
POSTER_HEIGHT = int(os.environ.get('POSTER_HEIGHT', '1920'))
POSTER_FEATURES = (
    '一键查院校',
    '智能冲稳保',
    '实时更新分数线',
)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc' if bold else '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for path in font_candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def poster_template_path() -> Path:
    custom = os.environ.get('REFERRAL_POSTER_TEMPLATE', '').strip()
    if custom:
        path = Path(custom)
        if path.exists():
            return path
    return DEFAULT_TEMPLATE_PATH


def _fit_portrait_canvas(image: Image.Image, width: int = POSTER_WIDTH, height: int = POSTER_HEIGHT) -> Image.Image:
    """将任意背景图裁切/缩放为竖版 9:16 画布。"""
    source = image.convert('RGBA')
    scale = max(width / source.width, height / source.height)
    resized = source.resize(
        (int(source.width * scale), int(source.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def render_default_poster_background(width: int = POSTER_WIDTH, height: int = POSTER_HEIGHT) -> Image.Image:
    """绘制默认竖版推广海报背景（无二维码）。"""
    canvas = Image.new('RGBA', (width, height), (232, 244, 255, 255))
    draw = ImageDraw.Draw(canvas)

    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = (
            int(120 + 60 * ratio),
            int(180 + 40 * ratio),
            int(255 - 20 * ratio),
            255,
        )
        draw.line((0, y, width, y), fill=color)

    margin = int(width * 0.06)
    card_top = int(height * 0.04)
    card_bottom = int(height * 0.96)
    draw.rounded_rectangle(
        (margin, card_top, width - margin, card_bottom),
        radius=36,
        fill=(255, 255, 255, 255),
    )

    avatar_size = int(width * 0.14)
    avatar_x = margin + int(width * 0.04)
    avatar_y = card_top + int(height * 0.03)
    draw.ellipse(
        (avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size),
        fill=(214, 230, 255, 255),
        outline=(22, 119, 255, 255),
        width=4,
    )

    title_font = _load_font(int(width * 0.075), bold=True)
    subtitle_font = _load_font(int(width * 0.038))
    section_font = _load_font(int(width * 0.048), bold=True)
    feature_font = _load_font(int(width * 0.04))

    title_x = avatar_x + avatar_size + int(width * 0.04)
    title_y = avatar_y + int(avatar_size * 0.12)
    draw.text((title_x, title_y), POSTER_BRAND_NAME, fill=(20, 24, 36, 255), font=title_font)
    draw.text((title_x, title_y + int(height * 0.055)), f'— {POSTER_TAGLINE} —', fill=(102, 112, 133, 255), font=subtitle_font)

    divider_y = avatar_y + avatar_size + int(height * 0.03)
    draw.line((margin + 24, divider_y, width - margin - 24, divider_y), fill=(214, 223, 238, 255), width=3)

    section_y = divider_y + int(height * 0.03)
    section_text = '核心功能介绍'
    section_width = draw.textlength(section_text, font=section_font)
    draw.text(((width - section_width) / 2, section_y), section_text, fill=(20, 24, 36, 255), font=section_font)

    feature_y = section_y + int(height * 0.06)
    bullet_x = margin + int(width * 0.1)
    for index, feature in enumerate(POSTER_FEATURES):
        y = feature_y + index * int(height * 0.055)
        draw.ellipse((bullet_x, y + 10, bullet_x + 16, y + 26), fill=(22, 119, 255, 255))
        draw.text((bullet_x + 30, y), feature, fill=(49, 55, 70, 255), font=feature_font)

    book_x = margin + int(width * 0.08)
    book_y = feature_y + int(height * 0.2)
    draw.rounded_rectangle(
        (book_x, book_y, book_x + int(width * 0.22), book_y + int(height * 0.12)),
        radius=16,
        fill=(22, 119, 255, 255),
    )
    draw.rounded_rectangle(
        (book_x + 12, book_y + 8, book_x + int(width * 0.22) - 8, book_y + int(height * 0.12) - 8),
        radius=12,
        fill=(255, 255, 255, 255),
    )

    tower_x = width - margin - int(width * 0.28)
    tower_y = book_y
    draw.rectangle((tower_x + 60, tower_y + 40, tower_x + 120, tower_y + 180), fill=(167, 198, 255, 255))
    draw.polygon(
        [(tower_x + 40, tower_y + 40), (tower_x + 140, tower_y + 40), (tower_x + 90, tower_y)],
        fill=(22, 119, 255, 255),
    )

    qr_zone_top = int(height * 0.62)
    draw.rounded_rectangle(
        (margin + 20, qr_zone_top, width - margin - 20, card_bottom - int(height * 0.02)),
        radius=24,
        fill=(248, 250, 255, 255),
    )
    return canvas


def load_poster_background(template_path: Path | None = None) -> Image.Image:
    path = template_path or poster_template_path()
    if path.exists():
        with Image.open(path) as image:
            return _fit_portrait_canvas(image)
    return render_default_poster_background()


def _qr_layout(canvas_size: tuple[int, int]) -> dict[str, int]:
    width, height = canvas_size
    qr_size = int(width * 0.42)
    qr_x = (width - qr_size) // 2
    qr_y = int(height * 0.66)
    return {
        'qr_size': qr_size,
        'qr_x': qr_x,
        'qr_y': qr_y,
        'caption_y': qr_y + qr_size + int(height * 0.018),
        'code_y': qr_y + qr_size + int(height * 0.048),
    }


def compose_referral_poster(
    qrcode_bytes: bytes,
    *,
    invite_code: str = '',
    display_name: str = '',
    template_path: Path | None = None,
) -> bytes:
    canvas = load_poster_background(template_path)
    if canvas.size != (POSTER_WIDTH, POSTER_HEIGHT):
        canvas = _fit_portrait_canvas(canvas)
    draw = ImageDraw.Draw(canvas)
    layout = _qr_layout(canvas.size)

    qr_image = Image.open(io.BytesIO(qrcode_bytes)).convert('RGBA')
    qr_image = qr_image.resize((layout['qr_size'], layout['qr_size']), Image.Resampling.LANCZOS)

    pad = max(10, layout['qr_size'] // 20)
    box_size = layout['qr_size'] + pad * 2
    box_x = layout['qr_x'] - pad
    box_y = layout['qr_y'] - pad
    draw.rounded_rectangle(
        (box_x, box_y, box_x + box_size, box_y + box_size),
        radius=max(16, pad),
        fill=(255, 255, 255, 255),
        outline=(22, 119, 255, 255),
        width=4,
    )
    canvas.alpha_composite(qr_image, (layout['qr_x'], layout['qr_y']))

    caption = '长按识别小程序 · 专属志愿填报助手'
    caption_font = _load_font(max(28, canvas.width // 34))
    caption_width = draw.textlength(caption, font=caption_font)
    draw.text(
        ((canvas.width - caption_width) / 2, layout['caption_y']),
        caption,
        fill=(31, 36, 48, 255),
        font=caption_font,
    )

    if invite_code:
        code_text = f'达人推广码：{invite_code}'
        if display_name:
            code_text = f'{display_name} · {code_text}'
        code_font = _load_font(max(24, canvas.width // 40), bold=True)
        code_width = draw.textlength(code_text, font=code_font)
        draw.text(
            ((canvas.width - code_width) / 2, layout['code_y']),
            code_text,
            fill=(22, 119, 255, 255),
            font=code_font,
        )

    output = io.BytesIO()
    canvas.convert('RGB').save(output, format='PNG', optimize=True)
    return output.getvalue()


def poster_metadata() -> dict[str, Any]:
    path = poster_template_path()
    return {
        'brand_name': POSTER_BRAND_NAME,
        'tagline': POSTER_TAGLINE,
        'template_path': str(path),
        'template_exists': path.exists(),
        'output_size': {'width': POSTER_WIDTH, 'height': POSTER_HEIGHT, 'ratio': '9:16'},
    }
