from html import escape
from urllib.parse import urlencode

from fastapi.responses import HTMLResponse

from db import get_connection, rows_to_dicts
from data_fetch_service import list_sources, list_tasks, list_records, list_brochures
from llm_settings_service import get_llm_settings, mask_api_key
from membership_service import list_plans, list_permissions, get_plan_permission_map, search_users, list_permission_usage, list_expiring_members
from payment_service import list_orders, get_order_stats, list_open_requests, get_support_contact
from dashboard_service import get_dashboard_stats
from admin_data_service import (
    PAGE_SIZE, search_schools, get_school, search_majors, get_major,
    search_admissions, get_admission, search_enrollment_plans, get_enrollment_plan,
    search_students, get_student, search_province_rules, get_province_rule,
    get_import_log, list_school_options, list_major_options,
)
from crawler_config import PROVINCE_IDS, REGION_ORDER, CRAWL_PRESETS
from crawler_service import list_crawl_logs, get_crawl_log, default_recent_years, get_province_data_overview, has_running_crawl


def render_page(title: str, body: str) -> HTMLResponse:
    user_bar = '''
      <form method="post" action="/admin/logout" style="margin-left:auto;margin-bottom:0">
        <button type="submit" class="btn-sm btn-muted">退出登录</button>
      </form>
    '''
    html = f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>{escape(title)}</title>
      <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f7fb; color: #17233d; }}
        header {{ background: linear-gradient(135deg, #1677ff, #36cfc9); color: white; padding: 28px 40px; }}
        header h1 {{ margin: 0; font-size: 28px; }}
        header p {{ margin: 8px 0 0; opacity: .9; }}
        nav {{ background: white; padding: 14px 40px; box-shadow: 0 8px 24px rgba(22, 119, 255, .08); position: sticky; top: 0; z-index: 2; display: flex; flex-wrap: wrap; align-items: center; gap: 8px 0; }}
        nav a {{ display: inline-block; margin-right: 18px; color: #1677ff; text-decoration: none; font-weight: 600; }}
        .login-wrap {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }}
        .login-card {{ width: 100%; max-width: 420px; }}
        main {{ padding: 28px 40px; }}
        .card {{ background: white; border-radius: 18px; padding: 24px; box-shadow: 0 12px 32px rgba(22, 119, 255, .08); margin-bottom: 22px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }}
        .stat {{ font-size: 30px; font-weight: 800; color: #1677ff; margin-top: 8px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 14px; overflow: hidden; }}
        th, td {{ padding: 12px 14px; border-bottom: 1px solid #eef2f7; text-align: left; font-size: 14px; }}
        th {{ background: #f7f9fc; color: #475467; }}
        tr:hover td {{ background: #fafcff; }}
        .toolbar {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
        input, select {{ height: 40px; border: 1px solid #d0d5dd; border-radius: 10px; padding: 0 12px; min-width: 180px; }}
        button, .button {{ height: 40px; border: 0; border-radius: 999px; padding: 0 18px; color: white; background: #1677ff; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; }}
        .muted {{ color: #667085; line-height: 1.7; }}
        .notice {{ background: #ecfdf3; color: #027a48; border-radius: 12px; padding: 12px 16px; margin: 12px 0; }}
        .warn-box {{ background: #fff7e6; color: #b54708; border: 1px solid #fedf89; border-radius: 12px; padding: 12px 16px; margin: 12px 0; line-height: 1.7; }}
        .danger {{ color: #f04438; }}
        .success {{ color: #12b76a; }}
        .tag {{ display: inline-block; padding: 4px 8px; border-radius: 999px; background: #eef5ff; color: #1677ff; font-size: 12px; }}
        .btn-sm {{ height: 32px; padding: 0 12px; font-size: 13px; }}
        .btn-danger {{ background: #f04438; }}
        .btn-muted {{ background: #98a2b3; }}
        .pagination {{ display: flex; gap: 8px; align-items: center; margin-top: 16px; flex-wrap: wrap; }}
        .pagination a, .pagination span {{ padding: 6px 12px; border-radius: 8px; text-decoration: none; color: #1677ff; background: #eef5ff; font-size: 14px; }}
        .pagination .current {{ background: #1677ff; color: white; font-weight: 600; }}
        textarea {{ border: 1px solid #d0d5dd; border-radius: 10px; padding: 10px 12px; min-width: 280px; min-height: 72px; font-family: inherit; }}
      </style>
    </head>
    <body>
      <header>
        <h1>智愿填报数据管理后台</h1>
        <p>本地开发后台：数据导入、院校管理、专业管理、录取数据查看</p>
      </header>
      <nav>
        <a href="/admin">首页</a>
        <a href="/admin/import">数据导入</a>
        <a href="/admin/crawler">数据采集</a>
        <a href="/admin/import/logs">导入日志</a>
        <a href="/admin/schools">院校数据</a>
        <a href="/admin/students">学生档案</a>
        <a href="/admin/majors">专业数据</a>
        <a href="/admin/admissions">录取数据</a>
        <a href="/admin/enrollment-plans">招生计划</a>
        <a href="/admin/province-rules">省份规则</a>
        <a href="/admin/data-sources">官方数据源</a>
        <a href="/admin/membership/plans">会员套餐</a>
        <a href="/admin/membership/users">用户会员</a>
        <a href="/admin/membership/usage">次数记录</a>
        <a href="/admin/payments">收款订单</a>
        <a href="/admin/referrals">推广分账</a>
        <a href="/admin/llm-settings">大模型配置</a>
        <a href="/admin/account">账号设置</a>
        <a href="/docs" target="_blank">接口文档</a>
        {user_bar}
      </nav>
      <main>{body}</main>
    </body>
    </html>
    """
    return HTMLResponse(html)


def admin_account(message: str = ''):
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    body = f'''
      <div class="card">
        <h2>后台账号设置</h2>
        {message_html}
        <p class="muted">修改管理后台登录密码。修改后需重新登录。</p>
        <form method="post" action="/admin/account/password">
          <div class="toolbar">
            <input name="old_password" type="password" placeholder="原密码" required />
            <input name="new_password" type="password" placeholder="新密码（至少6位）" required />
            <input name="confirm_password" type="password" placeholder="确认新密码" required />
            <button type="submit">修改密码</button>
          </div>
        </form>
      </div>
    '''
    return render_page('账号设置', body)


def admin_login(message: str = '', next_path: str = '/admin') -> HTMLResponse:
    safe_next = next_path if next_path.startswith('/admin') and not next_path.startswith('/admin/login') else '/admin'
    message_html = f'<p class="danger">{escape(message)}</p>' if message else ''
    html = f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>后台登录</title>
      <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f7fb; color: #17233d; }}
        .login-wrap {{ min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }}
        .card {{ background: white; border-radius: 18px; padding: 32px; box-shadow: 0 12px 32px rgba(22, 119, 255, .08); width: 100%; max-width: 420px; }}
        h1 {{ margin: 0 0 8px; font-size: 28px; }}
        .muted {{ color: #667085; line-height: 1.7; margin-bottom: 20px; }}
        .danger {{ color: #f04438; }}
        input {{ width: 100%; height: 44px; border: 1px solid #d0d5dd; border-radius: 10px; padding: 0 12px; margin-bottom: 14px; }}
        button {{ width: 100%; height: 44px; border: 0; border-radius: 999px; color: white; background: #1677ff; cursor: pointer; font-size: 16px; font-weight: 600; }}
      </style>
    </head>
    <body>
      <div class="login-wrap">
        <div class="card">
          <h1>管理后台登录</h1>
          <p class="muted">请输入账号和密码访问数据管理后台。</p>
          {message_html}
          <form method="post" action="/admin/login">
            <input type="hidden" name="next" value="{escape(safe_next)}" />
            <input name="username" placeholder="账号" autocomplete="username" required />
            <input name="password" type="password" placeholder="密码" autocomplete="current-password" required />
            <button type="submit">登录</button>
          </form>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(html)


def checked(val) -> str:
    return 'checked' if val else ''


def selected(val, current) -> str:
    return 'selected' if str(val) == str(current) else ''


def pagination_html(base_path: str, page: int, total: int, extra: dict | None = None, page_size: int = PAGE_SIZE) -> str:
    extra = extra or {}
    total_pages = max((total + page_size - 1) // page_size, 1)
    if total_pages <= 1:
        return f'<p class="muted">共 {total} 条</p>'
    parts = [f'<p class="muted">共 {total} 条，第 {page}/{total_pages} 页</p><div class="pagination">']
    for p in range(1, total_pages + 1):
        if p > 1 and p < total_pages and abs(p - page) > 2:
            if p == 2 or p == total_pages - 1:
                parts.append('<span>...</span>')
            continue
        if p == 1 or p == total_pages or abs(p - page) <= 1:
            params = {**extra, 'page': p}
            query = urlencode({k: v for k, v in params.items() if v})
            if p == page:
                parts.append(f'<span class="current">{p}</span>')
            else:
                parts.append(f'<a href="{base_path}?{query}">{p}</a>')
    parts.append('</div>')
    return ''.join(parts)


def school_options_html(selected_id: int | None = None) -> str:
    options = list_school_options()
    html = '<option value="">选择院校</option>'
    for item in options:
        html += f'<option value="{item["school_id"]}" {selected(str(item["school_id"]), selected_id)}>{escape(item["school_name"])} ({escape(item["school_code"])})</option>'
    return html


def major_options_html(selected_id: int | None = None) -> str:
    options = list_major_options()
    html = '<option value="">选择专业</option>'
    for item in options:
        html += f'<option value="{item["major_id"]}" {selected(str(item["major_id"]), selected_id)}>{escape(item["major_name"])} ({escape(item["major_code"])})</option>'
    return html


def table(headers: list[str], rows: list[dict], fields: list[str]) -> str:
    head = ''.join(f'<th>{escape(header)}</th>' for header in headers)
    body = ''
    for row in rows:
        cells = ''.join(f'<td>{escape(str(row.get(field, "") if row.get(field, "") is not None else ""))}</td>' for field in fields)
        body += f'<tr>{cells}</tr>'
    if not rows:
        body = f'<tr><td colspan="{len(headers)}" class="muted">暂无数据</td></tr>'
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def admin_home():
    stats = get_dashboard_stats()
    def rate_text(item):
        total = int(item.get('total') or 0)
        processed = int(item.get('processed') or 0)
        return '0%' if total == 0 else f'{processed / total * 100:.1f}%'

    business_counts = {
        '待处理申请': stats['pending_requests']['count'],
        '今日申请': stats['today_new_requests']['count'],
        '今日处理': stats['today_processed_requests']['count'],
        '申请转化率': rate_text(stats['request_conversion_total']),
        '开通转化率': rate_text(stats['request_conversion_open']),
        '续费转化率': rate_text(stats['request_conversion_renew']),
        '今日订单': stats['today_orders']['count'],
        '今日实收': f"¥{stats['today_orders']['amount']}",
        '今日新开通收入': f"¥{stats['today_open_orders']['amount']}",
        '今日续费收入': f"¥{stats['today_renew_orders']['amount']}",
        '累计实收': f"¥{stats['total_orders']['amount']}",
        '累计新开通收入': f"¥{stats['total_open_orders']['amount']}",
        '累计续费收入': f"¥{stats['total_renew_orders']['amount']}",
        '有效会员': stats['active_members']['count'],
        '7天内到期': stats['expiring_members']['count'],
        'AI今日消耗': stats['ai_today']['count']
    }
    with get_connection() as connection:
        data_counts = {
            '院校数量': connection.execute('SELECT COUNT(*) FROM schools').fetchone()[0],
            '专业数量': connection.execute('SELECT COUNT(*) FROM majors').fetchone()[0],
            '招生计划': connection.execute('SELECT COUNT(*) FROM enrollment_plans').fetchone()[0],
            '录取数据': connection.execute('SELECT COUNT(*) FROM admission_records').fetchone()[0]
        }
    business_cards = ''.join(f'<div class="card"><div class="muted">{escape(name)}</div><div class="stat">{value}</div></div>' for name, value in business_counts.items())
    data_cards = ''.join(f'<div class="card"><div class="muted">{escape(name)}</div><div class="stat">{value}</div></div>' for name, value in data_counts.items())
    request_rows = ''
    for request in stats['recent_requests']:
        request_rows += f'''
          <tr><td>{request.get('request_id', '')}</td><td>{escape(str(request.get('phone') or ''))}</td><td>{escape(str(request.get('student_name') or ''))}</td><td>{escape(str(request.get('plan_name') or request.get('plan_code') or ''))}</td><td>¥{escape(str(request.get('price') or 0))}</td><td>{escape(str(request.get('created_at') or ''))}</td></tr>
        '''
    if not request_rows:
        request_rows = '<tr><td colspan="6" class="muted">暂无待处理申请</td></tr>'
    order_rows = ''
    for order in stats['recent_orders']:
        order_rows += f'''
          <tr><td>{order.get('order_id', '')}</td><td>{escape(str(order.get('phone') or ''))}</td><td>{escape(str(order.get('student_name') or ''))}</td><td>{escape(str(order.get('plan_name') or ''))}</td><td>¥{escape(str(order.get('amount') or 0))}</td><td>{escape(str(order.get('paid_at') or ''))}</td></tr>
        '''
    if not order_rows:
        order_rows = '<tr><td colspan="6" class="muted">暂无订单</td></tr>'
    body = f'''
      <div class="card">
        <h2>运营看板</h2>
        <p class="muted">集中查看会员申请、订单收入、会员到期和 AI 使用情况。</p>
      </div>
      <div class="grid">{business_cards}</div>
      <div class="card">
        <h2>待处理开通申请</h2>
        <table><thead><tr><th>ID</th><th>手机号</th><th>姓名</th><th>套餐</th><th>应收</th><th>申请时间</th></tr></thead><tbody>{request_rows}</tbody></table>
        <p><a class="button" href="/admin/payments">去处理申请</a></p>
      </div>
      <div class="card">
        <h2>最近订单</h2>
        <table><thead><tr><th>ID</th><th>手机号</th><th>姓名</th><th>套餐</th><th>金额</th><th>支付时间</th></tr></thead><tbody>{order_rows}</tbody></table>
        <p><a class="button" href="/admin/payments">查看收款订单</a></p>
      </div>
      <div class="card">
        <h2>数据资产</h2>
        <div class="grid">{data_cards}</div>
        <p class="muted">录取数据越完整，推荐和风险检测越准确。</p>
        <a class="button" href="/admin/import">去导入数据</a>
        <a class="button btn-muted" href="/admin/crawler">在线采集</a>
      </div>
    '''
    return render_page('运营看板', body)


def admin_crawler(message: str = '', crawl_id: int | None = None):
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    recent_years = default_recent_years(3)
    overview = get_province_data_overview()
    configured_count = len(overview)
    ready_count = sum(1 for item in overview if item['admission_count'] > 0)
    running_any = has_running_crawl()
    province_options = ''.join(
        f'<option value="{escape(name)}">{escape(name)}</option>' for name in PROVINCE_IDS
    )
    year_checks = ''.join(
        f'<label style="display:inline-flex;align-items:center;gap:6px;margin-right:14px">'
        f'<input type="checkbox" name="years" value="{year}"{" checked" if year in recent_years else ""} /> {year}年</label>'
        for year in sorted(recent_years + [2022, 2021], reverse=True)
    )
    province_sections = ''
    for region in REGION_ORDER:
        region_rows = ''
        for item in overview:
            if item['region'] != region:
                continue
            status_tag = '<span class="tag">采集中</span>' if item['is_running'] else (
                '<span class="tag" style="background:#e8fff3;color:#12b76a">已有数据</span>' if item['admission_count'] else '<span class="tag" style="background:#f2f4f7;color:#667085">未采集</span>'
            )
            years_text = escape(str(item.get('years') or '—'))
            last_crawl = escape(str(item.get('last_success_at') or item.get('last_crawl_at') or '—'))
            disabled = 'disabled' if item['is_running'] else ''
            region_rows += f'''
              <tr>
                <td><strong>{escape(item["name"])}</strong><br><span class="muted">ID {escape(item["source_id"])}</span></td>
                <td>{status_tag}</td>
                <td>{item["admission_count"]}</td>
                <td>{item["plan_count"]}</td>
                <td>{item["rank_count"]}</td>
                <td>{years_text}</td>
                <td>{last_crawl}</td>
                <td class="toolbar" style="margin:0">
                  <form method="post" action="/admin/crawler/quick" style="display:inline">
                    <input type="hidden" name="province" value="{escape(item["name"])}" />
                    <input type="hidden" name="preset" value="trial" />
                    <button type="submit" class="btn-sm btn-muted" {disabled}>试跑</button>
                  </form>
                  <form method="post" action="/admin/crawler/quick" style="display:inline">
                    <input type="hidden" name="province" value="{escape(item["name"])}" />
                    <input type="hidden" name="preset" value="full_recent_3y" />
                    <button type="submit" class="btn-sm" {disabled}>近三年全量</button>
                  </form>
                  <a class="button btn-sm btn-muted" href="/admin/admissions?province={escape(item["name"])}">查看数据</a>
                </td>
              </tr>
            '''
        province_sections += f'''
          <div class="card">
            <h3>{escape(region)}</h3>
            <table>
              <thead>
                <tr>
                  <th>省份</th><th>状态</th><th>录取记录</th><th>招生计划</th><th>含位次</th><th>年份覆盖</th><th>最近采集</th><th>操作</th>
                </tr>
              </thead>
              <tbody>{region_rows}</tbody>
            </table>
          </div>
        '''
    detail_html = ''
    if crawl_id:
        log = get_crawl_log(crawl_id)
        if log:
            detail_html = f'''
              <div class="card">
                <h2>采集详情 #{crawl_id}</h2>
                <p><strong>数据源：</strong>{escape(str(log.get("source_name", "")))}</p>
                <p><strong>省份 / 年份：</strong>{escape(str(log.get("province", "")))} / {log.get("year", "")}</p>
                <p><strong>院校进度：</strong>{log.get("school_processed", 0)} / {log.get("school_total", 0)}</p>
                <p><strong>记录总数 / 成功 / 失败：</strong>{log.get("row_total", 0)} / {log.get("row_success", 0)} / {log.get("row_fail", 0)}</p>
                <p><strong>状态：</strong><span class="tag">{escape(str(log.get("status", "")))}</span></p>
                <p><strong>开始时间：</strong>{escape(str(log.get("created_at", "")))}</p>
                <p><strong>结束时间：</strong>{escape(str(log.get("finished_at") or "进行中"))}</p>
                <p><strong>错误信息：</strong></p>
                <textarea readonly style="width:100%;min-height:120px">{escape(str(log.get("error_message") or "无"))}</textarea>
                <p><a class="button btn-muted" href="/admin/crawler">返回列表</a></p>
              </div>
            '''
    logs = list_crawl_logs(30)
    log_rows = ''
    for row in logs:
        log_rows += f'''
          <tr>
            <td>{row.get("crawl_id", "")}</td>
            <td>{escape(str(row.get("province", "")))}</td>
            <td>{row.get("year", "")}</td>
            <td>{row.get("school_processed", 0)} / {row.get("school_total", 0)}</td>
            <td>{row.get("row_total", 0)}</td>
            <td>{row.get("row_success", 0)}</td>
            <td>{row.get("row_fail", 0)}</td>
            <td><span class="tag">{escape(str(row.get("status", "")))}</span></td>
            <td>{escape(str(row.get("created_at", "")))}</td>
            <td><a class="button btn-sm" href="/admin/crawler?crawl_id={row.get("crawl_id")}">详情</a></td>
          </tr>
        '''
    if not log_rows:
        log_rows = '<tr><td colspan="10" class="muted">暂无采集记录</td></tr>'
    running_hint = '<p class="muted">当前有采集任务在后台运行，相关省份按钮已暂时禁用。</p>' if running_any else ''
    body = f'''
      {detail_html}
      <div class="card">
        <h2>全国省份采集配置</h2>
        {message_html}
        {running_hint}
        <div class="grid">
          <div><div class="muted">已配置省份</div><div class="stat">{configured_count}</div></div>
          <div><div class="muted">已有本地数据</div><div class="stat">{ready_count}</div></div>
          <div><div class="muted">预设方案</div><div class="stat" style="font-size:18px">试跑 / 近三年全量 / 最近一年全量</div></div>
        </div>
        <p class="muted" style="margin-top:16px">
          已为全国 <strong>31 个生源省份</strong> 预置采集参数。需要哪个省的数据，在下方表格直接点「试跑」或「近三年全量」即可。
          全量采集约 3000 校 × 3 年，会在<strong>后台执行</strong>，可在采集日志查看进度。
        </p>
        <form method="post" action="/admin/crawler/quick" class="toolbar" style="margin-top:12px">
          <input type="hidden" name="preset" value="full_recent_3y" />
          <button type="submit" class="btn-muted" {"disabled" if running_any else ""}>全国 31 省近三年全量（依次后台执行）</button>
        </form>
        <p class="muted">命令行单省全量：<code>cd server && python crawler_service.py --province 河南 --preset full_recent_3y</code></p>
        <p class="muted">命令行全国全量：<code>cd server && python crawler_service.py --all-provinces --preset full_recent_3y</code></p>
      </div>
      {province_sections}
      <div class="card">
        <h2>自定义采集</h2>
        <p class="muted">
          数据来源：<strong>掌上高考 static-data.gaokao.cn</strong>。采集字段含最低分、最低位次、招生计划、选科要求等。
        </p>
        <form method="post" action="/admin/crawler/run">
          <div class="toolbar">
            <select name="province">{province_options}</select>
            <input name="school_limit" type="number" value="0" min="0" max="3000" placeholder="院校数量，0=全量" style="min-width:140px" />
            <button type="submit">自定义采集并导入</button>
          </div>
          <p style="margin:12px 0 8px"><strong>录取年份（可多选）：</strong></p>
          <div class="toolbar">{year_checks}</div>
        </form>
        <form method="post" action="/admin/crawler/schools" style="margin-top:12px">
          <div class="toolbar">
            <input name="school_limit" type="number" value="0" min="0" max="3000" placeholder="院校数量，0=全量" style="min-width:140px" />
            <button type="submit" class="btn-muted">仅同步全国院校库</button>
          </div>
        </form>
      </div>
      <div class="card">
        <h2>采集日志</h2>
        <table>
          <thead><tr><th>ID</th><th>省份</th><th>年份</th><th>院校进度</th><th>记录数</th><th>成功</th><th>失败</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>{log_rows}</tbody>
        </table>
      </div>
    '''
    return render_page('数据采集', body)


def admin_import(message: str = ''):
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    body = f'''
      <div class="card">
        <h2>导入历年录取数据</h2>
        {message_html}
        <p class="muted">支持 `.xlsx` 和 `.csv`。请使用模板字段：年份、省份、批次、院校代码、院校名称、专业代码、专业名称等。</p>
        <form action="/admin/import" method="post" enctype="multipart/form-data">
          <div class="toolbar">
            <input type="file" name="file" accept=".xlsx,.csv" required />
            <button type="submit">上传并导入</button>
            <a class="button" href="/api/import/logs" target="_blank">查看日志 JSON</a>
          </div>
        </form>
        <p class="muted">模板文件位置：<code>database/admission_import_template.csv</code></p>
      </div>
    '''
    return render_page('数据导入', body)


def admin_logs(log_id: int | None = None, message: str = ''):
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    detail_html = ''
    if log_id:
        log = get_import_log(log_id)
        if log:
            detail_html = f'''
              <div class="card">
                <h2>日志详情 #{log_id}</h2>
                <p><strong>类型：</strong>{escape(str(log.get("import_type", "")))}</p>
                <p><strong>文件名：</strong>{escape(str(log.get("file_name", "")))}</p>
                <p><strong>总数 / 成功 / 失败：</strong>{log.get("total_count", 0)} / {log.get("success_count", 0)} / {log.get("fail_count", 0)}</p>
                <p><strong>时间：</strong>{escape(str(log.get("created_at", "")))}</p>
                <p><strong>错误信息：</strong></p>
                <textarea readonly style="width:100%;min-height:120px">{escape(str(log.get("error_message") or "无"))}</textarea>
                <p><a class="button btn-muted" href="/admin/import/logs">返回列表</a></p>
              </div>
            '''
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute('SELECT * FROM import_logs ORDER BY created_at DESC LIMIT 100').fetchall())
    rows_html = ''
    for row in rows:
        rows_html += f'''
          <tr>
            <td>{row.get("log_id", "")}</td>
            <td>{escape(str(row.get("import_type", "")))}</td>
            <td>{escape(str(row.get("file_name", "")))}</td>
            <td>{row.get("total_count", 0)}</td>
            <td>{row.get("success_count", 0)}</td>
            <td>{row.get("fail_count", 0)}</td>
            <td>{escape(str(row.get("error_message") or "")[:80])}</td>
            <td>{escape(str(row.get("created_at", "")))}</td>
            <td><a class="button btn-sm" href="/admin/import/logs?log_id={row.get("log_id")}">详情</a></td>
          </tr>
        '''
    if not rows_html:
        rows_html = '<tr><td colspan="9" class="muted">暂无数据</td></tr>'
    body = f'''
      {detail_html}
      <div class="card">
        <h2>导入日志</h2>
        {message_html}
        <table><thead><tr><th>ID</th><th>类型</th><th>文件名</th><th>总数</th><th>成功</th><th>失败</th><th>错误</th><th>时间</th><th>操作</th></tr></thead><tbody>{rows_html}</tbody></table>
      </div>
    '''
    return render_page('导入日志', body)


def admin_schools(keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    rows, total = search_schools(keyword, page)
    edit = get_school(edit_id) if edit_id else None
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    form_title = f'编辑院校 #{edit_id}' if edit else '新增院校'
    form_action = f'/admin/schools/{edit_id}/save' if edit else '/admin/schools/create'
    rows_html = ''
    for row in rows:
        rows_html += f'''
          <tr>
            <td>{row.get("school_id", "")}</td>
            <td>{escape(str(row.get("school_code", "")))}</td>
            <td>{escape(str(row.get("school_name", "")))}</td>
            <td>{escape(str(row.get("province", "")))}</td>
            <td>{escape(str(row.get("city", "")))}</td>
            <td>{escape(str(row.get("school_type", "")))}</td>
            <td>{row.get("is_985", 0)}</td><td>{row.get("is_211", 0)}</td>
            <td>
              <a class="button btn-sm" href="/admin/schools?edit_id={row.get("school_id")}&keyword={escape(keyword)}&page={page}">编辑</a>
              <form method="post" action="/admin/schools/{row.get("school_id")}/delete" style="display:inline" onsubmit="return confirm('确认删除该院校？')">
                <button type="submit" class="btn-sm btn-danger">删除</button>
              </form>
            </td>
          </tr>
        '''
    if not rows_html:
        rows_html = '<tr><td colspan="9" class="muted">暂无数据</td></tr>'
    body = f'''
      <div class="card">
        <h2>{form_title}</h2>
        {message_html}
        <form class="toolbar" method="post" action="{form_action}">
          <input name="school_code" value="{escape(str((edit or {}).get("school_code", "")))}" placeholder="院校代码" required />
          <input name="school_name" value="{escape(str((edit or {}).get("school_name", "")))}" placeholder="院校名称" required />
          <input name="province" value="{escape(str((edit or {}).get("province", "")))}" placeholder="省份" />
          <input name="city" value="{escape(str((edit or {}).get("city", "")))}" placeholder="城市" />
          <input name="school_type" value="{escape(str((edit or {}).get("school_type", "")))}" placeholder="类型" />
          <input name="education_level" value="{escape(str((edit or {}).get("education_level", "")))}" placeholder="层次" />
          <label><input type="checkbox" name="is_985" value="1" {checked((edit or {}).get("is_985"))} /> 985</label>
          <label><input type="checkbox" name="is_211" value="1" {checked((edit or {}).get("is_211"))} /> 211</label>
          <label><input type="checkbox" name="is_double_first_class" value="1" {checked((edit or {}).get("is_double_first_class"))} /> 双一流</label>
          <label><input type="checkbox" name="is_public" value="1" {checked((edit or {}).get("is_public", 1))} /> 公办</label>
          <input name="website" value="{escape(str((edit or {}).get("website", "")))}" placeholder="官网" style="min-width:260px" />
          <button type="submit">{'保存修改' if edit else '新增院校'}</button>
          {f'<a class="button btn-muted" href="/admin/schools?keyword={escape(keyword)}&page={page}">取消编辑</a>' if edit else ''}
        </form>
      </div>
      <div class="card">
        <h2>院校列表</h2>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="院校名称 / 代码 / 城市 / 省份" />
          <button type="submit">搜索</button>
        </form>
        <table><thead><tr><th>ID</th><th>代码</th><th>名称</th><th>省份</th><th>城市</th><th>类型</th><th>985</th><th>211</th><th>操作</th></tr></thead><tbody>{rows_html}</tbody></table>
        {pagination_html('/admin/schools', page, total, {'keyword': keyword})}
      </div>
    '''
    return render_page('院校数据', body)


def admin_majors(keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    rows, total = search_majors(keyword, page)
    edit = get_major(edit_id) if edit_id else None
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    form_action = f'/admin/majors/{edit_id}/save' if edit else '/admin/majors/create'
    rows_html = ''
    for row in rows:
        rows_html += f'''
          <tr>
            <td>{row.get("major_id", "")}</td>
            <td>{escape(str(row.get("major_code", "")))}</td>
            <td>{escape(str(row.get("major_name", "")))}</td>
            <td>{escape(str(row.get("major_category", "")))}</td>
            <td>{escape(str(row.get("major_type", "")))}</td>
            <td>{escape(str(row.get("degree_type", "")))}</td>
            <td>{escape(str(row.get("duration", "")))}</td>
            <td>
              <a class="button btn-sm" href="/admin/majors?edit_id={row.get("major_id")}&keyword={escape(keyword)}&page={page}">编辑</a>
              <form method="post" action="/admin/majors/{row.get("major_id")}/delete" style="display:inline" onsubmit="return confirm('确认删除该专业？')">
                <button type="submit" class="btn-sm btn-danger">删除</button>
              </form>
            </td>
          </tr>
        '''
    if not rows_html:
        rows_html = '<tr><td colspan="8" class="muted">暂无数据</td></tr>'
    body = f'''
      <div class="card">
        <h2>{'编辑专业' if edit else '新增专业'}</h2>
        {message_html}
        <form class="toolbar" method="post" action="{form_action}">
          <input name="major_code" value="{escape(str((edit or {}).get("major_code", "")))}" placeholder="专业代码" required />
          <input name="major_name" value="{escape(str((edit or {}).get("major_name", "")))}" placeholder="专业名称" required />
          <input name="major_category" value="{escape(str((edit or {}).get("major_category", "")))}" placeholder="门类" />
          <input name="major_type" value="{escape(str((edit or {}).get("major_type", "")))}" placeholder="类型" />
          <input name="degree_type" value="{escape(str((edit or {}).get("degree_type", "")))}" placeholder="层次" />
          <input name="duration" value="{escape(str((edit or {}).get("duration", "")))}" placeholder="学制" />
          <button type="submit">{'保存修改' if edit else '新增专业'}</button>
          {f'<a class="button btn-muted" href="/admin/majors?keyword={escape(keyword)}&page={page}">取消编辑</a>' if edit else ''}
        </form>
      </div>
      <div class="card">
        <h2>专业列表</h2>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="专业名称 / 代码 / 类型" />
          <button type="submit">搜索</button>
        </form>
        <table><thead><tr><th>ID</th><th>代码</th><th>名称</th><th>门类</th><th>类型</th><th>层次</th><th>学制</th><th>操作</th></tr></thead><tbody>{rows_html}</tbody></table>
        {pagination_html('/admin/majors', page, total, {'keyword': keyword})}
      </div>
    '''
    return render_page('专业数据', body)


def admin_admissions(province: str = '', batch: str = '', year: str = '', keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    rows, total = search_admissions(province, batch, year, keyword, page)
    edit = get_admission(edit_id) if edit_id else None
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    form_action = f'/admin/admissions/{edit_id}/save' if edit else '/admin/admissions/create'
    rows_html = ''
    for row in rows:
        rows_html += f'''
          <tr>
            <td>{row.get("admission_id", "")}</td><td>{row.get("year", "")}</td><td>{escape(str(row.get("province", "")))}</td>
            <td>{escape(str(row.get("batch", "")))}</td><td>{escape(str(row.get("school_name", "")))}</td>
            <td>{escape(str(row.get("major_name", "")))}</td><td>{row.get("min_score", "")}</td><td>{row.get("min_rank", "")}</td>
            <td>
              <a class="button btn-sm" href="/admin/admissions?edit_id={row.get("admission_id")}&province={escape(province)}&batch={escape(batch)}&year={escape(year)}&keyword={escape(keyword)}&page={page}">编辑</a>
              <form method="post" action="/admin/admissions/{row.get("admission_id")}/delete" style="display:inline" onsubmit="return confirm('确认删除？')">
                <button type="submit" class="btn-sm btn-danger">删除</button>
              </form>
            </td>
          </tr>
        '''
    if not rows_html:
        rows_html = '<tr><td colspan="9" class="muted">暂无数据</td></tr>'
    body = f'''
      <div class="card">
        <h2>{'编辑录取数据' if edit else '新增录取数据'}</h2>
        {message_html}
        <form class="toolbar" method="post" action="{form_action}">
          <input name="year" value="{escape(str((edit or {}).get("year", year or "")))}" placeholder="年份" required />
          <input name="province" value="{escape(str((edit or {}).get("province", province or "")))}" placeholder="省份" required />
          <input name="batch" value="{escape(str((edit or {}).get("batch", batch or "")))}" placeholder="批次" required />
          <select name="school_id" required>{school_options_html((edit or {}).get("school_id"))}</select>
          <select name="major_id" required>{major_options_html((edit or {}).get("major_id"))}</select>
          <input name="min_score" value="{escape(str((edit or {}).get("min_score", "")))}" placeholder="最低分" />
          <input name="min_rank" value="{escape(str((edit or {}).get("min_rank", "")))}" placeholder="最低位次" />
          <input name="avg_score" value="{escape(str((edit or {}).get("avg_score", "")))}" placeholder="平均分" />
          <input name="avg_rank" value="{escape(str((edit or {}).get("avg_rank", "")))}" placeholder="平均位次" />
          <input name="enrollment_count" value="{escape(str((edit or {}).get("enrollment_count", "")))}" placeholder="招生人数" />
          <button type="submit">{'保存修改' if edit else '新增记录'}</button>
        </form>
      </div>
      <div class="card">
        <h2>录取数据列表</h2>
        <form class="toolbar" method="get">
          <input name="province" value="{escape(province)}" placeholder="省份" />
          <input name="batch" value="{escape(batch)}" placeholder="批次" />
          <input name="year" value="{escape(year)}" placeholder="年份" />
          <input name="keyword" value="{escape(keyword)}" placeholder="院校/专业名称" />
          <button type="submit">筛选</button>
        </form>
        <table><thead><tr><th>ID</th><th>年份</th><th>省份</th><th>批次</th><th>院校</th><th>专业</th><th>最低分</th><th>最低位次</th><th>操作</th></tr></thead><tbody>{rows_html}</tbody></table>
        {pagination_html('/admin/admissions', page, total, {'province': province, 'batch': batch, 'year': year, 'keyword': keyword})}
      </div>
    '''
    return render_page('录取数据', body)


def admin_enrollment_plans(province: str = '', batch: str = '', year: str = '', keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    rows, total = search_enrollment_plans(province, batch, year, keyword, page)
    edit = get_enrollment_plan(edit_id) if edit_id else None
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    form_action = f'/admin/enrollment-plans/{edit_id}/save' if edit else '/admin/enrollment-plans/create'
    rows_html = ''
    for row in rows:
        rows_html += f'''
          <tr>
            <td>{row.get("plan_id", "")}</td><td>{row.get("year", "")}</td><td>{escape(str(row.get("province", "")))}</td>
            <td>{escape(str(row.get("batch", "")))}</td><td>{escape(str(row.get("school_name", "")))}</td>
            <td>{escape(str(row.get("major_name", "")))}</td><td>{row.get("enrollment_count", "")}</td><td>{row.get("tuition", "")}</td>
            <td>
              <a class="button btn-sm" href="/admin/enrollment-plans?edit_id={row.get("plan_id")}&province={escape(province)}&batch={escape(batch)}&year={escape(year)}&keyword={escape(keyword)}&page={page}">编辑</a>
              <form method="post" action="/admin/enrollment-plans/{row.get("plan_id")}/delete" style="display:inline" onsubmit="return confirm('确认删除？')">
                <button type="submit" class="btn-sm btn-danger">删除</button>
              </form>
            </td>
          </tr>
        '''
    if not rows_html:
        rows_html = '<tr><td colspan="9" class="muted">暂无数据</td></tr>'
    body = f'''
      <div class="card">
        <h2>{'编辑招生计划' if edit else '新增招生计划'}</h2>
        {message_html}
        <form class="toolbar" method="post" action="{form_action}">
          <input name="year" value="{escape(str((edit or {}).get("year", year or "")))}" placeholder="年份" required />
          <input name="province" value="{escape(str((edit or {}).get("province", province or "")))}" placeholder="省份" required />
          <input name="batch" value="{escape(str((edit or {}).get("batch", batch or "")))}" placeholder="批次" required />
          <select name="school_id" required>{school_options_html((edit or {}).get("school_id"))}</select>
          <select name="major_id" required>{major_options_html((edit or {}).get("major_id"))}</select>
          <input name="subject_requirement" value="{escape(str((edit or {}).get("subject_requirement", "")))}" placeholder="选科要求" />
          <input name="enrollment_count" value="{escape(str((edit or {}).get("enrollment_count", "")))}" placeholder="招生人数" />
          <input name="tuition" value="{escape(str((edit or {}).get("tuition", "")))}" placeholder="学费" />
          <input name="duration" value="{escape(str((edit or {}).get("duration", "")))}" placeholder="学制" />
          <input name="campus" value="{escape(str((edit or {}).get("campus", "")))}" placeholder="校区" />
          <input name="special_notes" value="{escape(str((edit or {}).get("special_notes", "")))}" placeholder="备注" style="min-width:260px" />
          <button type="submit">{'保存修改' if edit else '新增计划'}</button>
        </form>
      </div>
      <div class="card">
        <h2>招生计划列表</h2>
        <form class="toolbar" method="get">
          <input name="province" value="{escape(province)}" placeholder="省份" />
          <input name="batch" value="{escape(batch)}" placeholder="批次" />
          <input name="year" value="{escape(year)}" placeholder="年份" />
          <input name="keyword" value="{escape(keyword)}" placeholder="院校/专业名称" />
          <button type="submit">筛选</button>
        </form>
        <table><thead><tr><th>ID</th><th>年份</th><th>省份</th><th>批次</th><th>院校</th><th>专业</th><th>人数</th><th>学费</th><th>操作</th></tr></thead><tbody>{rows_html}</tbody></table>
        {pagination_html('/admin/enrollment-plans', page, total, {'province': province, 'batch': batch, 'year': year, 'keyword': keyword})}
      </div>
    '''
    return render_page('招生计划', body)


def admin_province_rules(province: str = '', year: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    rows, total = search_province_rules(province, year, page)
    edit = get_province_rule(edit_id) if edit_id else None
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    form_action = f'/admin/province-rules/{edit_id}/save' if edit else '/admin/province-rules/create'
    rows_html = ''
    for row in rows:
        rows_html += f'''
          <tr>
            <td>{row.get("rule_id", "")}</td><td>{escape(str(row.get("province", "")))}</td><td>{row.get("year", "")}</td>
            <td>{escape(str(row.get("batch", "")))}</td><td>{escape(str(row.get("volunteer_mode", "")))}</td>
            <td>{row.get("school_count", "")}</td><td>{row.get("major_count_per_school", "")}</td>
            <td>
              <a class="button btn-sm" href="/admin/province-rules?edit_id={row.get("rule_id")}&province={escape(province)}&year={escape(year)}&page={page}">编辑</a>
              <form method="post" action="/admin/province-rules/{row.get("rule_id")}/delete" style="display:inline" onsubmit="return confirm('确认删除？')">
                <button type="submit" class="btn-sm btn-danger">删除</button>
              </form>
            </td>
          </tr>
        '''
    if not rows_html:
        rows_html = '<tr><td colspan="8" class="muted">暂无数据</td></tr>'
    body = f'''
      <div class="card">
        <h2>{'编辑省份规则' if edit else '新增省份规则'}</h2>
        {message_html}
        <form method="post" action="{form_action}">
          <div class="toolbar">
            <input name="province" value="{escape(str((edit or {}).get("province", province or "")))}" placeholder="省份" required />
            <input name="year" value="{escape(str((edit or {}).get("year", year or "")))}" placeholder="年份" required />
            <input name="batch" value="{escape(str((edit or {}).get("batch", "")))}" placeholder="批次" required />
            <input name="volunteer_mode" value="{escape(str((edit or {}).get("volunteer_mode", "")))}" placeholder="志愿模式" required />
            <input name="school_count" value="{escape(str((edit or {}).get("school_count", "")))}" placeholder="院校志愿数" />
            <input name="major_count_per_school" value="{escape(str((edit or {}).get("major_count_per_school", "")))}" placeholder="每校专业数" />
            <label><input type="checkbox" name="is_parallel_volunteer" value="1" {checked((edit or {}).get("is_parallel_volunteer", 1))} /> 平行志愿</label>
            <label><input type="checkbox" name="adjustment_supported" value="1" {checked((edit or {}).get("adjustment_supported", 1))} /> 支持调剂</label>
          </div>
          <div class="toolbar">
            <input name="score_priority_rule" value="{escape(str((edit or {}).get("score_priority_rule", "")))}" placeholder="分数优先规则" style="min-width:260px" />
            <textarea name="rule_description" placeholder="规则说明">{escape(str((edit or {}).get("rule_description", "")))}</textarea>
            <button type="submit">{'保存修改' if edit else '新增规则'}</button>
          </div>
        </form>
      </div>
      <div class="card">
        <h2>省份规则列表</h2>
        <form class="toolbar" method="get">
          <input name="province" value="{escape(province)}" placeholder="省份" />
          <input name="year" value="{escape(year)}" placeholder="年份" />
          <button type="submit">筛选</button>
        </form>
        <table><thead><tr><th>ID</th><th>省份</th><th>年份</th><th>批次</th><th>志愿模式</th><th>院校数</th><th>专业数</th><th>操作</th></tr></thead><tbody>{rows_html}</tbody></table>
        {pagination_html('/admin/province-rules', page, total, {'province': province, 'year': year})}
      </div>
    '''
    return render_page('省份规则', body)



def admin_students(keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    rows, total = search_students(keyword, page)
    edit = get_student(edit_id) if edit_id else None
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    edit_form = ''
    if edit:
        edit_form = f'''
          <div class="card">
            <h2>编辑学生档案 #{edit_id}</h2>
            {message_html}
            <form method="post" action="/admin/students/{edit_id}/save">
              <div class="toolbar">
                <input name="name" value="{escape(str(edit.get("name", "")))}" placeholder="姓名" required />
                <input name="phone" value="{escape(str(edit.get("phone", "")))}" placeholder="手机号" />
                <input name="province" value="{escape(str(edit.get("province", "")))}" placeholder="省份" required />
                <input name="city" value="{escape(str(edit.get("city", "")))}" placeholder="城市" />
                <input name="school_name" value="{escape(str(edit.get("school_name", "")))}" placeholder="学校" />
                <input name="grade" value="{escape(str(edit.get("grade", "")))}" placeholder="年级" />
                <input name="class_name" value="{escape(str(edit.get("class_name", "")))}" placeholder="班级" />
                <input name="exam_year" value="{escape(str(edit.get("exam_year", "")))}" placeholder="高考年份" required />
                <input name="subject_combination" value="{escape(str(edit.get("subject_combination", "")))}" placeholder="选科" required />
                <input name="score" value="{escape(str(edit.get("score", "")))}" placeholder="分数" required />
                <input name="rank" value="{escape(str(edit.get("rank", "")))}" placeholder="位次" required />
                <input name="target_batch" value="{escape(str(edit.get("target_batch", "")))}" placeholder="目标批次" required />
                <button type="submit">保存修改</button>
                <a class="button btn-muted" href="/admin/students?keyword={escape(keyword)}&page={page}">取消</a>
              </div>
            </form>
          </div>
        '''
    rows_html = ''
    for row in rows:
        rows_html += f'''
          <tr>
            <td>{row.get("student_id", "")}</td><td>{escape(str(row.get("phone", "")))}</td>
            <td>{escape(str(row.get("name", "")))}</td><td>{escape(str(row.get("school_name", "")))}</td>
            <td>{escape(str(row.get("class_name", "")))}</td><td>{row.get("score", "")}</td><td>{row.get("rank", "")}</td>
            <td>{escape(str(row.get("target_batch", "")))}</td>
            <td><a class="button btn-sm" href="/admin/students?edit_id={row.get("student_id")}&keyword={escape(keyword)}&page={page}">编辑</a></td>
          </tr>
        '''
    if not rows_html:
        rows_html = '<tr><td colspan="9" class="muted">暂无数据</td></tr>'
    body = f"""
      {edit_form}
      <div class="card">
        <h2>学生档案</h2>
        {'' if edit else message_html}
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="姓名 / 手机号 / 学校 / 班级" />
          <button type="submit">搜索</button>
          <a class="button" href="/admin/students/export?keyword={escape(keyword)}">导出 CSV</a>
        </form>
        <table><thead><tr><th>学生ID</th><th>手机号</th><th>姓名</th><th>学校</th><th>班级</th><th>分数</th><th>位次</th><th>批次</th><th>操作</th></tr></thead><tbody>{rows_html}</tbody></table>
        {pagination_html('/admin/students', page, total, {'keyword': keyword})}
      </div>
    """
    return render_page('学生档案', body)



def admin_data_sources(keyword: str = '', review_status: str = '', edit_id: int | None = None, message: str = ''):
    sources = list_sources(keyword)
    tasks = list_tasks()
    records = list_records(review_status=review_status or '')
    brochures = list_brochures(keyword)
    edit_source = None
    if edit_id:
        for source in sources:
            if source.get('source_id') == edit_id:
                edit_source = source
                break
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    rows_html = ''
    for source in sources:
        rows_html += f'''
          <tr>
            <td>{source.get('source_id', '')}</td>
            <td>{escape(str(source.get('school_name', '')))}</td>
            <td>{escape(str(source.get('source_name', '')))}</td>
            <td>{escape(str(source.get('data_type', '')))}</td>
            <td><a href="{escape(str(source.get('url', '')))}" target="_blank">打开</a></td>
            <td>{escape(str(source.get('last_status', '') or '未采集'))}</td>
            <td>{escape(str(source.get('last_fetch_at', '') or ''))}</td>
            <td>
              <form method="post" action="/admin/data-sources/{source.get('source_id')}/fetch" style="display:inline">
                <button type="submit" class="btn-sm">采集</button>
              </form>
              <a class="button btn-sm" href="/admin/data-sources?edit_id={source.get('source_id')}&keyword={escape(keyword)}">编辑</a>
              <form method="post" action="/admin/data-sources/{source.get('source_id')}/delete" style="display:inline" onsubmit="return confirm('确认删除？')">
                <button type="submit" class="btn-sm btn-danger">删除</button>
              </form>
            </td>
          </tr>
        '''
    if not rows_html:
        rows_html = '<tr><td colspan="8" class="muted">暂无数据源</td></tr>'

    record_rows = ''
    for record in records:
        status = record.get('review_status', 'pending')
        status_class = 'success' if status == 'approved' else ('danger' if status == 'rejected' else '')
        record_rows += f'''
          <tr>
            <td>{record.get('record_id', '')}</td>
            <td>{escape(str(record.get('school_name', '')))}</td>
            <td>{escape(str(record.get('record_type', '')))}</td>
            <td>{escape(str(record.get('title', '')))}</td>
            <td>{escape(str(record.get('file_ext', '')))}</td>
            <td class="{status_class}">{escape(str(status))}</td>
            <td><a href="{escape(str(record.get('url', '')))}" target="_blank">打开</a></td>
            <td>
              <form method="post" action="/admin/data-sources/records/{record.get('record_id')}/review" style="display:inline">
                <input type="hidden" name="review_status" value="approved" />
                <button type="submit" class="btn-sm">通过</button>
              </form>
              <form method="post" action="/admin/data-sources/records/{record.get('record_id')}/review" style="display:inline">
                <input type="hidden" name="review_status" value="rejected" />
                <button type="submit" class="btn-sm btn-danger">驳回</button>
              </form>
              <form method="post" action="/admin/data-sources/records/{record.get('record_id')}/archive" style="display:inline">
                <button type="submit" class="btn-sm btn-muted">归档章程</button>
              </form>
            </td>
          </tr>
        '''
    if not record_rows:
        record_rows = '<tr><td colspan="8" class="muted">暂无采集链接</td></tr>'

    brochure_rows = ''
    for item in brochures:
        brochure_rows += f'''
          <tr>
            <td>{item.get('brochure_id', '')}</td>
            <td>{escape(str(item.get('school_name', '')))}</td>
            <td>{item.get('year', '')}</td>
            <td>{escape(str(item.get('title', '')))}</td>
            <td><a href="{escape(str(item.get('source_url', '')))}" target="_blank">来源</a></td>
          </tr>
        '''
    if not brochure_rows:
        brochure_rows = '<tr><td colspan="5" class="muted">暂无已归档章程</td></tr>'

    edit_form = ''
    if edit_source:
        edit_form = f'''
          <div class="card">
            <h2>编辑数据源 #{edit_id}</h2>
            <form class="toolbar" method="post" action="/admin/data-sources/{edit_id}/save">
              <input name="school_name" value="{escape(str(edit_source.get('school_name', '')))}" required />
              <input name="school_code" value="{escape(str(edit_source.get('school_code', '')))}" />
              <input name="source_name" value="{escape(str(edit_source.get('source_name', '')))}" />
              <select name="data_type">
                <option value="招生信息" {selected('招生信息', edit_source.get('data_type'))}>招生信息</option>
                <option value="招生计划" {selected('招生计划', edit_source.get('data_type'))}>招生计划</option>
                <option value="招生章程" {selected('招生章程', edit_source.get('data_type'))}>招生章程</option>
                <option value="历年录取分数" {selected('历年录取分数', edit_source.get('data_type'))}>历年录取分数</option>
                <option value="专业介绍" {selected('专业介绍', edit_source.get('data_type'))}>专业介绍</option>
              </select>
              <input name="year" value="{escape(str(edit_source.get('year') or ''))}" placeholder="年份" />
              <input name="province" value="{escape(str(edit_source.get('province') or ''))}" placeholder="省份" />
              <input name="url" value="{escape(str(edit_source.get('url', '')))}" style="min-width:360px" required />
              <input name="remark" value="{escape(str(edit_source.get('remark') or ''))}" placeholder="备注" />
              <label><input type="checkbox" name="is_active" value="1" {checked(edit_source.get('is_active', 1))} /> 启用</label>
              <button type="submit">保存</button>
              <a class="button btn-muted" href="/admin/data-sources?keyword={escape(keyword)}">取消</a>
            </form>
          </div>
        '''

    task_table = table(
        ['任务ID', '数据源ID', '高校', '状态', '页面标题', '匹配链接', '错误', '时间'],
        tasks,
        ['task_id', 'source_id', 'school_name', 'task_status', 'page_title', 'matched_count', 'error_message', 'created_at']
    )
    body = f'''
      <div class="card">
        <h2>高校官方数据源</h2>
        {message_html}
        <p class="muted">配置高校招生官网 URL，自动发现招生计划、招生章程、历年录取分数等链接。采集结果需人工审核，通过后可归档到招生章程库。</p>
        {edit_form}
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="高校 / 数据源 / URL" />
          <button type="submit">搜索</button>
        </form>
        <form class="toolbar" method="post" action="/admin/data-sources">
          <input name="school_name" placeholder="高校名称" required />
          <input name="school_code" placeholder="高校代码" />
          <input name="source_name" placeholder="数据源名称" />
          <select name="data_type">
            <option value="招生信息">招生信息</option>
            <option value="招生计划">招生计划</option>
            <option value="招生章程">招生章程</option>
            <option value="历年录取分数">历年录取分数</option>
            <option value="专业介绍">专业介绍</option>
          </select>
          <input name="year" placeholder="年份" />
          <input name="province" placeholder="省份" />
          <input name="url" placeholder="https://..." style="min-width:360px" required />
          <input name="remark" placeholder="备注" />
          <button type="submit">新增数据源</button>
        </form>
        <table><thead><tr><th>ID</th><th>高校</th><th>数据源</th><th>类型</th><th>URL</th><th>状态</th><th>最近采集</th><th>操作</th></tr></thead><tbody>{rows_html}</tbody></table>
      </div>
      <div class="card"><h2>最近采集任务</h2>{task_table}</div>
      <div class="card">
        <h2>采集发现链接（人工审核）</h2>
        <form class="toolbar" method="get">
          <input type="hidden" name="keyword" value="{escape(keyword)}" />
          <select name="review_status">
            <option value="">全部状态</option>
            <option value="pending" {selected('pending', review_status)}>待审核</option>
            <option value="approved" {selected('approved', review_status)}>已通过</option>
            <option value="rejected" {selected('rejected', review_status)}>已驳回</option>
          </select>
          <button type="submit">筛选</button>
        </form>
        <table><thead><tr><th>ID</th><th>高校</th><th>类型</th><th>标题</th><th>扩展名</th><th>审核</th><th>链接</th><th>操作</th></tr></thead><tbody>{record_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>已归档招生章程</h2>
        <table><thead><tr><th>ID</th><th>高校</th><th>年份</th><th>标题</th><th>来源</th></tr></thead><tbody>{brochure_rows}</tbody></table>
      </div>
    '''
    return render_page('官方数据源', body)



def admin_llm_settings(message: str = ''):
    settings = get_llm_settings() or {}
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    enabled_checked = 'checked' if settings.get('is_enabled') else ''
    body = f'''
      <div class="card">
        <h2>大模型配置</h2>
        {message_html}
        <p class="muted">管理大模型 API 配置，已接入 AI 志愿方案解读。API Key 在页面中脱敏展示。</p>
        <form method="post" action="/admin/llm-settings">
          <div class="toolbar">
            <select name="provider">
              <option value="openai-compatible" {selected('openai-compatible', settings.get('provider'))}>OpenAI Compatible</option>
              <option value="deepseek" {selected('deepseek', settings.get('provider'))}>DeepSeek</option>
              <option value="qwen" {selected('qwen', settings.get('provider'))}>通义千问</option>
              <option value="zhipu" {selected('zhipu', settings.get('provider'))}>智谱</option>
            </select>
            <input name="base_url" value="{escape(str(settings.get('base_url') or ''))}" placeholder="Base URL，例如 https://api.openai.com/v1" style="min-width:360px" />
            <input name="model_name" value="{escape(str(settings.get('model_name') or ''))}" placeholder="模型名，例如 gpt-4o-mini / deepseek-chat" style="min-width:260px" />
            <input name="temperature" value="{escape(str(settings.get('temperature') or '0.7'))}" placeholder="temperature" />
          </div>
          <div class="toolbar">
            <input name="api_key" type="password" placeholder="API Key，留空则保留原 Key" style="min-width:460px" />
            <label class="muted"><input name="is_enabled" type="checkbox" value="1" {enabled_checked} /> 启用大模型</label>
            <input name="remark" value="{escape(str(settings.get('remark') or ''))}" placeholder="备注" />
            <button type="submit">保存配置</button>
            <button type="submit" formaction="/admin/llm-settings/test">测试连接</button>
          </div>
        </form>
        <p class="muted">当前 Key：<span class="tag">{escape(mask_api_key(settings.get('api_key')))}</span></p>
        <p class="muted">安全提示：生产环境建议把 Key 加密存储，并限制后台访问权限。</p>
      </div>
    '''
    return render_page('大模型配置', body)



def admin_membership_plans(message: str = ''):
    plans = list_plans()
    permissions = list_permissions()
    permission_map = get_plan_permission_map()
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    plan_rows = ''
    for plan in plans:
        checked = 'checked' if plan.get('is_active') else ''
        plan_rows += f'''
          <tr>
            <form method="post" action="/admin/membership/plans/save">
              <td><input name="plan_code" value="{escape(str(plan.get('plan_code', '')))}" readonly /></td>
              <td><input name="plan_name" value="{escape(str(plan.get('plan_name', '')))}" /></td>
              <td><input name="price" value="{escape(str(plan.get('price', '')))}" /></td>
              <td><input name="duration_days" value="{escape(str(plan.get('duration_days', '')))}" /></td>
              <td><input name="sort_order" value="{escape(str(plan.get('sort_order', '')))}" /></td>
              <td><label><input type="checkbox" name="is_active" value="1" {checked} /> 启用</label></td>
              <td><input name="description" value="{escape(str(plan.get('description', '')))}" style="min-width:260px" /></td>
              <td><button type="submit">保存</button></td>
            </form>
          </tr>
        '''
    permission_rows = ''
    for permission in permissions:
        permission_rows += f'<tr><td>{escape(str(permission.get("category") or ""))}</td><td>{escape(str(permission.get("permission_name") or ""))}</td>'
        for plan in plans:
            config = permission_map.get(plan['plan_code'], {}).get(permission['permission_code'], {})
            checked = 'checked' if config.get('is_enabled') else ''
            limit_value = config.get('limit_value', 0)
            permission_rows += f'''
              <td>
                <form method="post" action="/admin/membership/permissions/save" class="toolbar" style="margin:0">
                  <input type="hidden" name="plan_code" value="{escape(plan['plan_code'])}" />
                  <input type="hidden" name="permission_code" value="{escape(permission['permission_code'])}" />
                  <label><input type="checkbox" name="is_enabled" value="1" {checked} /> 开</label>
                  <input name="limit_value" value="{escape(str(limit_value))}" style="min-width:72px;width:72px" title="-1不限，0仅开关，正数为次数" />
                  <button type="submit">保存</button>
                </form>
              </td>
            '''
        permission_rows += '</tr>'
    plan_headers = ''.join(f'<th>{escape(str(plan.get("plan_name")))}</th>' for plan in plans)
    body = f'''
      <div class="card">
        <h2>会员套餐配置</h2>
        {message_html}
        <p class="muted">价格、有效期、启用状态都可自由调整。有效期 0 表示长期/免费；权限次数：-1 表示不限次，0 表示仅开关，正数表示限制次数。</p>
        <table><thead><tr><th>代码</th><th>名称</th><th>价格</th><th>天数</th><th>排序</th><th>状态</th><th>说明</th><th>操作</th></tr></thead><tbody>{plan_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>套餐权限矩阵</h2>
        <table><thead><tr><th>分类</th><th>权限</th>{plan_headers}</tr></thead><tbody>{permission_rows}</tbody></table>
      </div>
    '''
    return render_page('会员套餐配置', body)


def admin_membership_users(keyword: str = '', message: str = ''):
    users = search_users(keyword)
    expiring = list_expiring_members(7)
    plans = list_plans()
    options = ''.join(f'<option value="{escape(plan["plan_code"])}">{escape(plan["plan_name"])}（¥{plan["price"]}）</option>' for plan in plans if plan.get('is_active'))
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    rows = ''
    for user in users:
        rows += f'''
          <tr>
            <td>{user.get('user_id', '')}</td><td>{escape(str(user.get('phone') or ''))}</td><td>{escape(str(user.get('student_name') or user.get('name') or ''))}</td>
            <td>{escape(str(user.get('school_name') or ''))}</td><td>{escape(str(user.get('score') or ''))}</td><td>{escape(str(user.get('rank') or ''))}</td>
            <td><span class="tag">{escape(str(user.get('plan_name') or '免费版'))}</span><br/><span class="muted">{escape(str(user.get('expires_at') or '长期/未开通'))}</span></td>
            <td>
              <form method="post" action="/admin/membership/users/grant" class="toolbar" style="margin:0">
                <input type="hidden" name="user_id" value="{user.get('user_id', '')}" />
                <select name="plan_code">{options}</select>
                <input name="days" placeholder="天数，留空按套餐" style="min-width:120px;width:120px" />
                <input name="remark" placeholder="备注" />
                <button type="submit">开通/调整</button>
              </form>
              <form method="post" action="/admin/membership/users/revoke" style="display:inline;margin-top:6px" onsubmit="return confirm('确认撤销该用户会员？')">
                <input type="hidden" name="user_id" value="{user.get('user_id', '')}" />
                <button type="submit" class="btn-sm btn-danger">撤销会员</button>
              </form>
            </td>
          </tr>
        '''
    if not rows:
        rows = '<tr><td colspan="8" class="muted">暂无用户</td></tr>'
    expiring_rows = ''
    for member in expiring:
        expiring_rows += f'''
          <tr>
            <td>{member.get('user_id', '')}</td>
            <td>{escape(str(member.get('phone') or ''))}</td>
            <td>{escape(str(member.get('student_name') or member.get('user_name') or ''))}</td>
            <td>{escape(str(member.get('school_name') or ''))}</td>
            <td>{escape(str(member.get('plan_name') or member.get('plan_code') or ''))}</td>
            <td class="danger">{escape(str(member.get('expires_at') or ''))}</td>
            <td>
              <form method="post" action="/admin/payments/create" class="toolbar" style="margin:0">
                <input type="hidden" name="user_id" value="{member.get('user_id', '')}" />
                <input type="hidden" name="plan_code" value="{escape(str(member.get('plan_code') or ''))}" />
                <input type="hidden" name="days" value="{escape(str(member.get('duration_days') or 365))}" />
                <input type="hidden" name="redirect_to" value="/admin/membership/users" />
                <input type="hidden" name="order_type" value="renew" />
                <input name="amount" value="{escape(str(member.get('price') or 0))}" style="min-width:90px;width:90px" />
                <select name="pay_method"><option value="wechat_private">微信私聊</option><option value="wechat_work">企业微信</option><option value="manual">手动登记</option><option value="cash">现金</option></select>
                <input name="remark" value="续费跟进" style="min-width:120px;width:120px" />
                <button type="submit">生成续费订单</button>
              </form>
            </td>
          </tr>
        '''
    if not expiring_rows:
        expiring_rows = '<tr><td colspan="7" class="muted">未来 7 天暂无即将到期会员</td></tr>'
    body = f'''
      <div class="card">
        <h2>7天内即将到期会员</h2>
        <p class="muted">适合客服做续费提醒。确认收款后填写金额并生成续费订单，系统会同步延长会员。</p>
        <table><thead><tr><th>用户ID</th><th>手机号</th><th>姓名</th><th>学校</th><th>套餐</th><th>到期时间</th><th>续费</th></tr></thead><tbody>{expiring_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>用户会员管理</h2>
        {message_html}
        <p class="muted">个人主体阶段可用于手动开通/调整权益；企业主体接入微信支付后，也可继续作为客服后台。</p>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="手机号 / 姓名 / 学校" />
          <button type="submit">搜索</button>
        </form>
        <table><thead><tr><th>用户ID</th><th>手机号</th><th>姓名</th><th>学校</th><th>分数</th><th>位次</th><th>当前会员</th><th>开通/调整</th></tr></thead><tbody>{rows}</tbody></table>
      </div>
    '''
    return render_page('用户会员管理', body)



def admin_membership_usage(keyword: str = '', message: str = ''):
    usages = list_permission_usage(keyword)
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    rows = ''
    for item in usages:
        rows += f'''
          <tr>
            <td>{item.get('usage_id', '')}</td>
            <td>{item.get('user_id', '')}</td>
            <td>{escape(str(item.get('phone') or ''))}</td>
            <td>{escape(str(item.get('student_name') or item.get('user_name') or ''))}</td>
            <td>{escape(str(item.get('school_name') or ''))}</td>
            <td>{escape(str(item.get('plan_name') or item.get('plan_code') or ''))}</td>
            <td>{escape(str(item.get('permission_name') or item.get('permission_code') or ''))}</td>
            <td>{escape(str(item.get('period_key') or ''))}</td>
            <td><strong>{escape(str(item.get('used_count') or 0))}</strong></td>
            <td>{escape(str(item.get('updated_at') or ''))}</td>
            <td>
              <form method="post" action="/admin/membership/usage/reset" style="display:inline">
                <input type="hidden" name="usage_id" value="{item.get('usage_id', '')}" />
                <button type="submit" class="btn-sm">清零</button>
              </form>
              <form method="post" action="/admin/membership/usage/adjust" style="display:inline">
                <input type="hidden" name="usage_id" value="{item.get('usage_id', '')}" />
                <input type="hidden" name="delta" value="-1" />
                <button type="submit" class="btn-sm">-1</button>
              </form>
              <form method="post" action="/admin/membership/usage/adjust" style="display:inline">
                <input type="hidden" name="usage_id" value="{item.get('usage_id', '')}" />
                <input type="hidden" name="delta" value="1" />
                <button type="submit" class="btn-sm">+1</button>
              </form>
              <form method="post" action="/admin/membership/usage/delete" style="display:inline">
                <input type="hidden" name="usage_id" value="{item.get('usage_id', '')}" />
                <button type="submit" class="btn-sm btn-danger">删除</button>
              </form>
            </td>
          </tr>
        '''
    if not rows:
        rows = '<tr><td colspan="11" class="muted">暂无次数记录</td></tr>'
    body = f'''
      <div class="card">
        <h2>会员功能次数记录</h2>
        {message_html}
        <p class="muted">用于客服处理误扣次数、活动赠送、用户投诉等场景。清零会保留记录但 used_count 变为 0；删除会移除该周期记录。</p>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="手机号 / 姓名 / 学校 / 权限码" />
          <button type="submit">搜索</button>
          <a class="button" href="/admin/membership/usage/export?keyword={escape(keyword)}">导出 CSV</a>
        </form>
        <table><thead><tr><th>ID</th><th>用户ID</th><th>手机号</th><th>姓名</th><th>学校</th><th>套餐</th><th>功能</th><th>周期</th><th>已用</th><th>更新时间</th><th>操作</th></tr></thead><tbody>{rows}</tbody></table>
      </div>
    '''
    return render_page('会员次数记录', body)



def admin_payments(keyword: str = '', message: str = ''):
    orders = list_orders(keyword)
    open_requests = list_open_requests('pending')
    plans = list_plans()
    users = search_users('')[:200]
    stats = get_order_stats()
    support = get_support_contact()
    plan_options = ''.join(f'<option value="{escape(plan["plan_code"])}">{escape(plan["plan_name"])}（¥{plan["price"]}）</option>' for plan in plans if plan.get('is_active'))
    user_options = ''.join(f'<option value="{user["user_id"]}">{user["user_id"]} - {escape(str(user.get("phone") or ""))} - {escape(str(user.get("student_name") or user.get("name") or ""))}</option>' for user in users)
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    rows = ''
    for order in orders:
        order_type_text = '续费' if order.get('order_type') == 'renew' else ('开通' if order.get('order_type') == 'open' else '手动')
        rows += f'''
          <tr>
            <td>{order.get('order_id', '')}</td>
            <td>{escape(str(order.get('order_no') or ''))}</td>
            <td>{escape(str(order.get('phone') or ''))}</td>
            <td>{escape(str(order.get('student_name') or order.get('user_name') or ''))}</td>
            <td>{escape(str(order.get('plan_name') or order.get('plan_code') or ''))}</td>
            <td>¥{escape(str(order.get('amount') or 0))}</td>
            <td><span class="tag">{order_type_text}</span></td>
            <td>{escape(str(order.get('pay_method') or ''))}</td>
            <td><span class="tag">{escape(str(order.get('pay_status') or ''))}</span></td>
            <td>{escape(str(order.get('payer_contact') or ''))}</td>
            <td>{escape(str(order.get('paid_at') or ''))}</td>
            <td>{escape(str(order.get('remark') or ''))}</td>
            <td>
              {f'<form method="post" action="/admin/payments/{order.get("order_id")}/refund" style="display:inline" onsubmit="return confirm(\'确认退款？\')"><button type="submit" class="btn-sm btn-danger">退款</button></form>' if order.get('pay_status') == 'paid' else ''}
            </td>
          </tr>
        '''
    if not rows:
        rows = '<tr><td colspan="13" class="muted">暂无订单</td></tr>'
    request_rows = ''
    for request in open_requests:
        request_type_text = '续费' if request.get('request_type') == 'renew' else '开通'
        request_rows += f'''
          <tr>
            <td>{request.get('request_id', '')}</td>
            <td>{request.get('user_id', '')}</td>
            <td>{escape(str(request.get('phone') or ''))}</td>
            <td>{escape(str(request.get('student_name') or request.get('user_name') or ''))}</td>
            <td>{escape(str(request.get('school_name') or ''))}</td>
            <td>{escape(str(request.get('plan_name') or request.get('plan_code') or ''))}</td>
            <td><span class="tag">{request_type_text}</span></td>
            <td>¥{escape(str(request.get('price') or 0))}</td>
            <td>{escape(str(request.get('contact_name') or ''))}</td>
            <td>{escape(str(request.get('contact_phone') or ''))}</td>
            <td>{escape(str(request.get('message') or ''))}</td>
            <td>{escape(str(request.get('created_at') or ''))}</td>
            <td>
              <form method="post" action="/admin/payments/requests/confirm" class="toolbar" style="margin:0">
                <input type="hidden" name="request_id" value="{request.get('request_id', '')}" />
                <input name="amount" value="{escape(str(request.get('price') or 0))}" style="min-width:90px;width:90px" />
                <select name="pay_method"><option value="wechat_private">微信私聊</option><option value="wechat_work">企业微信</option><option value="manual">手动登记</option><option value="cash">现金</option></select>
                <button type="submit">确认开通</button>
              </form>
              <form method="post" action="/admin/payments/requests/cancel" style="display:inline">
                <input type="hidden" name="request_id" value="{request.get('request_id', '')}" />
                <button type="submit" style="background:#f04438">取消</button>
              </form>
            </td>
          </tr>
        '''
    if not request_rows:
        request_rows = '<tr><td colspan="13" class="muted">暂无待处理申请</td></tr>'
    body = f'''
      <div class="grid">
        <div class="card"><div class="muted">累计实收</div><div class="stat">¥{stats['total']['amount']}</div></div>
        <div class="card"><div class="muted">累计订单</div><div class="stat">{stats['total']['count']}</div></div>
        <div class="card"><div class="muted">今日实收</div><div class="stat">¥{stats['today']['amount']}</div></div>
        <div class="card"><div class="muted">今日订单</div><div class="stat">{stats['today']['count']}</div></div>
      </div>
      <div class="card">
        <h2>客服联系方式配置</h2>
        <p class="muted">这些信息会展示在小程序会员中心和提交申请后的提示中，用于引导用户付款和联系人工客服。</p>
        <form method="post" action="/admin/payments/support-contact">
          <div class="toolbar">
            <input name="support_wechat" value="{escape(support.get('support_wechat') or '')}" placeholder="客服微信号" />
            <input name="support_phone" value="{escape(support.get('support_phone') or '')}" placeholder="客服电话" />
            <input name="support_note" value="{escape(support.get('support_note') or '')}" placeholder="开通说明" style="min-width:360px" />
            <button type="submit">保存客服配置</button>
          </div>
        </form>
      </div>
      <div class="card">
        <h2>待处理开通申请</h2>
        <p class="muted">用户在小程序会员中心提交开通意向后会出现在这里。确认收到款项后点击“确认开通”，系统会生成订单并开通会员。</p>
        <p><a class="button" href="/admin/payments/requests/export?status=pending">导出待处理申请 CSV</a> <a class="button" href="/admin/payments/requests/export">导出全部申请 CSV</a></p>
        <table><thead><tr><th>ID</th><th>用户ID</th><th>手机号</th><th>姓名</th><th>学校</th><th>套餐</th><th>类型</th><th>应收</th><th>联系人</th><th>联系方式</th><th>留言</th><th>时间</th><th>操作</th></tr></thead><tbody>{request_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>手动登记收款并开通会员</h2>
        {message_html}
        <p class="muted">个人主体阶段可在此登记线下/企业微信/私聊收款，并自动给用户开通套餐。企业主体接入微信支付后也可复用为订单后台。</p>
        <form method="post" action="/admin/payments/create">
          <div class="toolbar">
            <select name="user_id">{user_options}</select>
            <select name="plan_code">{plan_options}</select>
            <input name="amount" placeholder="实收金额" />
            <input name="days" placeholder="自定义天数，留空按套餐" />
            <select name="order_type">
              <option value="manual">手动调整</option>
              <option value="open">新开通</option>
              <option value="renew">续费</option>
            </select>
            <select name="pay_method">
              <option value="manual">手动登记</option>
              <option value="wechat_private">微信私聊</option>
              <option value="wechat_work">企业微信</option>
              <option value="cash">现金</option>
              <option value="wechat_pay">微信支付</option>
            </select>
            <input name="payer_name" placeholder="付款人" />
            <input name="payer_contact" placeholder="联系方式/微信号" />
            <input name="remark" placeholder="备注" />
            <button type="submit">登记并开通</button>
          </div>
        </form>
      </div>
      <div class="card">
        <h2>订单记录</h2>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="订单号 / 手机号 / 姓名 / 联系方式" />
          <button type="submit">搜索</button>
          <a class="button" href="/admin/payments/export?keyword={escape(keyword)}">导出 CSV</a>
        </form>
        <table><thead><tr><th>ID</th><th>订单号</th><th>手机号</th><th>姓名</th><th>套餐</th><th>金额</th><th>类型</th><th>方式</th><th>状态</th><th>联系方式</th><th>支付时间</th><th>备注</th><th>操作</th></tr></thead><tbody>{rows}</tbody></table>
      </div>
    '''
    return render_page('收款订单', body)


def admin_referrals(keyword: str = '', tab: str = 'agents', message: str = ''):
    from referral_service import list_agents, list_bindings, list_commissions
    from referral_p1 import get_referral_policy_settings, trace_attribution, list_verify_logs
    from referral_p2 import get_bonus_settings, list_materials, list_poster_templates
    from poster_compose_service import get_poster_layout

    policy = get_referral_policy_settings()
    bonus = get_bonus_settings()
    materials = list_materials(active_only=False)
    poster_templates = list_poster_templates()
    poster_layout = get_poster_layout()
    default_rate = policy.get('commission_rate', 10)
    trace = trace_attribution(keyword) if keyword else {'bindings': [], 'commissions': [], 'orders': []}
    verify_logs = list_verify_logs(30)
    agents = list_agents(keyword)
    bindings = list_bindings(keyword)
    commissions = list_commissions(keyword)
    pending_total = sum(float(item.get('commission_amount') or 0) for item in commissions if item.get('status') == 'pending')
    settled_total = sum(float(item.get('commission_amount') or 0) for item in commissions if item.get('status') == 'settled')

    agent_rows = ''.join(
        f'''<tr>
          <td>{item.get("agent_id")}</td>
          <td>{escape(str(item.get("display_name") or ""))}</td>
          <td><code>{escape(str(item.get("invite_code") or ""))}</code></td>
          <td>{escape(str(item.get("user_name") or ""))}<br><span class="muted">{escape(str(item.get("user_phone") or ""))}</span></td>
          <td>{escape(str(item.get("agent_level") or "L1"))}</td>
          <td>{escape(str(item.get("tags") or ""))}<br><span class="muted">{escape(str(item.get("douyin_id") or ""))} {escape(str(item.get("fan_scale") or ""))}</span></td>
          <td>
            <form method="post" action="/admin/referrals/agent-rate" class="inline-form">
              <input type="hidden" name="agent_id" value="{item.get('agent_id')}" />
              <input name="commission_rate" value="{item.get('commission_rate')}" style="width:72px" />%
              <button type="submit" class="btn-sm">改</button>
            </form>
          </td>
          <td>{item.get("total_invites")}</td>
          <td>{item.get("total_paid_orders")}</td>
          <td>¥{item.get("total_commission")}</td>
          <td>¥{item.get("settled_commission")}</td>
          <td>{escape(str(item.get("status") or ""))}
            <form method="post" action="/admin/referrals/agent-blacklist" style="display:inline">
              <input type="hidden" name="agent_id" value="{item.get('agent_id')}" />
              <input type="hidden" name="blacklisted" value="{0 if int(item.get('is_blacklisted') or 0) else 1}" />
              <button type="submit" class="btn-sm">{'解除拉黑' if int(item.get('is_blacklisted') or 0) else '拉黑'}</button>
            </form>
          </td>
        </tr>'''
        for item in agents
    ) or '<tr><td colspan="12" class="muted">暂无博主</td></tr>'

    agent_profile_forms = ''.join(
        f'''<form class="toolbar" method="post" action="/admin/referrals/agent-profile">
          <input type="hidden" name="agent_id" value="{item.get('agent_id')}" />
          <input name="display_name" value="{escape(str(item.get('display_name') or ''))}" placeholder="昵称" />
          <input name="tags" value="{escape(str(item.get('tags') or ''))}" placeholder="标签(头部/腰部/素人)" />
          <input name="douyin_id" value="{escape(str(item.get('douyin_id') or ''))}" placeholder="抖音号" />
          <input name="fan_scale" value="{escape(str(item.get('fan_scale') or ''))}" placeholder="粉丝量级" />
          <button type="submit">保存达人#{item.get('agent_id')}</button>
        </form>'''
        for item in agents[:20]
    )

    poster_bg_forms = ''.join(
        f'''<form class="toolbar" method="post" action="/admin/referrals/poster-bg" enctype="multipart/form-data">
          <strong>{escape(str(item.get('template_name') or item.get('template_key') or ''))}</strong>
          <code>{escape(str(item.get('template_key') or ''))}</code>
          <span class="muted">当前背景：{escape(str(item.get('bg_image_path') or '纯色 ' + str(item.get('bg_color') or '')))}</span>
          <input type="hidden" name="template_key" value="{escape(str(item.get('template_key') or ''))}" />
          <input type="file" name="file" accept=".png,.jpg,.jpeg,.webp" />
          <button type="submit">上传背景图</button>
        </form>'''
        for item in poster_templates
    )

    material_rows = ''.join(
        f'''<tr>
          <td>{item.get('material_id')}</td>
          <td>{escape(str(item.get('category') or ''))}</td>
          <td>{escape(str(item.get('title') or ''))}</td>
          <td><pre style="white-space:pre-wrap">{escape(str(item.get('content') or ''))}</pre></td>
          <td>
            <form method="post" action="/admin/referrals/materials/delete" style="display:inline">
              <input type="hidden" name="material_id" value="{item.get('material_id')}" />
              <button type="submit">删除</button>
            </form>
          </td>
        </tr>'''
        for item in materials
    ) or '<tr><td colspan="5" class="muted">暂无素材</td></tr>'

    binding_rows = ''.join(
        f'''<tr>
          <td>{item.get("binding_id")}</td>
          <td>{escape(str(item.get("agent_name") or ""))}<br><code>{escape(str(item.get("agent_invite_code") or ""))}</code></td>
          <td>{escape(str(item.get("invitee_name") or ""))}<br><span class="muted">{escape(str(item.get("invitee_phone") or ""))}</span></td>
          <td>{escape(str(item.get("bind_source") or ""))}</td>
          <td>{escape(str(item.get("bound_at") or ""))}</td>
        </tr>'''
        for item in bindings
    ) or '<tr><td colspan="5" class="muted">暂无推广用户</td></tr>'

    commission_rows = ''.join(
        f'''<tr>
          <td>{item.get("commission_id")}</td>
          <td>{escape(str(item.get("order_no") or ""))}</td>
          <td>{escape(str(item.get("agent_name") or ""))}</td>
          <td>{escape(str(item.get("invitee_name") or ""))}<br><span class="muted">{escape(str(item.get("invitee_phone") or ""))}</span></td>
          <td>¥{item.get("order_amount")}</td>
          <td>{item.get("commission_rate")}%</td>
          <td>¥{item.get("commission_amount")}</td>
          <td>{escape(str(item.get("status") or ""))}</td>
          <td>{escape(str(item.get("created_at") or ""))}</td>
          <td>
            {'<form method="post" action="/admin/referrals/settle" style="display:inline"><input type="hidden" name="commission_id" value="' + str(item.get("commission_id")) + '" /><button type="submit">确认分账</button></form>' if item.get('status') == 'pending' else escape(str(item.get('settled_at') or ''))}
            <form method="post" action="/admin/referrals/commission-adjust" style="display:inline;margin-left:6px">
              <input type="hidden" name="commission_id" value="{item.get('commission_id')}" />
              <input name="commission_amount" value="{item.get('commission_amount')}" style="width:72px" />
              <button type="submit" class="btn-sm">调佣金</button>
            </form>
          </td>
        </tr>'''
        for item in commissions
    ) or '<tr><td colspan="10" class="muted">暂无分账记录</td></tr>'

    trace_binding_rows = ''.join(
        f'<tr><td>{escape(str(i.get("invitee_name") or ""))}</td><td>{escape(str(i.get("invitee_phone") or ""))}</td><td>{i.get("user_id")}</td><td>{escape(str(i.get("agent_name") or ""))}</td><td>{i.get("agent_id")}</td><td>{escape(str(i.get("bound_at") or ""))}</td></tr>'
        for i in trace.get('bindings', [])
    ) or '<tr><td colspan="6" class="muted">无匹配绑定</td></tr>'

    verify_rows = ''.join(
        f'<tr><td>{i.get("log_id")}</td><td>{escape(str(i.get("action") or ""))}</td><td>{escape(str(i.get("result") or ""))}</td><td>{escape(str(i.get("invite_code") or ""))}</td><td>{i.get("user_id") or ""}</td><td>{escape(str(i.get("detail") or ""))}</td><td>{escape(str(i.get("created_at") or ""))}</td></tr>'
        for i in verify_logs
    )

    body = f'''
      <div class="card">
        <h2>推广分账</h2>
        <p class="muted">博主扫码进入小程序领取专属海报；用户扫海报后绑定推广关系。用户支付成功后自动生成待分账记录，平台确认后标记已结算。</p>
        {f'<div class="notice">{escape(message)}</div>' if message else ''}
        <div class="stats">
          <div class="stat"><div class="stat-label">博主数</div><div class="stat-value">{len(agents)}</div></div>
          <div class="stat"><div class="stat-label">推广用户</div><div class="stat-value">{len(bindings)}</div></div>
          <div class="stat"><div class="stat-label">待分账</div><div class="stat-value">¥{pending_total:.2f}</div></div>
          <div class="stat"><div class="stat-label">已分账</div><div class="stat-value">¥{settled_total:.2f}</div></div>
          <div class="stat"><div class="stat-label">默认佣金比例</div><div class="stat-value">{default_rate}%</div></div>
        </div>
        <form class="toolbar" method="post" action="/admin/referrals/policy">
          <label>默认分账%</label><input name="commission_rate" value="{default_rate}" style="width:72px" />
          <label>归属规则</label>
          <select name="attribution_mode">
            <option value="permanent" {'selected' if policy.get('attribution_mode') == 'permanent' else ''}>永久归属</option>
            <option value="timed" {'selected' if policy.get('attribution_mode') == 'timed' else ''}>限时归属</option>
          </select>
          <label>限时天数</label><input name="attribution_days" value="{policy.get('attribution_days', 30)}" style="width:72px" />
          <label>结算周期</label>
          <select name="settlement_cycle">
            <option value="daily" {'selected' if policy.get('settlement_cycle') == 'daily' else ''}>日结</option>
            <option value="weekly" {'selected' if policy.get('settlement_cycle') == 'weekly' else ''}>周结</option>
            <option value="monthly" {'selected' if policy.get('settlement_cycle') == 'monthly' else ''}>月结</option>
          </select>
          <label>最低提现</label><input name="min_withdraw_amount" value="{policy.get('min_withdraw_amount', 10)}" style="width:72px" />
          <label>扫码福利豆</label><input name="bonus_beans" value="{bonus.get('bonus_beans', 200)}" style="width:72px" title="用户扫达人海报绑定后自动发放" />
          <label>体验天数</label><input name="bonus_days" value="{bonus.get('bonus_days', 3)}" style="width:72px" />
          <span class="muted">用户扫码绑定达人后领取 {bonus.get('bonus_beans', 200)} 星鼎豆（海报与弹窗展示）</span>
          <button type="submit">保存策略</button>
          <a class="button" href="/admin/referrals/overview">全局大盘</a>
          <a class="button" href="/admin/referrals/export">导出对账CSV</a>
          <a class="button" href="/admin/referrals/agents/export">导出达人CSV</a>
          <a class="button" href="/admin/referrals/withdrawals">提现审核</a>
        </form>
        <form class="toolbar" method="post" action="/admin/referrals/agents/import" enctype="multipart/form-data">
          <input type="file" name="file" accept=".csv,.xlsx" />
          <button type="submit">批量导入达人</button>
        </form>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="用户ID / 手机号 / 订单号 / 达人ID / 邀请码（归属溯源）" />
          <button type="submit">搜索/溯源</button>
        </form>
      </div>
      <div class="card">
        <h2>归属溯源</h2>
        <table><thead><tr><th>用户</th><th>手机</th><th>用户ID</th><th>达人</th><th>达人ID</th><th>绑定时间</th></tr></thead><tbody>{trace_binding_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>核销/绑定日志（最近30条）</h2>
        <table><thead><tr><th>ID</th><th>动作</th><th>结果</th><th>邀请码</th><th>用户ID</th><th>详情</th><th>时间</th></tr></thead><tbody>{verify_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>推广博主</h2>
        <table><thead><tr><th>ID</th><th>博主名</th><th>邀请码</th><th>绑定微信用户</th><th>等级</th><th>标签/抖音</th><th>佣金%</th><th>推广人数</th><th>付费单</th><th>累计佣金</th><th>已结算</th><th>状态</th></tr></thead><tbody>{agent_rows}</tbody></table>
        {agent_profile_forms}
      </div>
      <div class="card">
        <h2>海报背景图（自定义设计稿）</h2>
        <p class="muted">标准尺寸 <strong>{poster_layout.get('width')} × {poster_layout.get('height')}</strong> 像素（比例 5:8）。
        建议用 <strong>{poster_layout['design_size_2x']['width']} × {poster_layout['design_size_2x']['height']}</strong> 设计后导出 PNG/JPG。
        小程序码区域请留白：居中 <strong>{poster_layout.get('qr_size')}×{poster_layout.get('qr_size')}</strong>，
        坐标约 ({poster_layout.get('qr_x')}, {poster_layout.get('qr_y')})；顶部/底部留空给系统叠字。</p>
        <p class="muted">小程序码已开启透明底（is_hyaline），可叠在自定义背景上。</p>
        {poster_bg_forms}
      </div>
      <div class="card">
        <h2>推广素材库</h2>
        <form class="toolbar" method="post" action="/admin/referrals/materials/save">
          <input name="category" placeholder="分类(话术/口播/短视频)" />
          <input name="title" placeholder="标题" />
          <input name="content" placeholder="内容" style="min-width:320px" />
          <input name="sort_order" value="0" style="width:72px" />
          <button type="submit">新增素材</button>
        </form>
        <table><thead><tr><th>ID</th><th>分类</th><th>标题</th><th>内容</th><th>操作</th></tr></thead><tbody>{material_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>推广用户绑定</h2>
        <table><thead><tr><th>ID</th><th>博主</th><th>用户</th><th>来源</th><th>绑定时间</th></tr></thead><tbody>{binding_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>分账记录</h2>
        <table><thead><tr><th>ID</th><th>订单号</th><th>博主</th><th>用户</th><th>订单额</th><th>比例</th><th>佣金</th><th>状态</th><th>时间</th><th>操作</th></tr></thead><tbody>{commission_rows}</tbody></table>
      </div>
    '''
    return render_page('推广分账', body)


def admin_referrals_overview(days: int = 30, message: str = ''):
    import json
    from referral_p3 import (
        get_global_stats, get_level_config, list_faqs, list_douyin_invites,
        get_douyin_invite_template, get_auto_pay_settings, FOLLOW_UP_COMPLIANCE_NOTICE,
    )

    stats = get_global_stats(days)
    levels = get_level_config()
    faqs = list_faqs(active_only=False)
    invites = list_douyin_invites()
    auto_pay = get_auto_pay_settings()
    template = get_douyin_invite_template()

    daily_bind_rows = ''.join(
        f'<tr><td>{escape(str(i.get("day") or ""))}</td><td>{i.get("binds")}</td></tr>'
        for i in stats.get('daily_binds', [])
    ) or '<tr><td colspan="2" class="muted">暂无数据</td></tr>'

    daily_order_rows = ''.join(
        f'<tr><td>{escape(str(i.get("day") or ""))}</td><td>{i.get("orders")}</td><td>¥{i.get("commission")}</td></tr>'
        for i in stats.get('daily_orders', [])
    ) or '<tr><td colspan="3" class="muted">暂无数据</td></tr>'

    top_agent_rows = ''.join(
        f'''<tr>
          <td>{i.get("agent_id")}</td>
          <td>{escape(str(i.get("display_name") or ""))}</td>
          <td><code>{escape(str(i.get("invite_code") or ""))}</code></td>
          <td>{escape(str(i.get("agent_level") or ""))}</td>
          <td>{i.get("total_invites")}</td>
          <td>{i.get("total_paid_orders")}</td>
          <td>¥{i.get("range_commission")}</td>
        </tr>'''
        for i in stats.get('top_agents', [])
    ) or '<tr><td colspan="7" class="muted">暂无排行</td></tr>'

    level_rows = ''.join(
        f'<tr><td>{escape(str(i.get("agent_level") or ""))}</td><td>{i.get("count")}</td></tr>'
        for i in stats.get('level_distribution', [])
    ) or '<tr><td colspan="2" class="muted">暂无数据</td></tr>'

    level_config_rows = ''.join(
        f'<tr><td>{escape(str(i.get("level_key") or ""))}</td><td>{escape(str(i.get("level_name") or ""))}</td>'
        f'<td>{i.get("min_paid_orders")}</td><td>+{i.get("rate_bonus")}%</td></tr>'
        for i in levels
    )

    faq_rows = ''.join(
        f'''<tr>
          <td>{item.get("faq_id")}</td>
          <td>{escape(str(item.get("question") or ""))}</td>
          <td><pre style="white-space:pre-wrap">{escape(str(item.get("answer") or ""))}</pre></td>
          <td>{item.get("sort_order")}</td>
          <td>
            <form method="post" action="/admin/referrals/faqs/delete" style="display:inline">
              <input type="hidden" name="faq_id" value="{item.get('faq_id')}" />
              <button type="submit">删除</button>
            </form>
          </td>
        </tr>'''
        for item in faqs
    ) or '<tr><td colspan="5" class="muted">暂无 FAQ</td></tr>'

    invite_rows = ''.join(
        f'''<tr>
          <td>{item.get("invite_id")}</td>
          <td>{escape(str(item.get("display_name") or ""))}</td>
          <td>{escape(str(item.get("douyin_id") or item.get("agent_douyin_id") or ""))}</td>
          <td><pre style="white-space:pre-wrap;max-width:360px">{escape(str(item.get("invite_message") or ""))}</pre></td>
          <td>{escape(str(item.get("status") or ""))}</td>
          <td>
            <form method="post" action="/admin/referrals/douyin/status" style="display:inline">
              <input type="hidden" name="invite_id" value="{item.get('invite_id')}" />
              <input type="hidden" name="status" value="sent" />
              <button type="submit">标记已联系</button>
            </form>
            <form method="post" action="/admin/referrals/douyin/status" style="display:inline">
              <input type="hidden" name="invite_id" value="{item.get('invite_id')}" />
              <input type="hidden" name="status" value="joined" />
              <button type="submit">已合作</button>
            </form>
          </td>
        </tr>'''
        for item in invites[:50]
    ) or '<tr><td colspan="6" class="muted">暂无跟进任务</td></tr>'

    level_json = escape(json.dumps(levels, ensure_ascii=False))
    body = f'''
      <div class="card">
        <h2>推广全局大盘（近 {days} 天）</h2>
        {f'<div class="notice">{escape(message)}</div>' if message else ''}
        <a class="button" href="/admin/referrals">返回推广分账</a>
        <form class="toolbar" method="get" style="display:inline">
          <input name="days" value="{days}" style="width:72px" />
          <button type="submit">切换天数</button>
        </form>
        <div class="stats">
          <div class="stat"><div class="stat-label">达人总数</div><div class="stat-value">{stats.get("agents_total")}</div></div>
          <div class="stat"><div class="stat-label">活跃达人</div><div class="stat-value">{stats.get("agents_active")}</div></div>
          <div class="stat"><div class="stat-label">区间绑定</div><div class="stat-value">{stats.get("binds_range")}</div></div>
          <div class="stat"><div class="stat-label">区间付费单</div><div class="stat-value">{stats.get("paid_orders_range")}</div></div>
          <div class="stat"><div class="stat-label">区间GMV</div><div class="stat-value">¥{stats.get("order_amount_range")}</div></div>
          <div class="stat"><div class="stat-label">转化率</div><div class="stat-value">{stats.get("conversion_rate")}%</div></div>
          <div class="stat"><div class="stat-label">待分账</div><div class="stat-value">¥{stats.get("commission_pending")}</div></div>
          <div class="stat"><div class="stat-label">已分账</div><div class="stat-value">¥{stats.get("commission_settled")}</div></div>
          <div class="stat"><div class="stat-label">待提现</div><div class="stat-value">¥{stats.get("withdraw_pending")}</div></div>
          <div class="stat"><div class="stat-label">待跟进任务</div><div class="stat-value">{stats.get("douyin_invites_pending")}</div></div>
        </div>
      </div>
      <div class="card">
        <h2>达人排行榜</h2>
        <table><thead><tr><th>ID</th><th>昵称</th><th>邀请码</th><th>等级</th><th>推广人数</th><th>付费单</th><th>区间佣金</th></tr></thead><tbody>{top_agent_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>每日趋势</h2>
        <div style="display:flex;gap:24px;flex-wrap:wrap">
          <div><h3>每日绑定</h3><table><thead><tr><th>日期</th><th>绑定数</th></tr></thead><tbody>{daily_bind_rows}</tbody></table></div>
          <div><h3>每日付费/佣金</h3><table><thead><tr><th>日期</th><th>订单</th><th>佣金</th></tr></thead><tbody>{daily_order_rows}</tbody></table></div>
          <div><h3>等级分布</h3><table><thead><tr><th>等级</th><th>人数</th></tr></thead><tbody>{level_rows}</tbody></table></div>
        </div>
      </div>
      <div class="card">
        <h2>达人等级配置</h2>
        <table><thead><tr><th>等级</th><th>名称</th><th>最低付费单</th><th>佣金加成</th></tr></thead><tbody>{level_config_rows}</tbody></table>
        <form class="toolbar" method="post" action="/admin/referrals/levels/save">
          <input name="level_config_json" value='{level_json}' style="min-width:480px" />
          <button type="submit">保存等级 JSON</button>
        </form>
        <p class="muted">示例：[{{"level_key":"L1","level_name":"新手达人","min_paid_orders":0,"rate_bonus":0}}]</p>
      </div>
      <div class="card">
        <h2>微信自动打款</h2>
        <p class="muted">状态：{"已就绪" if auto_pay.get("ready") else "未配置商户证书"}；开关：{"开启" if auto_pay.get("enabled") else "关闭"}</p>
        <form class="toolbar" method="post" action="/admin/referrals/auto-pay/settings">
          <label><input type="checkbox" name="enabled" value="1" {'checked' if auto_pay.get('enabled') else ''} /> 审核通过后自动微信打款</label>
          <button type="submit">保存</button>
        </form>
      </div>
      <div class="card">
        <h2>达人跟进任务（内部 CRM）</h2>
        <div class="warn-box">{escape(FOLLOW_UP_COMPLIANCE_NOTICE)}</div>
        <p class="muted">说明：批量操作仅在系统内生成待跟进记录与参考话术，不会调用抖音接口或自动发信。请由运营人工联系，且仅联系已授权/已有合作意向的达人。</p>
        <form class="toolbar" method="post" action="/admin/referrals/douyin/queue">
          <input type="hidden" name="batch" value="1" />
          <button type="submit">批量生成跟进任务（已有平台账号）</button>
        </form>
        <form class="toolbar" method="post" action="/admin/referrals/douyin/template">
          <textarea name="template" rows="3" style="min-width:480px">{escape(template)}</textarea>
          <button type="submit">保存跟进话术模板</button>
        </form>
        <p class="muted">模板变量：{{昵称}}、{{抖音号}}、{{邀请码}}</p>
        <table><thead><tr><th>ID</th><th>达人</th><th>平台账号</th><th>跟进话术</th><th>状态</th><th>操作</th></tr></thead><tbody>{invite_rows}</tbody></table>
      </div>
      <div class="card">
        <h2>达人 FAQ 管理</h2>
        <form class="toolbar" method="post" action="/admin/referrals/faqs/save">
          <input name="question" placeholder="问题" style="min-width:200px" />
          <input name="answer" placeholder="回答" style="min-width:320px" />
          <input name="sort_order" value="0" style="width:72px" />
          <button type="submit">新增 FAQ</button>
        </form>
        <table><thead><tr><th>ID</th><th>问题</th><th>回答</th><th>排序</th><th>操作</th></tr></thead><tbody>{faq_rows}</tbody></table>
      </div>
    '''
    return render_page('推广全局大盘', body)


def admin_referral_withdrawals(keyword: str = '', message: str = ''):
    from referral_p1 import list_withdrawals
    from referral_p3 import get_auto_pay_settings
    auto_pay = get_auto_pay_settings()
    rows_data = list_withdrawals(keyword)
    rows = ''.join(
        f'''<tr>
          <td>{item.get("withdrawal_id")}</td>
          <td>{escape(str(item.get("display_name") or ""))}<br><code>{escape(str(item.get("invite_code") or ""))}</code></td>
          <td>¥{item.get("amount")}</td>
          <td>{escape(str(item.get("pay_method") or ""))}</td>
          <td>{escape(str(item.get("pay_account") or ""))}</td>
          <td>{escape(str(item.get("status") or ""))}</td>
          <td>{escape(str(item.get("created_at") or ""))}</td>
          <td>
            {'<form method="post" action="/admin/referrals/withdrawals/review" style="display:inline"><input type="hidden" name="withdrawal_id" value="' + str(item.get("withdrawal_id")) + '" /><input type="hidden" name="action" value="approved" /><button type="submit">通过</button></form>' if item.get('status') == 'pending' else ''}
            {'<form method="post" action="/admin/referrals/withdrawals/review" style="display:inline"><input type="hidden" name="withdrawal_id" value="' + str(item.get("withdrawal_id")) + '" /><input type="hidden" name="action" value="paid" /><button type="submit">已打款</button></form>' if item.get('status') in ('pending', 'approved') else ''}
            {'<form method="post" action="/admin/referrals/withdrawals/auto-pay" style="display:inline"><input type="hidden" name="withdrawal_id" value="' + str(item.get("withdrawal_id")) + '" /><button type="submit">微信自动打款</button></form>' if item.get('status') == 'approved' and item.get('pay_method') in ('wechat', '微信') and not item.get('transfer_bill_no') else ''}
            {'<form method="post" action="/admin/referrals/withdrawals/review" style="display:inline"><input type="hidden" name="withdrawal_id" value="' + str(item.get("withdrawal_id")) + '" /><input type="hidden" name="action" value="rejected" /><button type="submit">驳回</button></form>' if item.get('status') == 'pending' else ''}
          </td>
        </tr>'''
        for item in rows_data
    ) or '<tr><td colspan="8" class="muted">暂无提现申请</td></tr>'
    body = f'''
      <div class="card">
        <h2>达人提现审核</h2>
        {f'<div class="notice">{escape(message)}</div>' if message else ''}
        <a class="button" href="/admin/referrals">返回推广分账</a>
        <a class="button" href="/admin/referrals/overview">全局大盘</a>
        <form method="post" action="/admin/referrals/withdrawals/auto-pay" style="display:inline">
          <input type="hidden" name="batch" value="1" />
          <button type="submit" {'disabled' if not auto_pay.get('ready') else ''}>批量微信自动打款（已通过）</button>
        </form>
        <p class="muted">微信转账：{"已配置" if auto_pay.get("ready") else "未配置"}；自动打款开关：{"开启" if auto_pay.get("enabled") else "关闭"}（在全局大盘设置）</p>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="达人名 / 邀请码 / 收款账号" />
          <button type="submit">搜索</button>
        </form>
        <table><thead><tr><th>ID</th><th>达人</th><th>金额</th><th>方式</th><th>账号</th><th>状态</th><th>申请时间</th><th>操作</th></tr></thead><tbody>{rows}</tbody></table>
      </div>
    '''
    return render_page('达人提现审核', body)
