import os
import tempfile
import unittest
from pathlib import Path

from bootstrap_secrets import _parse_secrets_js, load_ecosystem_secrets, get_secrets_file_path


class BootstrapSecretsTest(unittest.TestCase):
    def test_parse_secrets_js(self):
        content = """
        module.exports = {
          DOUYIN_APP_SECRET: 'abc123',
          DOUYIN_SPI_TOKEN: "token456",
        };
        """
        parsed = _parse_secrets_js(content)
        self.assertEqual(parsed['DOUYIN_APP_SECRET'], 'abc123')
        self.assertEqual(parsed['DOUYIN_SPI_TOKEN'], 'token456')

    def test_load_from_real_file_if_exists(self):
        path = get_secrets_file_path()
        if not path.exists():
            self.skipTest('ecosystem.secrets.js not present')
        old = os.environ.get('DOUYIN_APP_SECRET')
        if 'DOUYIN_APP_SECRET' in os.environ:
            del os.environ['DOUYIN_APP_SECRET']
        try:
            loaded = load_ecosystem_secrets(force=True)
            self.assertIn('DOUYIN_APP_SECRET', loaded)
            self.assertTrue(os.getenv('DOUYIN_APP_SECRET'))
        finally:
            if old:
                os.environ['DOUYIN_APP_SECRET'] = old


if __name__ == '__main__':
    unittest.main()
