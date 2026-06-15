import base64
import io
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from poster_service import (
    POSTER_HEIGHT,
    POSTER_WIDTH,
    _load_font,
    compose_referral_poster,
    poster_metadata,
    poster_template_path,
)


def _fake_qrcode_bytes(size: int = 200) -> bytes:
    image = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, size - 10, size - 10), outline='black', width=4)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


class PosterServiceTests(unittest.TestCase):
    def test_template_exists(self):
        self.assertTrue(poster_template_path().exists())

    def test_bundled_font_renders_chinese(self):
        font = _load_font(32)
        image = Image.new('RGB', (320, 80), 'white')
        draw = ImageDraw.Draw(image)
        draw.text((10, 20), '智愿填报', fill='black', font=font)
        pixels = image.getdata()
        self.assertTrue(any(pixel != (255, 255, 255) for pixel in pixels))

    def test_compose_referral_poster_returns_portrait_png(self):
        poster = compose_referral_poster(
            _fake_qrcode_bytes(),
            invite_code='ABC123',
            display_name='张老师',
        )
        self.assertTrue(poster.startswith(b'\x89PNG'))
        with Image.open(io.BytesIO(poster)) as image:
            self.assertEqual(image.size, (POSTER_WIDTH, POSTER_HEIGHT))

    def test_poster_metadata(self):
        meta = poster_metadata()
        self.assertTrue(meta['template_exists'])
        self.assertTrue(meta['font_bundled'])
        self.assertTrue(meta['font_usable'])
        self.assertEqual(meta['output_size']['ratio'], '9:16')

    @patch('referral_service.generate_poster_qrcode', return_value=_fake_qrcode_bytes())
    def test_poster_image_base64_uses_template(self, _mock_qr):
        from referral_service import poster_image_base64

        encoded = poster_image_base64('TEST01', '李老师')
        raw = base64.b64decode(encoded)
        self.assertTrue(raw.startswith(b'\x89PNG'))


if __name__ == '__main__':
    unittest.main()
