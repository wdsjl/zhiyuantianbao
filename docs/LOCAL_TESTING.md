# 本地测试命令合集

本文档用于在本地电脑测试“智愿填报”微信小程序和 FastAPI 后端。以下命令默认使用 Windows PowerShell，并假设项目目录是：

```powershell
E:\zhiyuantianbao
```

如果你的项目目录不同，请把命令里的路径替换成自己的路径。

## 1. 进入项目目录

```powershell
cd E:\zhiyuantianbao
```

## 2. 拉取最新测试分支

如果你要测试当前 Cloud Agent 开发的版本，执行：

```powershell
git fetch origin cursor/add-project-context-bba1
git checkout cursor/add-project-context-bba1
git pull origin cursor/add-project-context-bba1
```

确认当前分支：

```powershell
git branch --show-current
```

应看到：

```text
cursor/add-project-context-bba1
```

## 3. 清理本地缓存文件

微信开发者工具会扫描项目目录，建议删除 Python 缓存目录：

```powershell
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

如果你只想删后端目录里的缓存：

```powershell
Remove-Item -Recurse -Force server\__pycache__
```

如果提示目录不存在，可以忽略。

## 4. 安装后端依赖

进入后端目录：

```powershell
cd E:\zhiyuantianbao\server
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

如果你的电脑使用 `python3` 命令：

```powershell
python3 -m pip install -r requirements.txt
```

## 5. 初始化 SQLite 数据库

回到项目根目录：

```powershell
cd E:\zhiyuantianbao
```

初始化数据库：

```powershell
python database\init_db.py
```

如果使用 `python3`：

```powershell
python3 database\init_db.py
```

成功时会看到类似：

```text
Database initialized: E:\zhiyuantianbao\database\zhiyuan.db
```

说明：

- `database\zhiyuan.db` 是本地数据库文件。
- 这个文件不会提交到 Git。
- 如果你想重置本地数据，可以先删除数据库再重新初始化：

```powershell
Remove-Item database\zhiyuan.db
python database\init_db.py
```

## 6. 启动后端

进入后端目录：

```powershell
cd E:\zhiyuantianbao\server
```

启动：

```powershell
python start.py
```

成功时会看到：

```text
Uvicorn running on http://127.0.0.1:8001
Application startup complete.
```

这个 PowerShell 窗口不要关闭。关闭后，后端服务也会停止。

## 7. 浏览器验证后端

打开新的 PowerShell 窗口，执行：

```powershell
curl http://127.0.0.1:8001/health
```

成功返回：

```json
{"status":"ok"}
```

也可以直接用浏览器打开：

```text
http://127.0.0.1:8001/health
```

常用本地地址：

```text
后台管理：
http://127.0.0.1:8001/admin

会员中心浏览器预览：
http://127.0.0.1:8001/preview/membership

接口文档：
http://127.0.0.1:8001/docs
```

## 8. 微信开发者工具导入小程序

1. 打开微信开发者工具。
2. 选择“导入项目”。
3. 项目目录选择：

```text
E:\zhiyuantianbao
```

也就是包含 `app.json` 的目录。

4. AppID：
   - 如果已有真实小程序 AppID，填真实 AppID。
   - 只是本地测试，也可以使用测试号或游客模式，按微信开发者工具提示操作。

5. 点击“编译”。

## 9. 小程序本地接口地址

小程序接口地址在：

```text
utils\request.js
```

默认会先请求：

```text
http://127.0.0.1:8001
```

如果失败，会自动重试：

```text
http://localhost:8001
```

所以本地模拟器一般不需要改接口地址。

## 10. 微信开发者工具本地设置

在微信开发者工具里打开：

```text
详情 -> 本地设置
```

建议本地测试时勾选：

```text
不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书
```

如果你的电脑开启了代理，建议确认代理绕过：

```text
127.0.0.1
localhost
```

或者临时关闭微信开发者工具的系统代理。

## 11. 清缓存并重新编译

如果你刚拉取过代码，但微信开发者工具还报旧错误，执行：

```text
工具 -> 清缓存 -> 清除文件缓存
```

然后重新点击：

```text
编译
```

## 12. 常见问题处理

### 12.1 WXSS 文件编译错误 unexpected `�`

如果看到：

```text
pages/volunteer/volunteer.wxss(79:11): unexpected `�`
```

先确认你已经拉取最新代码：

```powershell
cd E:\zhiyuantianbao
git pull origin cursor/add-project-context-bba1
```

检查文件：

```powershell
notepad pages\volunteer\volunteer.wxss
```

应该看到英文 class：

```css
.gradient-rush
.gradient-stable
.gradient-safe
.gradient-backup
```

不应该再看到：

```css
.gradient-冲
.gradient-稳
.gradient-保
.gradient-垫
```

如果仍然看到中文 class，说明本地代码还不是最新。

### 12.2 小程序控制台 Error: timeout

先确认后端还在运行：

```powershell
curl http://127.0.0.1:8001/health
```

如果浏览器或 curl 访问失败，重新启动后端：

```powershell
cd E:\zhiyuantianbao\server
python start.py
```

如果浏览器能访问，但微信开发者工具 timeout：

1. 检查“详情 -> 本地设置”是否已关闭合法域名校验。
2. 检查代理是否影响 `127.0.0.1` / `localhost`。
3. 清除微信开发者工具文件缓存后重新编译。

### 12.3 server\__pycache__ 保留目录提示

如果看到：

```text
server\__pycache__ 目录下的所有文件将会被忽略
```

可以执行：

```powershell
cd E:\zhiyuantianbao
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

当前项目配置也已经在 `project.config.json` 中忽略了 `server/`、`database/`、`docs/`。

### 12.4 favicon.ico 404

如果后端日志出现：

```text
GET /favicon.ico 404 Not Found
```

可以忽略。这只是浏览器自动请求网站图标，不影响功能。

### 12.5 Pydantic model_name warning

如果后端启动时出现：

```text
UserWarning: Field "model_name" has conflict with protected namespace "model_"
```

可以先忽略。它不是启动失败。

## 13. 真机扫码预览

如果你只在微信开发者工具模拟器里测试，不需要改接口地址。

如果你要手机扫码预览，小程序里的 `127.0.0.1` 指的是手机自己，不是电脑，所以需要改成电脑局域网 IP。

查看电脑 IP：

```powershell
ipconfig
```

找到类似：

```text
IPv4 地址 . . . . . . . . . . . . : 192.168.1.8
```

然后修改：

```text
utils\request.js
```

把：

```js
const BASE_URL = 'http://127.0.0.1:8001';
```

改为：

```js
const BASE_URL = 'http://192.168.1.8:8001';
```

同时确保：

1. 手机和电脑在同一个 Wi-Fi。
2. Windows 防火墙允许 Python 或 8001 端口访问。
3. 微信开发者工具已关闭合法域名校验。

如果只是在电脑模拟器里测试，不建议改成局域网 IP。

## 14. 推荐的完整测试顺序

第一次本地测试建议按这个顺序：

```powershell
cd E:\zhiyuantianbao
git fetch origin cursor/add-project-context-bba1
git checkout cursor/add-project-context-bba1
git pull origin cursor/add-project-context-bba1
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
python -m pip install -r server\requirements.txt
python database\init_db.py
cd server
python start.py
```

然后打开浏览器确认：

```text
http://127.0.0.1:8001/health
http://127.0.0.1:8001/admin
http://127.0.0.1:8001/preview/membership
```

最后打开微信开发者工具，导入：

```text
E:\zhiyuantianbao
```

清缓存后重新编译。
