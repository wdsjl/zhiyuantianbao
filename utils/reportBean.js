const { fetchEntitlements, goMembershipPage } = require('./membership');

// 每次生成报告扣除的星鼎豆（与套餐标价对应：金额元 × 100）
const REPORT_BEAN_COST = {
  trial: 1990,
  standard: 9900,
  premium: 16800
};

const PLAN_LABELS = {
  trial: '体验月卡',
  standard: '标准年卡',
  premium: '尊享年卡',
  free: '免费版'
};

function getReportBeanCost(planCode, planPrice) {
  if (REPORT_BEAN_COST[planCode] != null) return REPORT_BEAN_COST[planCode];
  const price = Number(planPrice) || 0;
  if (price > 0) return Math.round(price * 100);
  return null;
}

function buildReportBeanConfirmContent(planCode, planName, beanCost, reportTitle) {
  const title = reportTitle || 'AI 报告';
  const label = planName || PLAN_LABELS[planCode] || '当前套餐';
  return `生成一次${title}将扣除 ${beanCost} 星鼎豆（${label}）。\n\n确认后将开始生成，请知悉。`;
}

function confirmReportBeanDeduction(reportTitle) {
  return fetchEntitlements()
    .then((entitlements) => {
      const plan = (entitlements && entitlements.plan) || { plan_code: 'free', plan_name: '免费版' };
      const planCode = plan.plan_code || 'free';
      const beanCost = getReportBeanCost(planCode, plan.price);

      if (planCode === 'free' || beanCost == null) {
        return new Promise((resolve) => {
          wx.showModal({
            title: '需要开通会员',
            content: '生成报告需先开通会员。\n体验月卡每次生成扣除 1990 星鼎豆，标准年卡 9900 星鼎豆，尊享年卡 16800 星鼎豆。',
            confirmText: '去开通',
            cancelText: '取消',
            success: (res) => {
              if (res.confirm) goMembershipPage();
              resolve(false);
            }
          });
        });
      }

      return new Promise((resolve) => {
        wx.showModal({
          title: '确认扣除星鼎豆',
          content: buildReportBeanConfirmContent(planCode, plan.plan_name, beanCost, reportTitle),
          confirmText: '确认生成',
          cancelText: '取消',
          success: (res) => resolve(!!res.confirm)
        });
      });
    })
    .catch(() => {
      wx.showToast({ title: '会员信息加载失败', icon: 'none' });
      return false;
    });
}

module.exports = {
  REPORT_BEAN_COST,
  getReportBeanCost,
  confirmReportBeanDeduction
};
