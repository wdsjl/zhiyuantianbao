"""达人推广海报合成：背景模板 + 小程序码。"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parent / 'assets' / 'referral' / 'poster_template.png'
POSTER_BRAND_NAME = os.environ.get('POSTER_BRAND_NAME', '智愿填报')
POSTER_TAGLINE = os.environ.get('POSTER_TAGLINE', '志愿填报专家')


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


def _qr_layout(canvas_size: tuple[int, int]) -> dict[str, int]:
    width, height = canvas_size
    qr_size = int(min(width, height) * 0.28)
    qr_x = (width - qr_size) // 2
    qr_y = int(height * 0.68) - qr_size // 2
    return {
        'qr_size': qr_size,
        'qr_x': qr_x,
        'qr_y': qr_y,
        'caption_y': qr_y + qr_size + int(height * 0.02),
        'code_y': qr_y + qr_size + int(height * 0.06),
    }


def compose_referral_poster(
    qrcode_bytes: bytes,
    *,
    invite_code: str = '',
    display_name: str = '',
    template_path: Path | None = None,
) -> bytes:
    template = Image.open(template_path or poster_template_path()).convert('RGBA')
    canvas = template.copy()
    draw = ImageDraw.Draw(canvas)
    layout = _qr_layout(canvas.size)

    qr_image = Image.open(io.BytesIO(qrcode_bytes)).convert('RGBA')
    qr_image = qr_image.resize((layout['qr_size'], layout['qr_size']), Image.Resampling.LANCZOS)

    pad = max(8, layout['qr_size'] // 24)
    box_size = layout['qr_size'] + pad * 2
    box_x = layout['qr_x'] - pad
    box_y = layout['qr_y'] - pad
    draw.rounded_rectangle(
        (box_x, box_y, box_x + box_size, box_y + box_size),
        radius=max(12, pad),
        fill=(255, 255, 255, 255),
        outline=(22, 119, 255, 255),
        width=max(2, pad // 4),
    )
    canvas.alpha_composite(qr_image, (layout['qr_x'], layout['qr_y']))

    caption = '长按识别小程序 · 专属志愿填报助手'
    caption_font = _load_font(max(18, canvas.width // 42))
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
        code_font = _load_font(max(16, canvas.width // 48), bold=True)
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
    size = None
    if path.exists():
        with Image.open(path) as image:
            size = {'width': image.width, 'height': image.height}
    return {
        'brand_name': POSTER_BRAND_NAME,
        'tagline': POSTER_TAGLINE,
        'template_path': str(path),
        'template_exists': path.exists(),
        'template_size': size,
    }
