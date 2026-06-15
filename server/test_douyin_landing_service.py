import unittest
from unittest.mock import patch

from douyin_landing_service import (
    build_landing_page_url,
    generate_douyin_landing_links,
    resolve_landing_target,
    render_landing_page_html,
)
from wechat_link_service import _normalize_page_path, _normalize_query, generate_mini_program_links


class DouyinLandingServiceTests(unittest.TestCase):
    def test_normalize_page_path(self):
        self.assertEqual(_normalize_page_path('/pages/home/home'), 'pages/home/home')

    def test_normalize_query_from_dict(self):
        self.assertEqual(_normalize_query({'invite': 'ABC123', 'from': 'douyin'}), 'invite=ABC123&from=douyin')

    def test_resolve_douyin_redeem_target(self):
        target = resolve_landing_target(page='douyin_redeem', invite='ZD123')
        self.assertEqual(target['page_path'], 'pages/membership/membership')
        self.assertIn('scroll=douyin', target['query'])
        self.assertIn('invite=ZD123', target['query'])

    def test_build_landing_page_url(self):
        url = build_landing_page_url(page='home', invite='ABC123', from_source='douyin')
        self.assertIn('/douyin/landing?', url)
        self.assertIn('invite=ABC123', url)
        self.assertIn('page=home', url)

    @patch(
        'douyin_landing_service.generate_mini_program_links',
        return_value={
            'page_path': 'pages/home/home',
            'query': 'from=douyin',
            'share_path': 'pages/home/home?from=douyin',
            'url_scheme': 'weixin://dl/business/?t=test',
            'url_link': 'https://wxaurl.cn/test',
            'env_version': 'release',
        },
    )
    def test_generate_douyin_landing_links(self, _mock_links):
        payload = generate_douyin_landing_links(page='home', from_source='douyin')
        self.assertEqual(payload['url_scheme'], 'weixin://dl/business/?t=test')
        self.assertIn('/douyin/landing?', payload['landing_page_url'])
        self.assertIn('douyin_ad', payload['usage'])

    def test_render_landing_page_html_contains_buttons(self):
        html = render_landing_page_html(
            title='智愿填报',
            subtitle='测试',
            url_scheme='weixin://dl/business/?t=test',
            url_link='https://wxaurl.cn/test',
            invite='ABC123',
        )
        self.assertIn('打开微信小程序', html)
        self.assertIn('weixin://dl/business/?t=test', html)
        self.assertIn('https://wxaurl.cn/test', html)
        self.assertIn('ABC123', html)

    @patch('wechat_link_service._post_wechat_api')
    def test_generate_mini_program_links(self, mock_post):
        mock_post.side_effect = [
            {'openlink': 'weixin://dl/business/?t=abc'},
            {'url_link': 'https://wxaurl.cn/abc'},
        ]
        payload = generate_mini_program_links('pages/home/home', 'from=douyin')
        self.assertEqual(payload['url_scheme'], 'weixin://dl/business/?t=abc')
        self.assertEqual(payload['url_link'], 'https://wxaurl.cn/abc')


if __name__ == '__main__':
    unittest.main()
