const PLAN_BEAN_GRANT = {
  trial: 2000,
  standard: 12000,
  premium: 24000
};

const PLAN_CATALOG = {
  trial: {
    plan_name: '普通卡',
    description: '一次充值 ¥19.9，到账 2000 星鼎豆',
    price: 19.9
  },
  standard: {
    plan_name: '金卡',
    description: '起充 ¥99，到账 12000 星鼎豆',
    price: 99
  },
  premium: {
    plan_name: '白金卡',
    description: '起充 ¥168，到账 24000 星鼎豆',
    price: 168
  }
};

const PLAN_DISPLAY_NAMES = {
  free: '免费版',
  trial: '普通卡',
  standard: '金卡',
  premium: '白金卡'
};

function enrichPlan(plan) {
  if (!plan || !plan.plan_code) return plan || {};
  const meta = PLAN_CATALOG[plan.plan_code] || {};
  const beanGrant = PLAN_BEAN_GRANT[plan.plan_code] || 0;
  const price = Number(meta.price != null ? meta.price : plan.price) || 0;
  return {
    ...plan,
    plan_name: meta.plan_name || plan.plan_name,
    description: meta.description || plan.description,
    price,
    beanGrant
  };
}

function getPlanDisplayName(planCode, fallbackName) {
  return PLAN_DISPLAY_NAMES[planCode] || fallbackName || '免费版';
}

module.exports = {
  PLAN_BEAN_GRANT,
  PLAN_CATALOG,
  PLAN_DISPLAY_NAMES,
  enrichPlan,
  getPlanDisplayName
};
