import hashlib
import os


def get_wechat_msg_token() -> str:
    return (os.getenv('WECHAT_MSG_TOKEN') or '').strip()


def verify_wechat_server_signature(signature: str, timestamp: str, nonce: str, token: str | None = None) -> bool:
    secret = (token or get_wechat_msg_token()).strip()
    if not secret or not signature:
        return False
    parts = sorted([secret, str(timestamp or ''), str(nonce or '')])
    digest = hashlib.sha1(''.join(parts).encode('utf-8')).hexdigest()
    return digest == str(signature or '')
