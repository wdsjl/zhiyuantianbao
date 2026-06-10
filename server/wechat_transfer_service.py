"""微信商家转账（达人佣金自动打款）。"""

from __future__ import annotations

import secrets
import time
from typing import Any

from wechat_pay_service import _amount_to_fen, _request_wechat_pay, get_pay_config, is_wechat_v3_pay_ready


def is_wechat_transfer_ready() -> bool:
    return is_wechat_v3_pay_ready()


def _validate_openid(openid: str) -> str:
    openid = (openid or '').strip()
    if not openid or openid.startswith(('dev_', 'local_', 'test_', 'agent_import_')):
        raise ValueError('达人需使用真实微信登录后才能自动打款')
    return openid


def make_transfer_bill_no(withdrawal_id: int) -> str:
    return f'RW{time.strftime("%Y%m%d%H%M%S")}{withdrawal_id}{secrets.token_hex(2)[:4]}'


def transfer_to_agent_openid(
    openid: str,
    amount_yuan: float,
    withdrawal_id: int,
    remark: str = '达人佣金提现',
) -> dict[str, Any]:
    if not is_wechat_transfer_ready():
        raise ValueError('微信商家转账未配置。请在服务端配置 WECHAT_PAY_API_V3_KEY、证书与商户号。')

    config = get_pay_config()
    openid = _validate_openid(openid)
    amount_fen = _amount_to_fen(amount_yuan)
    if amount_fen < 30:
        raise ValueError('微信转账最低 0.30 元')
    if amount_fen > 20000000:
        raise ValueError('单笔转账金额超出限制')

    out_bill_no = make_transfer_bill_no(withdrawal_id)
    payload = {
        'appid': config['appid'],
        'out_bill_no': out_bill_no,
        'transfer_scene_id': '1005',
        'openid': openid,
        'transfer_amount': amount_fen,
        'transfer_remark': (remark or '达人佣金提现')[:32],
        'transfer_scene_report_infos': [
            {'info_type': '岗位类型', 'info_content': '推广达人'},
            {'info_type': '报酬说明', 'info_content': '推广佣金提现'},
        ],
    }
    try:
        result = _request_wechat_pay('POST', '/v3/fund-app/mch-transfer/transfer-bills', payload)
        return {
            'status': result.get('state') or result.get('status') or 'submitted',
            'out_bill_no': out_bill_no,
            'transfer_bill_no': result.get('transfer_bill_no') or result.get('batch_id') or '',
            'message': '微信转账已提交',
            'raw': result,
        }
    except ValueError as exc:
        # 兼容旧版批量转账接口
        if '404' not in str(exc) and 'NOT_FOUND' not in str(exc):
            raise
        batch_no = f'B{out_bill_no}'
        detail_no = f'D{out_bill_no}'
        legacy_payload = {
            'appid': config['appid'],
            'out_batch_no': batch_no,
            'batch_name': '达人佣金提现',
            'batch_remark': (remark or '达人佣金提现')[:32],
            'total_amount': amount_fen,
            'total_num': 1,
            'transfer_detail_list': [
                {
                    'out_detail_no': detail_no,
                    'transfer_amount': amount_fen,
                    'transfer_remark': (remark or '达人佣金提现')[:32],
                    'openid': openid,
                }
            ],
        }
        result = _request_wechat_pay('POST', '/v3/transfer/batches', legacy_payload)
        return {
            'status': result.get('batch_status') or 'submitted',
            'out_bill_no': batch_no,
            'transfer_bill_no': result.get('batch_id') or '',
            'message': '微信批量转账已提交',
            'raw': result,
        }
