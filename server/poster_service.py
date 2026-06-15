"""达人推广海报合成：竖版 9:16 背景图 + 小程序码。"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).resolve().parent / 'assets'
DEFAULT_TEMPLATE_PATH = ASSETS_DIR / 'referral' / 'poster_template.png'
BUNDLED_FONT_REGULAR = ASSETS_DIR / 'fonts' / 'WenQuanYiMicroHei.ttf'
BUNDLED_FONT_BOLD = ASSETS_DIR / 'fonts' / 'WenQuanYiMicroHei.ttf'
POSTER_BRAND_NAME = os.environ.get('POSTER_BRAND_NAME', '智愿填报')
POSTER_TAGLINE = os.environ.get('POSTER_TAGLINE', '志愿填报专家')
POSTER_WIDTH = int(os.environ.get('POSTER_WIDTH', '1080'))
POSTER_HEIGHT = int(os.environ.get('POSTER_HEIGHT', '1920'))


def _windows_font_dir() -> Path | None:
    windir = os.environ.get('WINDIR') or os.environ.get('SystemRoot')
    if not windir:
        return None
    fonts = Path(windir) / 'Fonts'
    return fonts if fonts.exists() else None


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: list[Path | str] = [
        BUNDLED_FONT_BOLD if bold else BUNDLED_FONT_REGULAR,
    ]
    windows_fonts = _windows_font_dir()
    if windows_fonts:
        candidates.extend([
            windows_fonts / ('msyhbd.ttc' if bold else 'msyh.ttc'),
            windows_fonts / 'simhei.ttf',
            windows_fonts / 'simsun.ttc',
        ])
    candidates.extend([
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc' if bold else '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    ])
    for path in candidates:
        path = Path(path)
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size=size)
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
    source = image.convert('RGBA')
    scale = max(width / source.width, height / source.height)
    resized = source.resize(
        (int(source.width * scale), int(source.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def load_poster_background(template_path: Path | None = None) -> Image.Image:
    path = template_path or poster_template_path()
    if not path.exists():
        raise FileNotFoundError(
            f'未找到海报背景图：{path}。请将竖版 9:16 设计稿放到 server/assets/referral/poster_template.png'
        )
    with Image.open(path) as image:
        canvas = _fit_portrait_canvas(image)
    if canvas.size != (POSTER_WIDTH, POSTER_HEIGHT):
        canvas = canvas.resize((POSTER_WIDTH, POSTER_HEIGHT), Image.Resampling.LANCZOS)
    return canvas


def _qr_layout(canvas_size: tuple[int, int]) -> dict[str, int]:
    width, height = canvas_size
    qr_size = int(width * 0.36)
    qr_x = (width - qr_size) // 2
    qr_y = int(height * 0.68)
    return {
        'qr_size': qr_size,
        'qr_x': qr_x,
        'qr_y': qr_y,
        'caption_y': min(qr_y + qr_size + int(height * 0.016), height - int(height * 0.09)),
        'code_y': min(qr_y + qr_size + int(height * 0.045), height - int(height * 0.05)),
    }


def compose_referral_poster(
    qrcode_bytes: bytes,
    *,
    invite_code: str = '',
    display_name: str = '',
    template_path: Path | None = None,
) -> bytes:
    canvas = load_poster_background(template_path)
    draw = ImageDraw.Draw(canvas)
    layout = _qr_layout(canvas.size)

    qr_image = Image.open(io.BytesIO(qrcode_bytes)).convert('RGBA')
    qr_image = qr_image.resize((layout['qr_size'], layout['qr_size']), Image.Resampling.LANCZOS)

    pad = max(10, layout['qr_size'] // 22)
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
    font_loaded = _load_font(28)
    return {
        'brand_name': POSTER_BRAND_NAME,
        'tagline': POSTER_TAGLINE,
        'template_path': str(path),
        'template_exists': path.exists(),
        'font_bundled': BUNDLED_FONT_REGULAR.exists(),
        'font_usable': not isinstance(font_loaded, ImageFont.ImageFont),
        'output_size': {'width': POSTER_WIDTH, 'height': POSTER_HEIGHT, 'ratio': '9:16'},
    }
