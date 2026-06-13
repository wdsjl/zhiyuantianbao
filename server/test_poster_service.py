import io
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from poster_service import (
    POSTER_HEIGHT,
    POSTER_WIDTH,
    compose_referral_poster,
    poster_metadata,
    poster_template_path,
    render_default_poster_background,
)


def _fake_qrcode_bytes(size: int = 200) -> bytes:
    image = Image.new('RGB', (size, size), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, size - 10, size - 10), outline='black', width=4)
    draw.line((10, 10, size - 10, size - 10), fill='black', width=3)
    draw.line((size - 10, 10, 10, size - 10), fill='black', width=3)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


class PosterServiceTests(unittest.TestCase):
    def test_template_exists(self):
        self.assertTrue(poster_template_path().exists())

    def test_default_background_is_portrait_9_16(self):
        image = render_default_poster_background()
        self.assertEqual(image.size, (POSTER_WIDTH, POSTER_HEIGHT))
        self.assertGreater(POSTER_HEIGHT, POSTER_WIDTH)
        self.assertAlmostEqual(POSTER_WIDTH / POSTER_HEIGHT, 9 / 16, places=2)

    def test_compose_referral_poster_returns_png(self):
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
        self.assertEqual(meta['brand_name'], '智愿填报')
        self.assertEqual(meta['output_size']['width'], POSTER_WIDTH)
        self.assertEqual(meta['output_size']['height'], POSTER_HEIGHT)
        self.assertEqual(meta['output_size']['ratio'], '9:16')

    @patch('referral_service.generate_poster_qrcode', return_value=_fake_qrcode_bytes())
    def test_poster_image_base64_uses_template(self, _mock_qr):
        from referral_service import poster_image_base64

        encoded = poster_image_base64('TEST01', '李老师')
        self.assertTrue(encoded)
        raw = __import__('base64').b64decode(encoded)
        self.assertTrue(raw.startswith(b'\x89PNG'))


if __name__ == '__main__':
    unittest.main()
