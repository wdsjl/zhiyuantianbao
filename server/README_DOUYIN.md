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
| `GET /api/douyin/landing/links` | 生成抖音落地页 + 唤起微信小程序链接 |
| `GET /douyin/landing` | 抖音 H5 落地页（点击唤起微信小程序） |

## 抖音落地页 / 唤起微信小程序

用于抖音广告、主页、私信、短视频挂载等场景：用户点击 H5 落地页后唤起微信小程序。

### 1. 生成跳转链接（API）

```powershell
Invoke-RestMethod "https://api.zntb.lhyun.net/api/douyin/landing/links?page=home&from=douyin"
```

常用 `page` 预设：

| page | 说明 |
|------|------|
| `home` | 小程序首页 |
| `membership` | 会员中心 |
| `douyin_redeem` | 会员中心并定位到抖音券兑换 |
| `promotion` | 达人推广中心 |

带达人推广码：

```powershell
Invoke-RestMethod "https://api.zntb.lhyun.net/api/douyin/landing/links?page=home&invite=ABC123&from=douyin"
```

返回字段：

| 字段 | 用途 |
|------|------|
| `landing_page_url` | **抖音投放落地页链接**（推荐填这个） |
| `url_scheme` | 微信 URL Scheme，可直接唤起小程序 |
| `url_link` | 微信 URL Link，备用外链 |
| `share_path` | 小程序内路径 |

### 2. 落地页示例

首页投放：

```text
https://api.zntb.lhyun.net/douyin/landing?page=home&from=douyin
```

抖音券兑换：

```text
https://api.zntb.lhyun.net/douyin/landing?page=douyin_redeem&from=douyin
```

达人推广：

```text
https://api.zntb.lhyun.net/douyin/landing?page=home&invite=达人推广码&from=douyin
```

### 3. 前置条件

需已配置 `WECHAT_APPID` 与 `WECHAT_SECRET`。微信 URL Scheme / URL Link 需企业主体小程序权限。

可选环境变量：

```text
DOUYIN_LANDING_BASE_URL=https://api.zntb.lhyun.net
WECHAT_LINK_ENV_VERSION=release
```

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
