# 域名根目录验证文件

微信小程序「服务器域名 / 业务域名」校验时，将微信提供的 `.txt` 文件放在本目录。

## 服务器路径

```
C:\zhiyuantianbao\public\eMyfL8Z1dv_df4d.txt
```

## 访问地址

```
https://api.zntb.lhyun.net/eMyfL8Z1dv_df4d.txt
```

仅用于校验 **你自己拥有的域名**（如 `api.zntb.lhyun.net`）。

**不要**把校验文件配置到 `gaokao.chsi.com.cn`：阳光高考是教育部官网，你无法在其服务器根目录放置文件，业务域名校验一定会失败。小程序内打开阳光高考章程请使用「复制链接 → 手机浏览器打开」。

## 部署后

```powershell
pm2 restart zhiyuan-backend
curl.exe https://api.zntb.lhyun.net/eMyfL8Z1dv_df4d.txt
```
