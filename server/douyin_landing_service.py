"""抖音投放 H5 落地页与微信小程序唤起链接。"""

from __future__ import annotations

import json
import os
from html import escape
from typing import Any
from urllib.parse import urlencode

from wechat_link_service import generate_mini_program_links

LANDING_BASE_URL = (os.getenv('DOUYIN_LANDING_BASE_URL') or 'https://api.zntb.lhyun.net').rstrip('/')
BRAND_NAME = os.getenv('POSTER_BRAND_NAME', '智愿填报')

PAGE_PRESETS: dict[str, dict[str, str]] = {
    'home': {
        'page_path': 'pages/home/home',
        'title': '智愿填报 · 高考志愿填报助手',
        'subtitle': '智能冲稳保推荐，一键生成志愿方案',
    },
    'membership': {
        'page_path': 'pages/membership/membership',
        'title': '智愿填报 · 会员中心',
        'subtitle': '开通会员，解锁智能志愿与报告能力',
    },
    'douyin_redeem': {
        'page_path': 'pages/membership/membership',
        'title': '智愿填报 · 抖音券兑换',
        'subtitle': '在抖音购买后，点此进入微信小程序兑换会员',
    },
    'promotion': {
        'page_path': 'pages/promotion/promotion',
        'title': '智愿填报 · 达人推广中心',
        'subtitle': '领取专属推广海报，绑定推广关系',
    },
}


def resolve_landing_target(
    page: str = 'home',
    page_path: str = '',
    query: str | dict[str, str] | None = None,
    invite: str = '',
    from_source: str = 'douyin',
) -> dict[str, str]:
    preset = PAGE_PRESETS.get(page, PAGE_PRESETS['home'])
    resolved_path = (page_path or preset['page_path']).strip().lstrip('/')
    query_map: dict[str, str] = {}
    if isinstance(query, dict):
        query_map.update({key: str(value) for key, value in query.items() if value not in (None, '')})
    elif query:
        for part in str(query).split('&'):
            if '=' in part:
                key, value = part.split('=', 1)
                query_map[key.strip()] = value.strip()
    if invite:
        query_map['invite'] = invite.strip().upper()
    if from_source:
        query_map['from'] = from_source
    if page == 'douyin_redeem':
        query_map.setdefault('scroll', 'douyin')
    query_text = urlencode(query_map)
    return {
        'page': page,
        'page_path': resolved_path,
        'query': query_text,
        'title': preset['title'],
        'subtitle': preset['subtitle'],
    }


def build_landing_page_url(
    page: str = 'home',
    page_path: str = '',
    query: str | dict[str, str] | None = None,
    invite: str = '',
    from_source: str = 'douyin',
) -> str:
    target = resolve_landing_target(page, page_path, query, invite, from_source)
    params = {
        'page': target['page'],
        'from': from_source or 'douyin',
    }
    if invite:
        params['invite'] = invite.strip().upper()
    if page_path:
        params['page_path'] = target['page_path']
    if target['query']:
        params['query'] = target['query']
    return f'{LANDING_BASE_URL}/douyin/landing?{urlencode(params)}'


def generate_douyin_landing_links(
    page: str = 'home',
    page_path: str = '',
    query: str | dict[str, str] | None = None,
    invite: str = '',
    from_source: str = 'douyin',
    *,
    env_version: str | None = None,
) -> dict[str, Any]:
    target = resolve_landing_target(page, page_path, query, invite, from_source)
    links = generate_mini_program_links(
        target['page_path'],
        target['query'],
        env_version=env_version,
    )
    landing_page_url = build_landing_page_url(
        page=page,
        page_path=target['page_path'],
        query=target['query'],
        invite=invite,
        from_source=from_source,
    )
    return {
        **links,
        'landing_page_url': landing_page_url,
        'title': target['title'],
        'subtitle': target['subtitle'],
        'from_source': from_source,
        'invite': invite.strip().upper() if invite else '',
        'usage': {
            'douyin_ad': '抖音广告/私信/主页填写 landing_page_url 作为落地页链接',
            'direct_scheme': '技术同学可直接使用 url_scheme 做按钮跳转',
            'direct_url_link': 'url_link 可在短信、邮件或部分外链场景使用',
        },
    }


def render_landing_page_html(
    *,
    title: str,
    subtitle: str,
    url_scheme: str,
    url_link: str,
    invite: str = '',
) -> str:
    invite_html = (
        f'<p class="invite">达人推广码：{escape(invite)}</p>'
        if invite else ''
    )
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
  <title>{escape(title)}</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: linear-gradient(180deg, #eaf3ff 0%, #f7faff 45%, #ffffff 100%);
      color: #1f2430;
    }}
    .wrap {{
      max-width: 720px;
      margin: 0 auto;
      padding: 28px 20px 40px;
    }}
    .card {{
      background: #fff;
      border-radius: 20px;
      padding: 28px 22px;
      box-shadow: 0 10px 30px rgba(22, 119, 255, 0.12);
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 28px;
      line-height: 1.35;
    }}
    .sub {{
      margin: 0 0 24px;
      color: #667085;
      font-size: 16px;
      line-height: 1.6;
    }}
    .btn {{
      display: block;
      width: 100%;
      box-sizing: border-box;
      border: none;
      border-radius: 14px;
      padding: 16px 18px;
      font-size: 18px;
      font-weight: 700;
      color: #fff;
      background: linear-gradient(135deg, #1677ff 0%, #3b8cff 100%);
      text-decoration: none;
      text-align: center;
    }}
    .btn-secondary {{
      margin-top: 12px;
      background: #eef4ff;
      color: #1677ff;
      font-weight: 600;
    }}
    .tips {{
      margin-top: 18px;
      color: #98a2b3;
      font-size: 13px;
      line-height: 1.7;
    }}
    .invite {{
      margin: 0 0 16px;
      color: #1677ff;
      font-size: 15px;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>{escape(title)}</h1>
      <p class="sub">{escape(subtitle)}</p>
      {invite_html}
      <a id="open-btn" class="btn" href="{escape(url_scheme)}">打开微信小程序</a>
      <a class="btn btn-secondary" href="{escape(url_link)}">备用链接打开小程序</a>
      <p class="tips">如在抖音内打开，请点击上方按钮唤起微信；若未自动跳转，请用备用链接或复制到浏览器打开。</p>
    </div>
  </div>
  <script>
    (function () {{
      var scheme = {json.dumps(url_scheme)};
      var urlLink = {json.dumps(url_link)};
      function openMiniProgram() {{
        window.location.href = scheme;
        setTimeout(function () {{
          window.location.href = urlLink;
        }}, 1200);
      }}
      document.getElementById('open-btn').addEventListener('click', function (event) {{
        event.preventDefault();
        openMiniProgram();
      }});
      setTimeout(openMiniProgram, 500);
    }})();
  </script>
</body>
</html>'''
