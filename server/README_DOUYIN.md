# 抖音团购 / 抖店对接说明

## 凭证配置

`ecosystem.config.js`：

```text
DOUYIN_APP_ID=tt4ba63d1bd5c2a9f301
DOUYIN_THIRD_SKU_TRIAL=trial
DOUYIN_THIRD_SKU_STANDARD=standard
DOUYIN_THIRD_SKU_PREMIUM=premium
```

`ecosystem.secrets.js`（勿提交 Git）：

```text
DOUYIN_APP_SECRET=抖音开放平台 AppSecret
DOUYIN_SPI_TOKEN=可选，SPI 回调鉴权令牌
```

## 接口

| 接口 | 说明 |
|------|------|
| `GET /api/douyin/status` | 检查抖音凭证与 client_token |
| `POST /api/douyin/spi/coupon/issue` | 抖音三方发券 SPI（下单后抖音回调） |
| `POST /api/douyin/redeem` | 微信小程序会员中心兑券 |
| `GET /api/douyin/redeem-hint` | 券码兑换指引 |

## 抖音后台需配置

1. **三方发券 SPI 地址**（联系抖音技术或解决方案配置）：
   ```text
   https://api.zntb.lhyun.net/api/douyin/spi/coupon/issue
   ```
2. 抖店商品 `third_sku_id` 建议填写：`trial` / `standard` / `premium`
3. 或使用商品名包含：普通卡 / 黄金卡 / 白金卡

## 用户流程

1. 用户在抖音/抖店下单
2. 抖音调用 SPI，系统返回兑换码（如 `ZDXXXXXXXXXX`）
3. 用户打开微信小程序 → 会员中心 → 抖音券兑换 → 输入券码
4. 自动开通会员并到账星鼎豆

## 部署（Windows 服务器）

一键部署（推荐）：

```powershell
cd C:\zhiyuantianbao
.\scripts\deploy-douyin.ps1
```

或手动执行：

```powershell
cd C:\zhiyuantianbao
git fetch origin
git reset --hard origin/cursor/douyin-integration-0c75
node scripts\check-secrets.js
pm2 delete zhiyuan-backend
pm2 start ecosystem.config.js --only zhiyuan-backend --update-env
pm2 save
```

密钥文件（二选一，勿提交 Git）：

| 文件 | 说明 |
|------|------|
| `ecosystem.secrets.js` | 与 PM2 共用，推荐 |
| `server/local.secrets.env` | 兜底，复制 `local.secrets.env.example` 填写 |

后端启动时会自动读取上述文件，不依赖 PM2 是否注入环境变量。

## 验收

```powershell
Invoke-RestMethod "https://api.zntb.lhyun.net/api/douyin/status"
```

成功响应应包含：

```text
enabled               : True
app_secret_configured : True
spi_token_configured  : True
client_token_ok       : True
secrets_bootstrap     : @{ secrets_file_exists=True; ... }
```

若响应**没有** `secrets_bootstrap` 字段，说明仍在跑旧代码，请重新执行部署脚本。
