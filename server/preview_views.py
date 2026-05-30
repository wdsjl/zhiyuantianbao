from datetime import datetime
from html import escape

from fastapi.responses import HTMLResponse

from membership_service import get_user_entitlements, list_plans, search_users
from payment_service import get_support_contact, list_user_open_requests, list_user_orders


PLAN_FEATURES = {
    'free': ['完整测评流程', '基础院校专业查询', '近2年分数线', '手动志愿模拟'],
    'trial': ['完整历年分数线', '深度测评报告', '智能推荐3次', 'AI解读3次', 'PDF导出1次'],
    'standard': ['智能推荐不限次', '风险检测不限次', 'AI解读', '草稿保存', 'PDF导出', '专业避坑指南'],
    'premium': ['标准年卡全部功能', '同分段往届参考', '院校深度对比', '地域就业规划', '专属答疑通道', '征集志愿提醒'],
}

REQUEST_STATUS_TEXT = {
    'pending': '待处理',
    'processed': '已开通',
    'cancelled': '已取消',
}

ORDER_STATUS_TEXT = {
    'pending': '待支付',
    'paid': '已支付',
    'refunded': '已退款',
    'cancelled': '已取消',
}


def format_price(value) -> str:
    amount = float(value or 0)
    if amount == 0:
        return '免费'
    return f'¥{int(amount)}' if amount.is_integer() else f'¥{amount}'


def format_duration(days) -> str:
    duration_days = int(days or 0)
    return f'{duration_days}天' if duration_days > 0 else '长期'


def status_text(value: str | None, mapping: dict[str, str]) -> str:
    return mapping.get(value or '', value or '')


def build_membership_notice(entitlements: dict, plans: list[dict]) -> dict | None:
    membership = entitlements.get('membership')
    latest = entitlements.get('latest_membership')
    if membership and membership.get('expires_at'):
        try:
            expires_at = datetime.strptime(str(membership['expires_at']), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
        diff_days = (expires_at.date() - datetime.now().date()).days
        if 0 <= diff_days <= 7:
            return {
                'type': 'warning',
                'plan_code': membership.get('plan_code'),
                'plan_name': membership.get('plan_name') or '会员',
                'text': f"您的{membership.get('plan_name') or '会员'}将在{diff_days}天后到期，建议及时续费。",
                'price_text': next((plan['price_text'] for plan in plans if plan['plan_code'] == membership.get('plan_code')), ''),
            }
    if not membership and latest and latest.get('status') == 'expired':
        return {
            'type': 'expired',
            'plan_code': latest.get('plan_code'),
            'plan_name': latest.get('plan_name') or '会员',
            'text': f"您的{latest.get('plan_name') or '会员'}已过期，续费后可继续使用会员功能。",
            'price_text': next((plan['price_text'] for plan in plans if plan['plan_code'] == latest.get('plan_code')), ''),
        }
    return None


def mobile_card(content: str, extra_class: str = '') -> str:
    return f'<section class="mini-card {extra_class}">{content}</section>'


def plan_card(plan: dict, current_plan_code: str) -> str:
    is_current = plan['plan_code'] == current_plan_code
    feature_html = ''.join(f'<span class="feature-item">{escape(feature)}</span>' for feature in plan['features'])
    button_html = (
        '<button class="secondary-btn" disabled>当前套餐</button>'
        if is_current
        else '<button class="primary-btn" disabled title="浏览器预览页不提交真实申请">提交开通申请</button>'
    )
    return mobile_card(
        f'''
        <div class="plan-head">
          <div>
            <div class="plan-name">{escape(str(plan.get('plan_name') or ''))}</div>
            <div class="sub-text">{escape(str(plan.get('description') or ''))}</div>
          </div>
          <div class="plan-price">{escape(plan['price_text'])}</div>
        </div>
        <div class="sub-text">有效期：{escape(plan['duration_text'])}</div>
        <div class="feature-list">{feature_html}</div>
        {button_html}
        ''',
        'current-plan' if is_current else ''
    )


def support_card(support: dict) -> str:
    if not any([support.get('support_wechat'), support.get('support_phone'), support.get('support_note')]):
        return ''
    lines = ''
    if support.get('support_wechat'):
        lines += f'<div class="contact-line">客服微信：{escape(str(support["support_wechat"]))}</div>'
    if support.get('support_phone'):
        lines += f'<div class="contact-line">客服电话：{escape(str(support["support_phone"]))}</div>'
    if support.get('support_note'):
        lines += f'<div class="warn-box">{escape(str(support["support_note"]))}</div>'
    return mobile_card(f'<div class="section-title">开通联系指引</div>{lines}')


def request_rows(open_requests: list[dict]) -> str:
    if not open_requests:
        return ''
    rows = ''
    for item in open_requests:
        rows += f'''
        <div class="status-row">
          <div>
            <div class="status-title">{escape(str(item.get('plan_name') or item.get('plan_code') or ''))} · {escape(format_price(item.get('price')))}</div>
            <div class="sub-text">提交时间：{escape(str(item.get('created_at') or ''))}</div>
            {f'<div class="sub-text">备注：{escape(str(item.get("message") or ""))}</div>' if item.get('message') else ''}
          </div>
          <div class="status-tag status-{escape(str(item.get('request_status') or ''))}">{escape(status_text(item.get('request_status'), REQUEST_STATUS_TEXT))}</div>
        </div>
        '''
    return mobile_card(f'<div class="section-title">我的开通申请</div>{rows}')


def order_rows(orders: list[dict]) -> str:
    if not orders:
        return ''
    rows = ''
    for item in orders:
        rows += f'''
        <div class="status-row">
          <div>
            <div class="status-title">{escape(str(item.get('plan_name') or item.get('plan_code') or ''))} · {escape(format_price(item.get('amount')))}</div>
            <div class="sub-text">订单号：{escape(str(item.get('order_no') or ''))}</div>
            <div class="sub-text">支付时间：{escape(str(item.get('paid_at') or ''))}</div>
          </div>
          <div class="status-tag status-{escape(str(item.get('pay_status') or ''))}">{escape(status_text(item.get('pay_status'), ORDER_STATUS_TEXT))}</div>
        </div>
        '''
    return mobile_card(f'<div class="section-title">我的订单</div>{rows}')


def user_selector(user_id: int | None) -> str:
    users = search_users('')[:100]
    options = '<option value="">免费版游客视角</option>'
    for user in users:
        label = f"{user.get('user_id')} - {user.get('phone') or ''} - {user.get('student_name') or user.get('name') or ''}"
        selected = ' selected' if user_id and int(user['user_id']) == user_id else ''
        options += f'<option value="{user.get("user_id")}"{selected}>{escape(label)}</option>'
    return f'''
      <form class="preview-toolbar" method="get" action="/preview/membership">
        <label>
          选择预览用户
          <select name="user_id">{options}</select>
        </label>
        <label>
          或输入用户 ID
          <input name="custom_user_id" value="{escape(str(user_id or ''))}" placeholder="例如 1" />
        </label>
        <button type="submit">刷新预览</button>
        <a class="button" href="/admin/payments">去后台处理申请/订单</a>
      </form>
    '''


def membership_preview_page(user_id: int | None = None, custom_user_id: str = '') -> HTMLResponse:
    if custom_user_id.strip().isdigit():
        user_id = int(custom_user_id.strip())

    raw_plans = [plan for plan in list_plans() if plan.get('is_active')]
    plans = [
        {
            **plan,
            'price_text': format_price(plan.get('price')),
            'duration_text': format_duration(plan.get('duration_days')),
            'features': PLAN_FEATURES.get(plan.get('plan_code'), []),
        }
        for plan in raw_plans
    ]
    entitlements = get_user_entitlements(user_id)
    plan = entitlements.get('plan') or {'plan_name': '免费版', 'plan_code': 'free'}
    membership = entitlements.get('membership')
    current_plan_code = plan.get('plan_code') or 'free'
    support = get_support_contact()
    open_requests = list_user_open_requests(user_id) if user_id else []
    orders = list_user_orders(user_id) if user_id else []
    notice = build_membership_notice(entitlements, plans)

    expires_text = (
        f"到期时间：{escape(str(membership.get('expires_at')))}"
        if membership and membership.get('expires_at')
        else '免费功能长期可用，会员功能请联系客服开通。'
    )
    notice_html = ''
    if notice:
        notice_html = mobile_card(
            f'''
            <div class="section-title">会员提醒</div>
            <div class="sub-text">{escape(notice['text'])}</div>
            <button class="primary-btn renew-btn" disabled title="浏览器预览页不提交真实申请">立即续费</button>
            ''',
            f'expire-card {notice["type"]}'
        )
    plan_html = ''.join(plan_card(item, current_plan_code) for item in plans)
    content = f'''
      <!doctype html>
      <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>会员中心浏览器预览</title>
        <style>
          * {{ box-sizing: border-box; }}
          body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #eef3fb; color: #17233d; }}
          header {{ padding: 28px 40px; background: linear-gradient(135deg, #1677ff, #36cfc9); color: white; }}
          header h1 {{ margin: 0; font-size: 28px; }}
          header p {{ margin: 8px 0 0; opacity: .9; }}
          main {{ max-width: 1160px; margin: 0 auto; padding: 28px 24px 56px; }}
          .preview-toolbar {{ display: flex; gap: 14px; align-items: end; flex-wrap: wrap; padding: 20px; margin-bottom: 24px; background: white; border-radius: 18px; box-shadow: 0 12px 32px rgba(22, 119, 255, .08); }}
          label {{ display: grid; gap: 6px; color: #475467; font-size: 14px; font-weight: 600; }}
          input, select {{ height: 40px; min-width: 220px; border: 1px solid #d0d5dd; border-radius: 10px; padding: 0 12px; }}
          button, .button {{ height: 40px; border: 0; border-radius: 999px; padding: 0 18px; color: white; background: #1677ff; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; }}
          button:disabled {{ cursor: not-allowed; opacity: .9; }}
          .layout {{ display: grid; grid-template-columns: minmax(320px, 420px) 1fr; gap: 28px; align-items: start; }}
          .phone-shell {{ width: 100%; max-width: 420px; margin: 0 auto; padding: 18px 12px; background: #111827; border-radius: 38px; box-shadow: 0 24px 80px rgba(16, 24, 40, .24); position: sticky; top: 20px; }}
          .phone-screen {{ height: 760px; overflow: auto; background: #f5f7fb; border-radius: 28px; padding: 18px; }}
          .mini-card {{ background: white; border-radius: 18px; padding: 20px; box-shadow: 0 12px 32px rgba(22, 119, 255, .08); margin-bottom: 16px; }}
          .member-hero {{ background: linear-gradient(135deg, #1677ff, #36cfc9); color: white; }}
          .member-hero .sub-text {{ color: rgba(255, 255, 255, .86); }}
          .section-title {{ font-size: 18px; font-weight: 800; margin-bottom: 10px; }}
          .sub-text {{ color: #667085; line-height: 1.7; font-size: 14px; }}
          .current-plan {{ border: 2px solid #1677ff; box-shadow: 0 16px 44px rgba(22, 119, 255, .16); }}
          .plan-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 10px; }}
          .plan-name {{ font-size: 18px; font-weight: 800; color: #17233d; margin-bottom: 4px; }}
          .plan-price {{ font-size: 24px; font-weight: 900; color: #f79009; white-space: nowrap; }}
          .feature-list {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0; }}
          .feature-item {{ padding: 7px 10px; border-radius: 999px; background: #eef5ff; color: #1677ff; font-size: 13px; }}
          .primary-btn, .secondary-btn {{ width: 100%; height: 42px; }}
          .secondary-btn {{ background: #eef5ff; color: #1677ff; }}
          .contact-line {{ font-size: 16px; color: #17233d; font-weight: 700; margin: 8px 0; }}
          .warn-box {{ margin-top: 10px; padding: 12px; border-radius: 12px; background: #fff7e6; color: #9a5b00; line-height: 1.7; font-size: 14px; }}
          .expire-card.warning {{ border-left: 5px solid #f79009; }}
          .expire-card.expired {{ border-left: 5px solid #f04438; }}
          .renew-btn {{ margin-top: 14px; }}
          .status-row {{ display: flex; justify-content: space-between; gap: 16px; padding: 16px 0; border-bottom: 1px solid #edf0f5; }}
          .status-row:last-child {{ border-bottom: 0; }}
          .status-title {{ font-size: 15px; font-weight: 700; color: #17233d; margin-bottom: 4px; }}
          .status-tag {{ flex: 0 0 auto; height: 28px; line-height: 28px; padding: 0 10px; border-radius: 999px; font-size: 13px; background: #eef5ff; color: #1677ff; }}
          .status-pending {{ background: #fff7e6; color: #f79009; }}
          .status-processed, .status-paid {{ background: #ecfdf3; color: #12b76a; }}
          .status-cancelled, .status-refunded {{ background: #f2f4f7; color: #667085; }}
          .side-card {{ background: white; border-radius: 18px; padding: 24px; box-shadow: 0 12px 32px rgba(22, 119, 255, .08); margin-bottom: 18px; }}
          .side-card h2 {{ margin: 0 0 12px; }}
          .side-card li {{ margin: 8px 0; color: #475467; }}
          code {{ background: #eef5ff; color: #1677ff; padding: 2px 6px; border-radius: 6px; }}
          @media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} .phone-shell {{ position: static; }} }}
        </style>
      </head>
      <body>
        <header>
          <h1>会员中心浏览器预览</h1>
          <p>用于在 Cursor 内置浏览器中查看小程序会员中心的页面状态；按钮为只读模拟，不会提交真实申请。</p>
        </header>
        <main>
          {user_selector(user_id)}
          <div class="layout">
            <div class="phone-shell">
              <div class="phone-screen">
                {mobile_card(f'<div class="section-title">会员中心</div><div class="sub-text">当前套餐：{escape(str(plan.get("plan_name") or "免费版"))}</div><div class="sub-text">{expires_text}</div>', 'member-hero')}
                {notice_html}
                {plan_html}
                {support_card(support)}
                {request_rows(open_requests)}
                {order_rows(orders)}
                {mobile_card('<div class="section-title">合规说明</div><div class="warn-box">个人主体阶段不在小程序内直接收款。点击套餐可提交开通申请，客服确认收款后人工开通；企业主体升级后可接入微信支付自动开通。</div><div class="warn-box">所有推荐、风险检测和 AI 解读仅供参考，不构成录取承诺，最终以官方招生政策和正式填报系统为准。</div>')}
              </div>
            </div>
            <aside>
              <div class="side-card">
                <h2>如何使用这个预览</h2>
                <ul>
                  <li>默认展示免费版游客视角。</li>
                  <li>选择或输入用户 ID 后，可查看该用户的会员、申请和订单状态。</li>
                  <li>真实小程序仍需使用微信开发者工具预览；此页用于浏览器快速验收 UI 和数据。</li>
                </ul>
              </div>
              <div class="side-card">
                <h2>相关入口</h2>
                <p><a class="button" href="/admin">后台首页</a></p>
                <p><a class="button" href="/admin/payments">收款订单 / 申请处理</a></p>
                <p><a class="button" href="/docs">FastAPI 文档</a></p>
              </div>
              <div class="side-card">
                <h2>接口来源</h2>
                <ul>
                  <li><code>GET /api/membership/plans</code></li>
                  <li><code>GET /api/membership/entitlements</code></li>
                  <li><code>GET /api/membership/my-status</code></li>
                  <li><code>GET /api/membership/support-contact</code></li>
                </ul>
              </div>
            </aside>
          </div>
        </main>
      </body>
      </html>
    '''
    return HTMLResponse(content)
