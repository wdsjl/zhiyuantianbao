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

浏览器或 curl 能打开且内容与微信后台一致即可点「验证」。

## 部署后

```powershell
pm2 restart zhiyuan-backend
curl.exe https://api.zntb.lhyun.net/eMyfL8Z1dv_df4d.txt
```
