"""服务端合成推广海报（背景 + 文案 + 微信小程序码）。"""

from __future__ import annotations

import io
import os
import platform
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

POSTER_WIDTH = 600
POSTER_HEIGHT = 960
QR_SIZE = 312
QR_X = (POSTER_WIDTH - QR_SIZE) // 2
QR_Y = 280
POSTER_BG_DIR = Path(__file__).resolve().parent / 'assets' / 'poster-bg'

FONT_CANDIDATES = [
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/msyhbd.ttc',
    'C:/Windows/Fonts/simhei.ttf',
    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]


def _hex_to_rgb(color: str, default: tuple[int, int, int] = (22, 119, 255)) -> tuple[int, int, int]:
    raw = (color or '').strip().lstrip('#')
    if len(raw) == 6:
        try:
            return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass
    return default


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = list(FONT_CANDIDATES)
    if bold and platform.system() == 'Windows':
        candidates = ['C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/msyh.ttc'] + candidates
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def get_poster_layout() -> dict[str, Any]:
    return {
        'width': POSTER_WIDTH,
        'height': POSTER_HEIGHT,
        'ratio': '5:8',
        'qr_size': QR_SIZE,
        'qr_x': QR_X,
        'qr_y': QR_Y,
        'design_size_2x': {'width': POSTER_WIDTH * 2, 'height': POSTER_HEIGHT * 2},
        'safe_zones': {
            'top_text': {'x': 48, 'y': 56, 'width': 504, 'height': 200},
            'qr': {'x': QR_X, 'y': QR_Y, 'width': QR_SIZE, 'height': QR_SIZE},
            'bottom_text': {'x': 48, 'y': POSTER_HEIGHT - 140, 'width': 504, 'height': 120},
        },
    }


def resolve_poster_bg_path(template: dict[str, Any] | None) -> str:
    template = template or {}
    raw = (template.get('bg_image_path') or '').strip()
    if not raw:
        return ''
    path = Path(raw)
    if not path.is_absolute():
        path = POSTER_BG_DIR / path.name
    return str(path) if path.exists() else ''


def compose_promotion_poster(
    display_name: str,
    invite_code: str,
    qr_bytes: bytes,
    template: dict[str, Any] | None = None,
    reward_text: str = '扫码领取专属权益',
) -> bytes:
    template = template or {}
    width, height = POSTER_WIDTH, POSTER_HEIGHT
    bg = _hex_to_rgb(template.get('bg_color') or '#1677ff')
    fg = _hex_to_rgb(template.get('text_color') or '#ffffff', (255, 255, 255))

    bg_path = resolve_poster_bg_path(template)
    if bg_path:
        image = Image.open(bg_path).convert('RGBA')
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    else:
        image = Image.new('RGBA', (width, height), (*bg, 255))
    draw = ImageDraw.Draw(image)

    font_title = _load_font(40, bold=True)
    font_name = _load_font(30, bold=True)
    font_sub = _load_font(24)
    font_small = _load_font(22)

    draw.text((48, 56), '智愿填报', fill=fg, font=font_title)
    draw.text((48, 118), (display_name or '专属达人')[:12], fill=fg, font=font_name)
    draw.text((48, 168), '高考志愿智能辅助', fill=fg, font=font_sub)
    draw.text((48, 212), (reward_text or '扫码领取专属权益')[:18], fill=fg, font=font_sub)

    qr_image = Image.open(io.BytesIO(qr_bytes)).convert('RGBA')
    qr_image = qr_image.resize((QR_SIZE, QR_SIZE), Image.Resampling.LANCZOS)
    image.paste(qr_image, (QR_X, QR_Y), qr_image)

    code_text = f'推广码 {invite_code}'
    draw.text((48, height - 120), code_text, fill=fg, font=font_small)
    draw.text((48, height - 76), '微信扫一扫小程序码', fill=fg, font=font_small)

    buffer = io.BytesIO()
    image.convert('RGB').save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


def save_poster_background(template_key: str, file_bytes: bytes, filename: str = '') -> str:
    POSTER_BG_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(filename or 'bg.png').suffix.lower() or '.png'
    if ext not in ('.png', '.jpg', '.jpeg', '.webp'):
        ext = '.png'
    target = POSTER_BG_DIR / f'{template_key}{ext}'
    target.write_bytes(file_bytes)
    return target.name
