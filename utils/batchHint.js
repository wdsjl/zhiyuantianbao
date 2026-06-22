const UNDERGRADUATE_HINT_SCORE = 400;

function isJuniorBatch(batch) {
  return /专科|高职|高专/.test(String(batch || ''));
}

function isUndergraduateBatch(batch) {
  return /本科|一段|二段|一批|二批/.test(String(batch || '')) && !isJuniorBatch(batch);
}

function isArtSportsBatch(batch) {
  return /艺术|体育|艺考|体考/.test(String(batch || ''));
}

function isArtSportsProfile(form) {
  const examType = (form && form.examType) || '';
  const waive = !!(form && form.waiveArtSports);
  return (examType === '艺术类' || examType === '体育类') && !waive;
}

function getBatchMismatchWarning(form, availableBatches) {
  const score = Number(form && form.score);
  const batch = (form && form.targetBatch) || '';
  if (!batch) return '';

  if (form && form.waiveArtSports && isArtSportsBatch(batch)) {
    return '您已勾选「放弃艺体批次」，将按普通类本科生成约48个志愿，而非艺术64个「专业+院校」平行志愿。报艺考请取消该勾选。';
  }

  if (isArtSportsProfile(form) && isArtSportsBatch(batch)) {
    return '';
  }

  if (Number.isFinite(score) && score >= UNDERGRADUATE_HINT_SCORE && isJuniorBatch(batch)) {
    return `当前分数 ${score} 分较高，目标批次为「${batch}」可能填错。本科考生通常应选择「本科批」。`;
  }

  if (Number.isFinite(score) && score > 0 && score < 280 && isUndergraduateBatch(batch)) {
    return `当前分数 ${score} 分偏低，目标批次为「${batch}」可能不匹配，请确认是否应选专科批。`;
  }

  if (Array.isArray(availableBatches) && availableBatches.length) {
    const names = availableBatches.map((item) => item.batch || item);
    const exact = names.includes(batch);
    if (!exact) {
      const summary = availableBatches
        .slice(0, 4)
        .map((item) => `${item.batch}(${item.school_major_count || item.record_count || 0}条)`)
        .join('、');
      return `库内暂无「${batch}」数据。当前省份可用批次：${summary || '无'}。`;
    }
  }

  return '';
}

module.exports = {
  UNDERGRADUATE_HINT_SCORE,
  getBatchMismatchWarning,
  isJuniorBatch,
  isUndergraduateBatch,
  isArtSportsBatch,
  isArtSportsProfile
};
