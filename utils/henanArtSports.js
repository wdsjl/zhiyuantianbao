/** 河南艺体综合分公式（与 server/henan_art_sports_service.py 一致） */
const ART_FORMULAS = {
  1: (w, z) => w,
  2: (w, z) => 0.8 * w + 0.5 * z,
  3: (w, z) => 0.7 * w + 0.75 * z,
  4: (w, z) => 0.6 * w + z,
  5: (w, z) => 0.5 * w + 1.25 * z
};

const SPORTS_FORMULAS = {
  1: (w, t) => w,
  2: (w, t) => 0.3 * w + 3.5 * t,
  3: (w, t) => 0.5 * w + 2.5 * t,
  4: (w, t) => 0.7 * w + 1.5 * t,
  5: (w, t) => 5 * t
};

const PRO_MAX = { 艺术类: 300, 体育类: 150 };

function defaultFormulaId(category, batchLevel) {
  if (category === '艺术类') return 5;
  if (category === '体育类') return 3;
  return 5;
}

function calcComposite(category, cultureScore, proScore, formulaId) {
  const w = Number(cultureScore) || 0;
  const p = Number(proScore) || 0;
  const fid = Number(formulaId) || defaultFormulaId(category, '本科');
  const fn = category === '体育类' ? SPORTS_FORMULAS[fid] : ART_FORMULAS[fid];
  if (!fn) return 0;
  return Math.round(fn(w, p) * 100) / 100;
}

function checkDualLine(cultureScore, proScore, cultureCutoff, proCutoff) {
  const cultureOk = cultureCutoff == null || cultureCutoff === '' || Number(cultureScore) >= Number(cultureCutoff);
  const proOk = proCutoff == null || proCutoff === '' || Number(proScore) >= Number(proCutoff);
  return {
    culture_ok: cultureOk,
    pro_ok: proOk,
    dual_line_ok: cultureOk && proOk
  };
}

function isHenanArtSportsProvince(province) {
  return String(province || '').replace(/\s/g, '').replace(/省$/, '') === '河南';
}

function getExamType(profile) {
  if (!profile) return '普通类';
  return profile.examType || profile.exam_type || '普通类';
}

function isWaivedArtSports(profile) {
  return !!(profile && (profile.waiveArtSports || profile.waive_art_sports_batch));
}

function inferExamTypeFromBatch(batch, examType) {
  const type = examType || '普通类';
  const text = String(batch || '');
  if (type === '艺术类' || type === '体育类') return type;
  if (text.includes('艺术')) return '艺术类';
  if (text.includes('体育')) return '体育类';
  return type;
}

function isArtSportsActive(profile) {
  if (!profile || !isHenanArtSportsProvince(profile.province)) return false;
  if (isWaivedArtSports(profile)) return false;
  const examType = inferExamTypeFromBatch(
    profile.targetBatch || profile.target_batch,
    getExamType(profile)
  );
  return examType === '艺术类' || examType === '体育类';
}

function batchLevelFromTargetBatch(targetBatch) {
  return String(targetBatch || '').includes('专科') ? '专科' : '本科';
}

function categoryFromExamType(examType) {
  if (examType === '体育类') return '体育类';
  if (examType === '艺术类') return '艺术类';
  return '';
}

function resolveArtSportsTargetBatch(profile) {
  const examType = inferExamTypeFromBatch(
    profile.targetBatch || profile.target_batch,
    getExamType(profile)
  );
  const batch = String(profile.targetBatch || profile.target_batch || '');
  if (examType === '艺术类') {
    if (batch.includes('艺术')) return batch;
    return batch.includes('专科') ? '艺术专科批' : '艺术本科批';
  }
  if (examType === '体育类') {
    if (batch.includes('体育')) return batch;
    return batch.includes('专科') ? '体育专科批' : '体育本科批';
  }
  return batch;
}

module.exports = {
  ART_FORMULAS,
  SPORTS_FORMULAS,
  PRO_MAX,
  defaultFormulaId,
  calcComposite,
  checkDualLine,
  isHenanArtSportsProvince,
  getExamType,
  isWaivedArtSports,
  isArtSportsActive,
  inferExamTypeFromBatch,
  batchLevelFromTargetBatch,
  categoryFromExamType,
  inferExamTypeFromBatch,
  resolveArtSportsTargetBatch
};
