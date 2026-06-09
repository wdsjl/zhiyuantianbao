# 智愿填报后端服务

## 启动

```bash
cd server
python start.py
```

默认地址：

```text
http://127.0.0.1:8001
```

接口文档：

```text
http://127.0.0.1:8001/docs
```

管理后台：

```text
http://127.0.0.1:8001/admin
```

默认登录账号（首次启动自动写入数据库，可通过环境变量覆盖）：

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_SESSION_SECRET=请改成随机字符串
```

未登录访问 `/admin/*` 会自动跳转到登录页。

## Windows PM2 部署

推荐使用项目根目录的 `ecosystem.config.js`：

```powershell
cd C:\zhiyuantianbao
pm2 start ecosystem.config.js
pm2 save
```

或使用 `server/run.bat`：

```powershell
pm2 start C:\zhiyuantianbao\server\run.bat --name zhiyuan-backend --interpreter cmd --interpreter-args "/c"
```

不要使用 `start.py`（含热重载，Windows 下易崩溃）。

## 微信登录配置

后端已支持：

```text
POST /api/auth/login
```

本地开发时，即使没有微信 `appid` 和 `secret`，接口也会自动生成 `dev_xxx` 类型 openid，方便调试。

正式上线前，需要设置环境变量：

```text
WECHAT_APPID=你的小程序appid
WECHAT_SECRET=你的小程序secret
```

设置后，后端会使用微信官方 `jscode2session` 换取真实 `openid`。

**微信支付必须配置 `WECHAT_SECRET`**，否则用户 openid 会是 `local_` / `dev_` 临时值，支付时会提示「请先使用微信登录后再支付」。

在服务器 `ecosystem.secrets.js` 中填写：

```javascript
module.exports = {
  WECHAT_SECRET: '你的小程序AppSecret',
  WECHAT_PAY_API_V3_KEY: '...',
  WECHAT_PAY_SERIAL_NO: '...'
};
```

然后执行 `pm2 restart zhiyuan-backend --update-env`。

验证是否生效：

```text
GET https://api.zntb.lhyun.net/api/auth/wechat/status
```

应返回 `{"enabled": true, "appid_configured": true, "secret_configured": true}`。

若 `secret_configured` 为 `false`，说明运行中的 pm2 进程未读到 `WECHAT_SECRET`（常见原因：secrets 文件路径不对、未 `--update-env` 重启）。

## 本地爬取后上传到服务器

适合在本地电脑长时间跑爬虫，再把数据合并到服务器（保留服务器上的用户、订单、会员等数据）。

### 1. 本地爬取

```powershell
cd C:\zhiyuantianbao\server
python -u crawler_service.py --progress
python -u crawler_service.py --province 河南 --preset full_recent_3y
# 或全国：python -u crawler_service.py --all-provinces --preset full_recent_3y
```

不确定哪些省已爬完时，先执行 `--progress`，会列出 31 省状态并自动生成续爬命令。

爬取结果保存在项目根目录：

```text
database/zhiyuan.db
```

建议先复制一份备份：

```powershell
copy C:\zhiyuantianbao\database\zhiyuan.db C:\zhiyuantianbao\database\zhiyuan_local.db
```

### 2. 上传到服务器

将 `zhiyuan_local.db` 通过远程桌面、FTP、网盘等方式复制到服务器，例如：

```text
C:\zhiyuantianbao\database\zhiyuan_local.db
```

### 3. 合并到服务器数据库（推荐）

```powershell
cd C:\zhiyuantianbao\server
pm2 stop zhiyuan-backend
copy C:\zhiyuantianbao\database\zhiyuan.db C:\zhiyuantianbao\database\zhiyuan_backup.db
python db_merge.py --source C:\zhiyuantianbao\database\zhiyuan_local.db --target C:\zhiyuantianbao\database\zhiyuan.db
pm2 start zhiyuan-backend
```

`db_merge.py` 只合并院校、专业、录取、招生计划和采集日志，**不会覆盖**用户档案、订单、会员、志愿草稿。

### 4. 整库替换（仅适用于服务器尚无业务数据）

若服务器还是空库、没有真实用户，也可以直接替换：

```powershell
pm2 stop zhiyuan-backend
copy C:\zhiyuantianbao\database\zhiyuan.db C:\zhiyuantianbao\database\zhiyuan.db
pm2 start zhiyuan-backend
```

## 已支持能力

- 学生档案保存 / 查询
- 家长绑定学生
- 院校 / 专业 / 录取数据查询
- 近三年位次加权推荐
- 风险排查
- 志愿草稿新增 / 更新 / 删除 / 查询
- 后台数据导入
- 后台学生档案管理

## MySQL 迁移

MySQL 建表脚本：

```text
database/schema.mysql.sql
```

建议流程：

1. 在 MySQL 8.0+ 创建测试库并执行 `schema.mysql.sql`
2. 从 SQLite 导出 CSV
3. 按表导入 MySQL
4. 修改后端 `db.py`，将 SQLite 连接替换为 MySQL 连接池
5. 先在测试环境跑通导入、推荐、草稿、后台页面
6. 再切换正式环境

后续如要正式迁移，建议增加：

```text
pymysql 或 mysqlclient
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME 环境变量
连接池
迁移校验脚本
```

## 真机测试

微信开发者工具里使用 `127.0.0.1` 可以调试，但真机访问不到电脑本机的 `127.0.0.1`。

真机测试推荐：

1. 手机和电脑连接同一个局域网
2. 查询电脑局域网 IP，例如 `192.168.1.8`
3. 修改小程序接口地址：

```text
utils/request.js
```

把：

```text
http://127.0.0.1:8001
```

改为：

```text
http://192.168.1.8:8001
```

4. Windows 防火墙允许 Python / 8001 端口访问
5. 微信开发者工具勾选“不校验合法域名”
6. 真机预览测试

正式上线必须使用 HTTPS，并在微信公众平台配置合法 request 域名。

当前生产 API 域名：

```text
https://api.zntb.lhyun.net
```

小程序 `utils/request.js` 中 `BASE_URL` 已指向该地址。微信公众平台 request 合法域名填写：

```text
api.zntb.lhyun.net
```

## 虚拟支付（会员）

小程序会员中心已接入**小程序虚拟支付**（道具直购 `short_series_goods`），价格以星鼎豆展示（1 元 = 10 星鼎豆）。

`ecosystem.config.js` 中配置：

```text
WECHAT_VIRTUAL_PAY_OFFER_ID=1450554502
WECHAT_VIRTUAL_PAY_ENV=0
```

`ecosystem.secrets.js` 中配置：

```text
WECHAT_SECRET=小程序Secret
WECHAT_VIRTUAL_PAY_APP_KEY=现网AppKey
WECHAT_VIRTUAL_PAY_SANDBOX_APP_KEY=沙箱AppKey
```

可选：若虚拟支付后台道具 ID 不是 `trial` / `standard` / `premium`，可设置：

```text
WECHAT_VIRTUAL_PRODUCT_TRIAL=道具ID
WECHAT_VIRTUAL_PRODUCT_STANDARD=道具ID
WECHAT_VIRTUAL_PRODUCT_PREMIUM=道具ID
```

部署步骤：

1. 虚拟支付后台为三个会员套餐创建并发布道具，价格（分）分别为 `1990` / `9900` / `16800`
2. 配置发货推送 URL：`https://api.zntb.lhyun.net/api/payments/virtual/deliver-notify`
3. 重启：`pm2 restart zhiyuan-backend --update-env`
4. 访问 `GET /api/payments/wechat/status`，返回 `{"enabled": true}` 表示虚拟支付就绪

## 后台原路退款

管理后台「收款订单」页点击退款时：

- **虚拟支付订单**（`pay_method=virtual_pay`）：调用 `/xpay/refund_order` 原路退回
- **历史微信支付订单**（`pay_method=wechat_pay`）：仍走微信 V3 `/v3/refund/domestic/refunds`
- **线下/人工订单**：仅标记退款并撤销会员

历史微信退款仍需配置 `WECHAT_PAY_API_V3_KEY`、`WECHAT_PAY_SERIAL_NO` 与商户私钥。
