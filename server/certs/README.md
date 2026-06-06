# 微信支付证书目录

请将微信商户平台下载的 API 证书私钥放到此目录：

```text
apiclient_key.pem
```

并在服务器环境变量中配置：

```text
WECHAT_APPID=你的小程序AppID
WECHAT_MCH_ID=1621904940
WECHAT_PAY_API_V3_KEY=商户平台APIv3密钥
WECHAT_PAY_SERIAL_NO=商户API证书序列号
WECHAT_PAY_PRIVATE_KEY_PATH=C:/zhiyuantianbao/server/certs/apiclient_key.pem
WECHAT_PAY_NOTIFY_URL=https://api.zntb.lhyun.net/api/payments/wechat/notify
```

注意：不要把真实证书私钥提交到 Git 仓库。
