function requestVirtualPayment(paymentData) {
  return new Promise((resolve, reject) => {
    if (!wx.canIUse('requestVirtualPayment')) {
      reject({ errMsg: '当前微信版本不支持虚拟支付', message: '请升级微信客户端后重试' });
      return;
    }
    wx.requestVirtualPayment({
      mode: paymentData.mode || 'short_series_goods',
      signData: paymentData.signData,
      paySig: paymentData.paySig,
      signature: paymentData.signature,
      success: resolve,
      fail: reject
    });
  });
}

function getLoginCode() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (res) => {
        if (res.code) resolve(res.code);
        else reject(new Error('微信登录失败，请重试'));
      },
      fail: (error) => reject(error)
    });
  });
}

module.exports = {
  requestVirtualPayment,
  getLoginCode
};
