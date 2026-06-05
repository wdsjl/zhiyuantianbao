module.exports = {
  apps: [{
    name: 'zhiyuan-backend',
    script: 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe',
    args: '-m uvicorn main:app --host 127.0.0.1 --port 8001',
    cwd: 'C:/zhiyuantianbao/server',
    windowsHide: true,
    env: {
      ADMIN_USERNAME: 'admin',
      ADMIN_PASSWORD: 'admin123',
      ADMIN_SESSION_SECRET: 'please-change-this-secret'
    }
  }]
};
