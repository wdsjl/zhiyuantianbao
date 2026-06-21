# 回归锁（已修复功能契约）

以下功能已在 `cursor/membership-pricing-revamp-0c75` 修复并**锁死**。修改相关文件前必须先跑测试；未通过不得合并。

## 锁死项

| 模块 | 不变量 |
|------|--------|
| 省份志愿 | 河南本科批 **48** 条；`volunteer_count` 为 0 或 9 时走省份规则，禁止硬编码 9 |
| 小程序志愿 | `pages/volunteer/volunteer.js` 必须 `volunteer_count: 0` 并调用 `/api/province-rules/resolve` |
| 白金 PDF | `premium` 套餐 `pdf_export` 权限 `limit=-1`；DB upsert 同步 |
| 院校检索 | 城市名兼容（北京/北京市）；双一流含 985/211；单次加载 200 条 |
| 虚拟支付发货 | 通知微信用 `VPO...` 单号；支持 `assume_paid`；双环境 AppKey 重试 |
| 虚拟支付道具 | 普通卡 `xdptk`/1990分；白金卡 `xdbjk`/29800分；`env=0` 现网 |
| 支付配置 | `ecosystem.secrets.js` 部署前必须跑 `validate-ecosystem-secrets.ps1` |
| 发货回调 | `GET+POST /api/payments/virtual/deliver-notify` 必须保留 |

## 校验命令

```bash
cd server
python -m unittest test_regression_locks.py test_membership_pricing.py -v
```

服务器：

```powershell
powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\verify-regression-locks.ps1
powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\validate-ecosystem-secrets.ps1
powershell -ExecutionPolicy Bypass -File C:\zhiyuantianbao\scripts\safe-pm2-restart.ps1
```

**部署艺体或其他功能后重启后端，请用 `safe-pm2-restart.ps1`，不要用裸 `pm2 restart`。**

## 契约源码

- `server/regression_locks.py` — 必需/禁止的源码片段
- `server/test_regression_locks.py` — 自动化测试

**禁止**在未更新契约与测试的情况下修改上表涉及文件的行为。
