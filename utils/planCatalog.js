const PLAN_CATALOG = {
  trial: {
    plan_name: '普通卡',
    description: '引流体验卡，含基础查询与测评；不含智能推荐、AI 报告与 PDF 导出',
    price: 19.9
  },
  premium: {
    plan_name: '白金卡',
    description: '报考季全功能畅享，智能推荐、AI 报告、PDF 导出不限次',
    price: 298
  }
};

const PLAN_DISPLAY_NAMES = {
  free: '免费版',
  trial: '普通卡',
  standard: '金卡',
  premium: '白金卡'
};

const SEASON_EXPIRE_LABEL = '报考季有效至当年9月30日';

function enrichPlan(plan) {
  if (!plan || !plan.plan_code) return plan || {};
  const meta = PLAN_CATALOG[plan.plan_code] || {};
  const price = Number(meta.price != null ? meta.price : plan.price) || 0;
  return {
    ...plan,
    plan_name: meta.plan_name || plan.plan_name,
    description: meta.description || plan.description,
    price,
    seasonExpireLabel: SEASON_EXPIRE_LABEL
  };
}

function getPlanDisplayName(planCode, fallbackName) {
  return PLAN_DISPLAY_NAMES[planCode] || fallbackName || '免费版';
}

module.exports = {
  PLAN_CATALOG,
  PLAN_DISPLAY_NAMES,
  SEASON_EXPIRE_LABEL,
  enrichPlan,
  getPlanDisplayName
};
