# 域名与 HTTPS 证书部署说明

本文档以当前接口域名为例：

```text
api.zntb.lhyun.net
```

小程序正式环境必须使用 HTTPS 域名，不能直接使用 `http://IP:端口`。

## 1. DNS 解析

在域名服务商后台添加解析记录：

```text
记录类型：A
主机记录：api
记录值：你的服务器公网 IP
```

解析后，用本地 PowerShell 检查：

```powershell
nslookup api.zntb.lhyun.net
```

返回你的服务器公网 IP 即表示解析基本生效。

## 2. 后端服务端口

FastAPI 后端仍然按项目默认方式启动：

```bash
cd server
python start.py
```

默认监听：

```text
http://127.0.0.1:8001
```

正式部署时建议不要直接暴露 8001 给公网，而是使用 Nginx 监听 80/443，再反向代理到本机 8001。

## 3. 证书放在哪里

证书只放在服务器上，不放进小程序代码，也不要提交到 Git。

推荐两种方式。

### 方式 A：Certbot 自动证书路径

如果使用 Certbot / Let's Encrypt，证书通常在：

```text
/etc/letsencrypt/live/api.zntb.lhyun.net/fullchain.pem
/etc/letsencrypt/live/api.zntb.lhyun.net/privkey.pem
```

Nginx 直接引用这两个文件即可。

### 方式 B：手动上传证书

如果你从阿里云、腾讯云、Cloudflare 或其他平台下载了 Nginx 证书，可以放到：

```text
/etc/nginx/ssl/api.zntb.lhyun.net/fullchain.pem
/etc/nginx/ssl/api.zntb.lhyun.net/privkey.pem
```

创建目录：

```bash
sudo mkdir -p /etc/nginx/ssl/api.zntb.lhyun.net
```

上传证书后设置权限：

```bash
sudo chown -R root:root /etc/nginx/ssl/api.zntb.lhyun.net
sudo chmod 600 /etc/nginx/ssl/api.zntb.lhyun.net/privkey.pem
sudo chmod 644 /etc/nginx/ssl/api.zntb.lhyun.net/fullchain.pem
```

常见文件名对应关系：

```text
*.pem / fullchain.pem / bundle.crt  -> 证书链文件
*.key / privkey.pem                 -> 私钥文件
```

私钥文件非常敏感，不能发给别人，不能提交到仓库。

## 4. Nginx 配置示例

新建配置文件：

```bash
sudo nano /etc/nginx/conf.d/api.zntb.lhyun.net.conf
```

写入：

```nginx
server {
    listen 80;
    server_name api.zntb.lhyun.net;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.zntb.lhyun.net;

    ssl_certificate /etc/letsencrypt/live/api.zntb.lhyun.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.zntb.lhyun.net/privkey.pem;

    # 如果你是手动上传证书，改成：
    # ssl_certificate /etc/nginx/ssl/api.zntb.lhyun.net/fullchain.pem;
    # ssl_certificate_key /etc/nginx/ssl/api.zntb.lhyun.net/privkey.pem;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

检查配置：

```bash
sudo nginx -t
```

重载 Nginx：

```bash
sudo systemctl reload nginx
```

## 5. HTTPS 验证

服务器上验证：

```bash
curl -I https://api.zntb.lhyun.net/health
```

本地电脑浏览器打开：

```text
https://api.zntb.lhyun.net/health
```

正常返回：

```json
{"status":"ok"}
```

后台地址：

```text
https://api.zntb.lhyun.net/admin
```

接口文档：

```text
https://api.zntb.lhyun.net/docs
```

## 6. 微信公众平台配置

微信小程序正式请求前，需要到微信公众平台配置合法域名：

```text
开发管理 -> 开发设置 -> 服务器域名 -> request 合法域名
```

添加：

```text
https://api.zntb.lhyun.net
```

注意：

- 必须是 HTTPS。
- 不能带端口。
- 证书必须有效且域名匹配。

## 7. 项目中的域名配置

小程序接口配置在：

```text
utils/request.js
```

当前生产接口域名：

```js
const PRODUCTION_BASE_URL = 'https://api.zntb.lhyun.net';
```

发布版小程序默认使用：

```text
https://api.zntb.lhyun.net
```

开发版小程序默认优先使用本地：

```text
http://127.0.0.1:8001
http://localhost:8001
```

如果你在微信开发者工具里想强制测试线上接口，可以在控制台执行：

```js
wx.setStorageSync('apiBaseUrl', 'https://api.zntb.lhyun.net')
```

恢复默认本地调试：

```js
wx.removeStorageSync('apiBaseUrl')
```

然后重新编译或重启小程序。

## 8. 安全提醒

正式公网部署前，后台入口必须增加登录和权限保护：

```text
https://api.zntb.lhyun.net/admin
```

当前后台仍是开发期管理页面，不建议无保护直接暴露给公网长期使用。
