const path = require('path');
const fs = require('fs');

const root = path.join(__dirname, '..');
const secretsJsPath = path.join(root, 'ecosystem.secrets.js');
const localEnvPath = path.join(root, 'server', 'local.secrets.env');

const REQUIRED_KEYS = ['DOUYIN_APP_SECRET', 'DOUYIN_SPI_TOKEN'];
const OPTIONAL_KEYS = ['WECHAT_SECRET', 'WECHAT_VIRTUAL_PAY_APP_KEY'];

function parseEnvFile(content) {
  const values = {};
  for (const line of content.split(/\r?\n/)) {
    const text = line.trim();
    if (!text || text.startsWith('#') || !text.includes('=')) continue;
    const idx = text.indexOf('=');
    const key = text.slice(0, idx).trim();
    let value = text.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"'))
      || (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (value) values[key] = value;
  }
  return values;
}

function loadSecrets() {
  const merged = {};
  let source = '';

  if (fs.existsSync(secretsJsPath)) {
    try {
      const fromJs = require(secretsJsPath);
      Object.assign(merged, fromJs);
      source = 'ecosystem.secrets.js';
    } catch (error) {
      console.error('ecosystem.secrets.js load failed:', error.message);
      process.exit(1);
    }
  }

  if (fs.existsSync(localEnvPath)) {
    const fromEnv = parseEnvFile(fs.readFileSync(localEnvPath, 'utf8'));
    for (const [key, value] of Object.entries(fromEnv)) {
      if (!merged[key]) {
        merged[key] = value;
        if (!source) source = 'server/local.secrets.env';
        else if (source !== 'both') source = 'both';
      }
    }
  }

  return { merged, source };
}

console.log('project root:', root);
console.log('ecosystem.secrets.js:', secretsJsPath, 'exists:', fs.existsSync(secretsJsPath));
console.log('local.secrets.env:', localEnvPath, 'exists:', fs.existsSync(localEnvPath));

const { merged: secrets, source } = loadSecrets();

if (!Object.keys(secrets).length) {
  console.error('\nERROR: 未找到任何密钥。请创建 ecosystem.secrets.js 或 server/local.secrets.env');
  process.exit(1);
}

console.log('\nsecrets source:', source || '(unknown)');
console.log('loaded keys:', Object.keys(secrets).join(', ') || '(empty)');

let ok = true;
for (const key of REQUIRED_KEYS) {
  const present = Boolean(secrets[key]);
  console.log(`${key}:`, present ? 'OK' : 'MISSING');
  if (!present) ok = false;
}
for (const key of OPTIONAL_KEYS) {
  console.log(`${key}:`, secrets[key] ? 'OK' : '(optional, missing)');
}

if (!ok) {
  console.error('\nERROR: 缺少抖音必需密钥。请编辑 ecosystem.secrets.js 或 server/local.secrets.env');
  process.exit(1);
}

console.log('\nAll required Douyin secrets OK');
