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
