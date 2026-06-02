# 智愿填报项目上下文

本文档供后续 Cloud Agent 或开发者快速了解当前仓库状态。开始任何新任务前，建议先阅读本文档，再结合具体代码确认最新实现。

## 项目概览

- 仓库：`wdsjl/zhiyuantianbao`
- 项目形态：微信小程序前端 + FastAPI 后端 + SQLite 本地数据库
- 小程序接口基础地址：`utils/request.js`
- 生产接口域名：`https://api.zntb.lhyun.net`
- 后端默认本地地址：`http://127.0.0.1:8001`
- 后台入口：`http://127.0.0.1:8001/admin`
- FastAPI 文档：`http://127.0.0.1:8001/docs`

## 目录速览

```text
.
├── app.js / app.json / app.wxss      # 微信小程序入口配置
├── pages/                            # 小程序页面
│   ├── membership/                   # 会员中心
│   ├── mine/                         # 我的
│   ├── profile/                      # 学生档案
│   ├── volunteer/                    # 志愿填报
│   └── ...
├── utils/
│   ├── request.js                    # 小程序请求 BASE_URL
│   ├── membership.js                 # 小程序会员能力封装
│   └── ...
├── server/
│   ├── start.py                      # 后端启动入口
│   ├── main.py                       # FastAPI 路由
│   ├── db.py                         # SQLite 连接，指向 database/zhiyuan.db
│   ├── admin_views.py                # 后台 HTML 页面
│   ├── membership_service.py         # 会员套餐、权益、用户会员、次数限制
│   ├── payment_service.py            # 订单、开通/续费申请、客服配置、CSV 导出
│   ├── dashboard_service.py          # 运营看板统计
│   └── ...
└── database/
    ├── schema.sql                    # SQLite 基础表结构
    ├── seed.sql                      # 基础种子数据
    ├── init_db.py                    # 本地 SQLite 初始化脚本
    └── schema.mysql.sql              # MySQL 迁移参考脚本
```

## 本地启动与初始化

### 1. 安装依赖

```bash
cd server
pip install -r requirements.txt
```

### 2. 初始化数据库

本地 SQLite 数据库文件 `database/zhiyuan.db` 不提交到 Git。新的 Cloud Agent 环境通常需要重新初始化：

```bash
python database/init_db.py
```

说明：

- `database/init_db.py` 会执行 `database/schema.sql` 和 `database/seed.sql`。
- 后端运行时还会在启动阶段通过 `ensure_membership_tables()`、`ensure_payment_tables()` 自动补齐会员、支付、申请和客服配置相关表。
- 如果遇到基础表不存在，优先确认是否已执行初始化脚本。

### 3. 启动后端

```bash
cd server
python start.py
```

默认服务地址：

```text
http://127.0.0.1:8001
```

### 4. 小程序接口地址

小程序请求地址在：

```text
utils/request.js
```

默认值：

```js
const BASE_URL = 'http://127.0.0.1:8001';
```

真机调试时，手机无法访问电脑本机的 `127.0.0.1`，需要改成局域网 IP，例如 `http://192.168.1.8:8001`，并在微信开发者工具中按需勾选“不校验合法域名”。

## 已完成能力

### 小程序会员中心

主要文件：

- `pages/membership/membership.js`
- `pages/membership/membership.wxml`
- `pages/membership/membership.wxss`
- `utils/membership.js`

已支持：

- 展示当前会员状态
- 展示套餐权益
- 支持提交会员开通申请
- 支持续费申请
- 展示用户自己的申请记录和订单记录
- 展示后台配置的客服微信、电话和说明

开通/续费申请通过：

```text
POST /api/membership/open-requests
```

字段约定：

- `request_type = open`：新开通申请
- `request_type = renew`：续费申请

### 后端会员体系

主要文件：

- `server/membership_service.py`
- `server/main.py`

核心表：

- `membership_plans`：会员套餐
- `membership_permissions`：权益定义
- `membership_plan_permissions`：套餐权益和次数限制
- `user_memberships`：用户会员记录
- `user_permission_usage`：功能次数使用记录

默认套餐：

- `free`：免费版
- `trial`：体验月卡
- `standard`：标准年卡
- `premium`：尊享年卡

次数约定：

- `limit_value < 0` 表示不限次数。
- `ai_plan_explain` 对 `standard` / `premium` 使用按天周期：`day:YYYY-MM-DD`。
- 其他有次数限制的会员权益通常按会员周期：`membership:{user_membership_id}`。

会员到期处理：

- 后端启动时会调用 `expire_overdue_memberships()`。
- 获取权益时也会触发到期处理。

### 后台会员管理

主要文件：

- `server/admin_views.py`
- `server/main.py`
- `server/membership_service.py`

后台入口：

```text
http://127.0.0.1:8001/admin
```

已支持：

- 查看和管理会员套餐、权益
- 查看会员用户
- 给用户开通或调整会员
- 即将到期会员续费
- 查看会员功能次数记录
- 清零或删除次数记录

### 支付与申请管理

主要文件：

- `server/payment_service.py`
- `server/admin_views.py`
- `server/main.py`

核心表：

- `membership_open_requests`：开通/续费申请
- `payment_orders`：支付/收款订单
- `app_settings`：客服配置等应用设置

已支持：

- 用户提交开通/续费申请
- 后台查看待处理申请
- 后台确认申请后生成订单并开通会员
- 后台取消申请
- 后台配置客服微信、电话、说明

申请字段约定：

- `request_type = open`
- `request_type = renew`

### 订单管理

主要文件：

- `server/payment_service.py`
- `server/admin_views.py`
- `server/main.py`

已支持：

- 手动登记收款并开通会员
- 订单列表展示订单类型
- 即将到期会员续费订单自动标记为续费

订单字段约定：

- `order_type = open`：开通订单
- `order_type = renew`：续费订单
- `order_type = manual`：后台手动登记

### 客服配置

主要文件：

- `server/payment_service.py`
- `pages/membership/membership.js`

接口：

```text
GET /api/membership/support-contact
```

后台可配置：

- 客服微信：`support_wechat`
- 客服电话：`support_phone`
- 说明文案：`support_note`

小程序会员中心会展示这些联系方式，用于引导用户提交申请后联系客服确认收款。

### 运营看板

主要文件：

- `server/dashboard_service.py`
- `server/admin_views.py`

后台首页已展示：

- 待处理申请数
- 今日申请数
- 今日处理数
- 今日订单数
- 今日实收
- 今日新开通收入
- 今日续费收入
- 累计实收
- 累计新开通收入
- 累计续费收入
- 申请转化率
- 开通转化率
- 续费转化率
- 有效会员数
- 7 天内到期会员数
- AI 今日消耗

### CSV 导出

主要文件：

- `server/payment_service.py`
- `server/main.py`

已支持：

- 订单导出 CSV：`GET /admin/payments/export`
- 开通/续费申请导出 CSV：`GET /admin/payments/requests/export`

导出响应使用 `utf-8-sig`，兼容 Excel 中文打开。


### 后台登录和权限

主要文件：

- `server/admin_auth_service.py`
- `server/main.py`
- `server/admin_views.py`

核心表：

- `admin_accounts`：后台管理员账号

已支持：

- 首次访问 `/admin` 时，如果没有后台账号，会跳转 `/admin/setup` 初始化超级管理员
- `/admin/login` 后台登录
- `/admin/logout` 退出登录
- `/admin/accounts` 多账号管理、重置密码、启停账号、角色分配
- 角色权限：`super_admin`、`admin`、`operator`、`viewer`

生产环境建议配置 `ADMIN_SESSION_SECRET`，避免使用默认开发密钥。

## 常用接口

会员相关：

```text
GET  /api/membership/plans
GET  /api/membership/entitlements
GET  /api/membership/my-status
GET  /api/membership/support-contact
POST /api/membership/open-requests
GET  /api/membership/permissions/{permission_code}/check
POST /api/membership/permissions/{permission_code}/consume
```

认证相关：

```text
POST /api/auth/login
```

本地开发时，如果没有配置 `WECHAT_APPID` 和 `WECHAT_SECRET`，后端会自动生成 `dev_xxx` 类型 openid，方便调试。

## 环境变量

示例文件：

```text
.env.example
```

当前包含：

```text
WECHAT_APPID=
WECHAT_SECRET=

# Optional future production settings
# API_BASE_URL=https://api.example.com
# DB_HOST=
# DB_PORT=3306
# DB_USER=
# DB_PASSWORD=
# DB_NAME=
```

正式上线前至少需要配置真实：

- `WECHAT_APPID`
- `WECHAT_SECRET`

当前生产接口域名已按 `https://api.zntb.lhyun.net` 配置；HTTPS 证书和 Nginx 反向代理说明见 `docs/DOMAIN_SSL_DEPLOYMENT.md`。

## 部署与上线注意事项

1. 正式小程序部署需要 HTTPS 域名。
2. 微信公众平台需要配置 request 合法域名。
3. 后台管理入口在正式公网部署前必须增加登录和权限保护。
4. 当前后端默认允许所有 CORS 来源，正式部署应按实际域名收敛。
5. 本地 SQLite 数据库 `database/zhiyuan.db` 不提交；Cloud Agent 或新环境需要重新执行初始化脚本，或提供 seed/schema 恢复数据。
6. 若迁移 MySQL，可参考 `database/schema.mysql.sql` 和 `server/README.md` 的迁移说明。

## 后续开发建议

- 新增接口时优先在 `server/main.py` 添加路由，在对应 service 文件内放业务逻辑。
- 涉及会员权益时优先复用 `check_permission()`、`consume_permission()`、`get_user_entitlements()`。
- 涉及订单或申请时优先复用 `payment_service.py` 内已有的创建订单、处理申请、导出 CSV 方法。
- 新增后台页面时保持 `admin_views.py` 当前的纯 HTML 字符串风格。
- 新增小程序 API 请求时复用 `utils/request.js` 的 `request()`。
- 修改数据库结构时要同时考虑：
  - `database/schema.sql`
  - `database/schema.mysql.sql`（如需保持 MySQL 迁移参考）
  - 运行时 `ensure_*_tables()` 是否需要兼容已有 SQLite 库