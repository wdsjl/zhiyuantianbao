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
  return String(province || '').replace(/\s/g, '') === '河南';
}

module.exports = {
  ART_FORMULAS,
  SPORTS_FORMULAS,
  PRO_MAX,
  defaultFormulaId,
  calcComposite,
  checkDualLine,
  isHenanArtSportsProvince
};
