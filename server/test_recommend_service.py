"""检索与批次匹配辅助测试。"""

import unittest

from recommend_service import expand_batch_aliases, province_variants


class RecommendServiceTests(unittest.TestCase):
    def test_expand_batch_aliases_undergrad(self) -> None:
        aliases = expand_batch_aliases('本科批')
        self.assertIn('本科批', aliases)
        self.assertIn('本科', aliases)

    def test_province_variants_henan(self) -> None:
        variants = province_variants('河南')
        self.assertIn('河南', variants)
        self.assertIn('河南省', variants)


if __name__ == '__main__':
    unittest.main()
