"""服务端合成推广海报（背景 + 文案 + 微信小程序码）。"""

from __future__ import annotations

import io
import os
import platform
from typing import Any

from PIL import Image, ImageDraw, ImageFont

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


def compose_promotion_poster(
    display_name: str,
    invite_code: str,
    qr_bytes: bytes,
    template: dict[str, Any] | None = None,
    reward_text: str = '扫码领取专属权益',
) -> bytes:
    template = template or {}
    width, height = 600, 960
    bg = _hex_to_rgb(template.get('bg_color') or '#1677ff')
    fg = _hex_to_rgb(template.get('text_color') or '#ffffff', (255, 255, 255))

    image = Image.new('RGB', (width, height), bg)
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
    qr_size = 312
    qr_image = qr_image.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    qr_x = (width - qr_size) // 2
    qr_y = 280
    image.paste(qr_image, (qr_x, qr_y), qr_image if qr_image.mode == 'RGBA' else None)

    code_text = f'推广码 {invite_code}'
    draw.text((48, height - 120), code_text, fill=fg, font=font_small)
    draw.text((48, height - 76), '微信扫一扫小程序码', fill=fg, font=font_small)

    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()
