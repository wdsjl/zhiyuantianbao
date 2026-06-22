"""检索与批次匹配辅助测试。"""

import unittest

from recommend_service import expand_batch_aliases, province_variants


class RecommendServiceTests(unittest.TestCase):
    def test_expand_batch_aliases_undergrad(self) -> None:
        aliases = expand_batch_aliases('本科批')
        self.assertIn('本科批', aliases)
        self.assertIn('本科', aliases)

    def test_expand_batch_aliases_art_undergrad(self) -> None:
        aliases = expand_batch_aliases('艺术本科批')
        self.assertIn('艺术本科批', aliases)
        self.assertIn('艺考本科批', aliases)
        self.assertNotIn('本科普通批', aliases)

    def test_expand_batch_aliases_sports_junior(self) -> None:
        aliases = expand_batch_aliases('体育专科批')
        self.assertIn('体育专科批', aliases)
        self.assertNotIn('高职专科批', aliases)

    def test_province_variants_henan(self) -> None:
        variants = province_variants('河南')
        self.assertIn('河南', variants)
        self.assertIn('河南省', variants)


if __name__ == '__main__':
    unittest.main()
