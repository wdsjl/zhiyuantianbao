const { getCurrentUserId, goMembershipPage } = require('./membership');
const { request } = require('./request');

const REPORT_BEAN_COST = 500;
const NON_REFUND_NOTICE = '星鼎豆充值后不支持退款，已消费的星鼎豆不退还。';

const PLAN_GRANTS = {
  trial: { name: '普通卡', beans: 2000, price: 19.9 },
  standard: { name: '金卡', beans: 12000, price: 99 },
  premium: { name: '白金卡', beans: 24000, price: 168 }
};

function fetchBeanBalance() {
  const userId = getCurrentUserId();
  if (!userId) {
    return Promise.reject(new Error('请先登录'));
  }
  return request({ url: '/api/membership/beans', data: { user_id: Number(userId) } });
}

function consumeReportBeans(reportTitle) {
  const userId = getCurrentUserId();
  return request({
    url: '/api/membership/beans/consume-report',
    method: 'POST',
    data: {
      user_id: Number(userId),
      report_title: reportTitle || 'AI 报告'
    }
  });
}

function buildRechargeHint() {
  return [
    '普通卡：¥19.9 → 2000 星鼎豆',
    '金卡：¥99 → 12000 星鼎豆',
    '白金卡：¥168 → 24000 星鼎豆',
    `每次生成报告扣除 ${REPORT_BEAN_COST} 星鼎豆`
  ].join('\n');
}

function confirmReportBeanDeduction(reportTitle) {
  return fetchBeanBalance()
    .then((res) => {
      const balance = Number(res.balance) || 0;
      const cost = Number(res.report_cost) || REPORT_BEAN_COST;
      const title = reportTitle || 'AI 报告';

      if (balance < cost) {
        return new Promise((resolve) => {
          wx.showModal({
            title: '星鼎豆不足',
            content: `生成一次${title}需要 ${cost} 星鼎豆。\n当前余额：${balance} 星鼎豆\n\n${buildRechargeHint()}\n\n${NON_REFUND_NOTICE}`,
            confirmText: '去充值',
            cancelText: '取消',
            success: (modalRes) => {
              if (modalRes.confirm) goMembershipPage();
              resolve(false);
            }
          });
        });
      }

      const afterBalance = balance - cost;
      return new Promise((resolve) => {
        wx.showModal({
          title: '消费确认',
          content: [
            `生成一次${title}将扣除 ${cost} 星鼎豆。`,
            `当前余额：${balance} 星鼎豆`,
            `扣后余额：${afterBalance} 星鼎豆`,
            '',
            NON_REFUND_NOTICE,
            '确认后继续生成？'
          ].join('\n'),
          confirmText: '确认生成',
          cancelText: '取消',
          success: (modalRes) => resolve(!!modalRes.confirm)
        });
      });
    })
    .catch((error) => {
      wx.showToast({ title: error.message || '星鼎豆信息加载失败', icon: 'none' });
      return false;
    });
}

module.exports = {
  REPORT_BEAN_COST,
  PLAN_GRANTS,
  NON_REFUND_NOTICE,
  fetchBeanBalance,
  consumeReportBeans,
  confirmReportBeanDeduction
};
