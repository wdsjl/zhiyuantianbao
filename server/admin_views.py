from html import escape
from urllib.parse import urlencode

from fastapi.responses import HTMLResponse

from db import get_connection, rows_to_dicts
from data_fetch_service import list_sources, list_tasks, list_records
from llm_settings_service import get_llm_settings, mask_api_key
from membership_service import list_plans, list_permissions, get_plan_permission_map, search_users, list_permission_usage, list_expiring_members
from payment_service import list_orders, get_order_stats, list_open_requests, get_support_contact
from dashboard_service import get_dashboard_stats


def page(title: str, body: str) -> HTMLResponse:
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
        nav {{ background: white; padding: 14px 40px; box-shadow: 0 8px 24px rgba(22, 119, 255, .08); position: sticky; top: 0; z-index: 2; }}
        nav a {{ display: inline-block; margin-right: 18px; color: #1677ff; text-decoration: none; font-weight: 600; }}
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
        .danger {{ color: #f04438; }}
        .success {{ color: #12b76a; }}
        .tag {{ display: inline-block; padding: 4px 8px; border-radius: 999px; background: #eef5ff; color: #1677ff; font-size: 12px; }}
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
        <a href="/admin/import/logs">导入日志</a>
        <a href="/admin/schools">院校数据</a>
        <a href="/admin/students">学生档案</a>
        <a href="/admin/majors">专业数据</a>
        <a href="/admin/admissions">录取数据</a>
        <a href="/admin/data-sources">官方数据源</a>
        <a href="/admin/membership/plans">会员套餐</a>
        <a href="/admin/membership/users">用户会员</a>
        <a href="/admin/membership/usage">次数记录</a>
        <a href="/admin/payments">收款订单</a>
        <a href="/preview/membership" target="_blank">会员页预览</a>
        <a href="/admin/llm-settings">大模型配置</a>
        <a href="/docs" target="_blank">接口文档</a>
      </nav>
      <main>{body}</main>
    </body>
    </html>
    """
    return HTMLResponse(html)


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
      </div>
    '''
    return page('运营看板', body)


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
    return page('数据导入', body)


def admin_logs():
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute('SELECT * FROM import_logs ORDER BY created_at DESC LIMIT 100').fetchall())
    body = '<div class="card"><h2>导入日志</h2>' + table(
        ['ID', '类型', '文件名', '总数', '成功', '失败', '错误', '时间'],
        rows,
        ['log_id', 'import_type', 'file_name', 'total_count', 'success_count', 'fail_count', 'error_message', 'created_at']
    ) + '</div>'
    return page('导入日志', body)


def admin_schools(keyword: str = ''):
    sql = 'SELECT * FROM schools WHERE 1=1'
    params = []
    if keyword:
        sql += ' AND (school_name LIKE ? OR school_code LIKE ? OR city LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like])
    sql += ' ORDER BY school_id DESC LIMIT 100'
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(sql, params).fetchall())
    query = escape(keyword)
    body = f'''
      <div class="card">
        <h2>院校数据</h2>
        <form class="toolbar" method="get">
          <input name="keyword" value="{query}" placeholder="院校名称 / 代码 / 城市" />
          <button type="submit">搜索</button>
        </form>
        {table(['ID', '代码', '名称', '省份', '城市', '类型', '层次', '985', '211', '双一流', '公办'], rows, ['school_id', 'school_code', 'school_name', 'province', 'city', 'school_type', 'education_level', 'is_985', 'is_211', 'is_double_first_class', 'is_public'])}
      </div>
    '''
    return page('院校数据', body)


def admin_majors(keyword: str = ''):
    sql = 'SELECT * FROM majors WHERE 1=1'
    params = []
    if keyword:
        sql += ' AND (major_name LIKE ? OR major_code LIKE ? OR major_type LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like])
    sql += ' ORDER BY major_id DESC LIMIT 100'
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(sql, params).fetchall())
    body = f'''
      <div class="card">
        <h2>专业数据</h2>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="专业名称 / 代码 / 类型" />
          <button type="submit">搜索</button>
        </form>
        {table(['ID', '代码', '名称', '门类', '类型', '层次', '学制'], rows, ['major_id', 'major_code', 'major_name', 'major_category', 'major_type', 'degree_type', 'duration'])}
      </div>
    '''
    return page('专业数据', body)


def admin_admissions(province: str = '', batch: str = '', year: str = ''):
    sql = '''
    SELECT ar.admission_id, ar.year, ar.province, ar.batch, s.school_name, s.school_code,
           m.major_name, m.major_code, ar.min_score, ar.min_rank, ar.avg_score, ar.avg_rank, ar.enrollment_count
    FROM admission_records ar
    JOIN schools s ON s.school_id = ar.school_id
    JOIN majors m ON m.major_id = ar.major_id
    WHERE 1=1
    '''
    params = []
    if province:
        sql += ' AND ar.province = ?'
        params.append(province)
    if batch:
        sql += ' AND ar.batch = ?'
        params.append(batch)
    if year:
        sql += ' AND ar.year = ?'
        params.append(int(year))
    sql += ' ORDER BY ar.year DESC, ar.min_rank ASC LIMIT 200'
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(sql, params).fetchall())
    body = f'''
      <div class="card">
        <h2>录取数据</h2>
        <form class="toolbar" method="get">
          <input name="province" value="{escape(province)}" placeholder="省份，例如 浙江" />
          <input name="batch" value="{escape(batch)}" placeholder="批次，例如 普通类一段" />
          <input name="year" value="{escape(year)}" placeholder="年份，例如 2025" />
          <button type="submit">筛选</button>
        </form>
        {table(['ID', '年份', '省份', '批次', '院校', '院校代码', '专业', '专业代码', '最低分', '最低位次', '平均分', '平均位次', '招生人数'], rows, ['admission_id', 'year', 'province', 'batch', 'school_name', 'school_code', 'major_name', 'major_code', 'min_score', 'min_rank', 'avg_score', 'avg_rank', 'enrollment_count'])}
      </div>
    '''
    return page('录取数据', body)



def admin_students(keyword: str = ''):
    sql = """
    SELECT s.student_id, u.user_id, u.openid, u.phone, u.role, s.name, s.province, s.city,
           s.school_name, s.grade, s.class_name, s.exam_year, s.subject_combination,
           s.score, s.rank, s.target_batch, s.updated_at
    FROM students s
    JOIN users u ON u.user_id = s.user_id
    WHERE 1=1
    """
    params = []
    if keyword:
        sql += ' AND (s.name LIKE ? OR u.phone LIKE ? OR s.school_name LIKE ? OR s.class_name LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like, like])
    sql += ' ORDER BY s.updated_at DESC LIMIT 200'
    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(sql, params).fetchall())
    body = f"""
      <div class="card">
        <h2>学生档案</h2>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="姓名 / 手机号 / 学校 / 班级" />
          <button type="submit">搜索</button>
        </form>
        {table(['学生ID', '用户ID', '手机号', '角色', '姓名', '省份', '城市', '学校', '年级', '班级', '年份', '选科', '分数', '位次', '批次', '更新时间'], rows, ['student_id', 'user_id', 'phone', 'role', 'name', 'province', 'city', 'school_name', 'grade', 'class_name', 'exam_year', 'subject_combination', 'score', 'rank', 'target_batch', 'updated_at'])}
      </div>
    """
    return page('学生档案', body)



def admin_data_sources(keyword: str = '', message: str = ''):
    sources = list_sources(keyword)
    tasks = list_tasks()
    records = list_records()
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
              <form method="post" action="/admin/data-sources/{source.get('source_id')}/fetch">
                <button type="submit">采集</button>
              </form>
            </td>
          </tr>
        '''
    if not rows_html:
        rows_html = '<tr><td colspan="8" class="muted">暂无数据源</td></tr>'

    task_table = table(
        ['任务ID', '数据源ID', '高校', '状态', '页面标题', '匹配链接', '错误', '时间'],
        tasks,
        ['task_id', 'source_id', 'school_name', 'task_status', 'page_title', 'matched_count', 'error_message', 'created_at']
    )
    record_table = table(
        ['记录ID', '任务ID', '类型', '标题', '扩展名', '关键词', '审核状态', '链接'],
        records,
        ['record_id', 'task_id', 'record_type', 'title', 'file_ext', 'matched_keyword', 'review_status', 'url']
    )
    body = f'''
      <div class="card">
        <h2>高校官方数据源</h2>
        {message_html}
        <p class="muted">第一版支持配置高校招生官网 URL，并自动发现页面中的招生计划、招生章程、历年录取分数、PDF、Excel、CSV、Word 等链接。采集结果先归档，后续人工审核后再入库。</p>
        <form class="toolbar" method="get">
          <input name="keyword" value="{escape(keyword)}" placeholder="高校 / 数据源 / URL" />
          <button type="submit">搜索</button>
        </form>
        <form class="toolbar" method="post" action="/admin/data-sources">
          <input name="school_name" placeholder="高校名称" required />
          <input name="school_code" placeholder="高校代码" />
          <input name="source_name" placeholder="数据源名称，例如本科招生网" />
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
      <div class="card"><h2>采集发现链接</h2>{record_table}</div>
    '''
    return page('官方数据源', body)



def admin_llm_settings(message: str = ''):
    settings = get_llm_settings() or {}
    message_html = f'<p class="success">{escape(message)}</p>' if message else ''
    enabled_checked = 'checked' if settings.get('is_enabled') else ''
    body = f'''
      <div class="card">
        <h2>大模型配置</h2>
        {message_html}
        <p class="muted">管理后台可直接填写大模型 API Key。当前仅保存配置，后续可用于智能问答、招生章程解读、专业推荐解释等能力。API Key 会在页面中脱敏展示。</p>
        <form method="post" action="/admin/llm-settings">
          <div class="toolbar">
            <select name="provider">
              <option value="openai-compatible">OpenAI Compatible</option>
              <option value="deepseek">DeepSeek</option>
              <option value="qwen">通义千问</option>
              <option value="zhipu">智谱</option>
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
    return page('大模型配置', body)



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
    return page('会员套餐配置', body)


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
    return page('用户会员管理', body)



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
                <button type="submit">清零</button>
              </form>
              <form method="post" action="/admin/membership/usage/delete" style="display:inline">
                <input type="hidden" name="usage_id" value="{item.get('usage_id', '')}" />
                <button type="submit" style="background:#f04438">删除</button>
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
        </form>
        <table><thead><tr><th>ID</th><th>用户ID</th><th>手机号</th><th>姓名</th><th>学校</th><th>套餐</th><th>功能</th><th>周期</th><th>已用</th><th>更新时间</th><th>操作</th></tr></thead><tbody>{rows}</tbody></table>
      </div>
    '''
    return page('会员次数记录', body)



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
          </tr>
        '''
    if not rows:
        rows = '<tr><td colspan="12" class="muted">暂无订单</td></tr>'
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
        <table><thead><tr><th>ID</th><th>订单号</th><th>手机号</th><th>姓名</th><th>套餐</th><th>金额</th><th>类型</th><th>方式</th><th>状态</th><th>联系方式</th><th>支付时间</th><th>备注</th></tr></thead><tbody>{rows}</tbody></table>
      </div>
    '''
    return page('收款订单', body)
