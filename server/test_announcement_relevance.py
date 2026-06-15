import unittest

from announcement_crawler_service import (
    is_excluded_announcement,
    is_relevant_announcement,
    should_auto_reject_announcement,
)


class AnnouncementRelevanceTests(unittest.TestCase):
    def test_excludes_procurement_and_news(self):
        samples = [
            ('某某大学食堂招标公告', 'https://www.example.edu.cn/news/123'),
            ('无人机设备采购结果公示', 'https://www.example.edu.cn/zsb/456'),
            ('校友论坛活动通知', 'https://www.example.edu.cn/zsb/789'),
            ('教师节表彰大会', 'https://www.example.edu.cn/zsb/honor'),
        ]
        for title, url in samples:
            self.assertTrue(is_excluded_announcement(title, url), title)
            self.assertTrue(should_auto_reject_announcement(title, url))
            self.assertFalse(is_relevant_announcement(title, url)[0], title)

    def test_accepts_recruitment_announcements(self):
        samples = [
            ('2026年本科招生章程', 'https://www.example.edu.cn/zsb/zszc.pdf'),
            ('2026年招生计划公告', 'https://www.example.edu.cn/zsb/zsjh.htm'),
            ('招生简章', 'https://www.example.edu.cn/recruit/jianzhang.html'),
        ]
        for title, url in samples:
            self.assertFalse(is_excluded_announcement(title, url), title)
            self.assertFalse(should_auto_reject_announcement(title, url))
            self.assertTrue(is_relevant_announcement(title, url)[0], title)

    def test_rejects_without_strong_recruit_signal(self):
        title = '学校召开工作会议'
        url = 'https://www.example.edu.cn/news/meeting.html'
        self.assertFalse(is_relevant_announcement(title, url)[0])
        self.assertTrue(should_auto_reject_announcement(title, url))


if __name__ == '__main__':
    unittest.main()
