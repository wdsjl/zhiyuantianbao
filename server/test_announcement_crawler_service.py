import unittest

from announcement_crawler_service import (
    classify_announcement_type,
    discover_announcement_links,
    is_relevant_announcement,
    mentions_henan,
    normalize_school_website,
    url_hash,
    upsert_announcement,
)


class AnnouncementCrawlerTests(unittest.TestCase):
    def test_is_relevant_announcement_requires_recruit_and_year(self):
        ok, keywords = is_relevant_announcement('河南大学2026年本科招生章程', 'https://example.com/zs.htm', 2026)
        self.assertTrue(ok)
        self.assertIn('2026', keywords)

    def test_is_relevant_announcement_rejects_unrelated(self):
        ok, _ = is_relevant_announcement('学校新闻：运动会圆满落幕', 'https://example.com/news/1', 2026)
        self.assertFalse(ok)

    def test_classify_announcement_type(self):
        self.assertEqual(classify_announcement_type('2026招生章程', ''), '招生章程')
        self.assertEqual(classify_announcement_type('招生计划公布', ''), '招生计划')

    def test_discover_links_from_html(self):
        html = '''
        <html><body>
          <a href="/zs/2026-plan.pdf">2026年招生计划公告</a>
          <a href="/about.html">学校简介</a>
        </body></html>
        '''
        links = discover_announcement_links('https://school.edu.cn/', html)
        titles = [item['title'] for item in links]
        self.assertIn('2026年招生计划公告', titles)

    def test_mentions_henan(self):
        self.assertTrue(mentions_henan('面向河南考生招生', ''))
        self.assertFalse(mentions_henan('2026年招生简章', 'https://school.edu.cn/zs'))

    def test_normalize_school_website(self):
        self.assertEqual(normalize_school_website('www.zzu.edu.cn'), 'https://www.zzu.edu.cn/')

    def test_url_hash_stable(self):
        self.assertEqual(url_hash('https://a.com/x'), url_hash('https://a.com/x#section'))

    def test_upsert_announcement_dedupes(self):
        import time
        unique_url = f'https://example.com/announcement-{int(time.time() * 1000)}'
        payload = {
            'source_org': '测试大学',
            'source_type': 'university',
            'school_name': '测试大学',
            'province': '河南',
            'target_province': '河南',
            'year': 2026,
            'title': '2026年招生公告',
            'announcement_type': '招生公告',
            'url': unique_url,
            'matched_keywords': ['招生', '2026'],
            'mentions_henan': True,
        }
        self.assertTrue(upsert_announcement(payload))
        self.assertFalse(upsert_announcement(payload))


if __name__ == '__main__':
    unittest.main()
