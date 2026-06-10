const path = require('path');

let secrets = {};
const secretsPath = path.join(__dirname, 'ecosystem.secrets.js');
try {
  secrets = require(secretsPath);
  const loadedKeys = Object.keys(secrets || {});
  console.log(`[ecosystem] loaded secrets: ${loadedKeys.join(', ') || '(empty)'}`);
  if (!secrets.DOUYIN_APP_SECRET) {
    console.error('[ecosystem] WARNING: DOUYIN_APP_SECRET missing in ecosystem.secrets.js');
  }
} catch (error) {
  console.error(`[ecosystem] failed to load ${secretsPath}: ${error.message}`);
  secrets = {};
}

module.exports = {
  apps: [{
    name: 'zhiyuan-backend',
    script: 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe',
    args: '-m uvicorn main:app --host 127.0.0.1 --port 8001',
    cwd: 'C:/zhiyuantianbao/server',
    windowsHide: true,
    env: {
      ADMIN_USERNAME: 'admin',
      ADMIN_PASSWORD: 'admin123',
      ADMIN_SESSION_SECRET: 'please-change-this-secret',
      WECHAT_APPID: 'wx58ed9703d22d85c2',
      WECHAT_MCH_ID: '1621904940',
      WECHAT_VIRTUAL_PAY_OFFER_ID: '1450554502',
      WECHAT_VIRTUAL_PAY_ENV: '0',
      WECHAT_VIRTUAL_PRODUCT_TRIAL: 'xdptk',
      WECHAT_VIRTUAL_PRODUCT_STANDARD: 'xdhjk',
      WECHAT_VIRTUAL_PRODUCT_PREMIUM: 'xdbjk',
      WECHAT_PAY_NOTIFY_URL: 'https://api.zntb.lhyun.net/api/payments/wechat/notify',
      WECHAT_PAY_PRIVATE_KEY_PATH: 'C:/zhiyuantianbao/server/certs/apiclient_key.pem',
      WECHAT_QRCODE_ENV_VERSION: 'trial',
      DOUYIN_APP_ID: 'tt4ba63d1bd5c2a9f301',
      DOUYIN_THIRD_SKU_TRIAL: 'trial',
      DOUYIN_THIRD_SKU_STANDARD: 'standard',
      DOUYIN_THIRD_SKU_PREMIUM: 'premium',
      ...secrets
    }
  }]
};
