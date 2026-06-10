const path = require('path');
const fs = require('fs');

const secretsPath = path.join(__dirname, '..', 'ecosystem.secrets.js');

console.log('secrets file:', secretsPath);
console.log('exists:', fs.existsSync(secretsPath));

try {
  const secrets = require(secretsPath);
  console.log('loaded keys:', Object.keys(secrets));
  console.log('DOUYIN_APP_SECRET:', secrets.DOUYIN_APP_SECRET ? 'OK' : 'MISSING');
  console.log('DOUYIN_SPI_TOKEN:', secrets.DOUYIN_SPI_TOKEN ? 'OK' : 'MISSING');
  console.log('WECHAT_SECRET:', secrets.WECHAT_SECRET ? 'OK' : 'MISSING');
} catch (error) {
  console.error('load failed:', error.message);
  process.exit(1);
}
