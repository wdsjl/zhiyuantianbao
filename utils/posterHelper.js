function stripBase64Prefix(dataUrl) {
  const raw = String(dataUrl || '');
  const index = raw.indexOf('base64,');
  return index >= 0 ? raw.slice(index + 7) : raw;
}

function base64ToTempFilePath(base64Data, filename) {
  const pure = stripBase64Prefix(base64Data);
  if (!pure) {
    return Promise.reject(new Error('二维码数据为空'));
  }
  const filePath = `${wx.env.USER_DATA_PATH}/${filename || `poster_qr_${Date.now()}.png`}`;
  const fs = wx.getFileSystemManager();
  return new Promise((resolve, reject) => {
    fs.writeFile({
      filePath,
      data: pure,
      encoding: 'base64',
      success: () => {
        wx.getImageInfo({
          src: filePath,
          success: () => resolve(filePath),
          fail: (error) => reject(error || new Error('二维码图片无效'))
        });
      },
      fail: (error) => reject(error || new Error('二维码写入失败'))
    });
  });
}

module.exports = {
  base64ToTempFilePath,
  stripBase64Prefix
};
