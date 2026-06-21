const { isArtSportsActive, inferExamTypeFromBatch } = require('./henanArtSports');

function splitText(value) {
  if (!value || !String(value).trim()) return [];
  return String(value)
    .split(/[,，、;；\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildPreferencesPayload(form) {
  if (!form) return null;
  return {
    preferredCities: splitText(form.preferredCitiesText),
    preferredMajorTypes: splitText(form.preferredMajorTypesText),
    preferredMajors: splitText(form.preferredMajorsText),
    avoidDirections: splitText(form.avoidDirectionsText),
    schoolLevelPreference: form.schoolLevelPreference || '',
    schoolNaturePreference: form.schoolNaturePreference || '',
    tuitionBudget: form.tuitionBudget || '',
    careerGoal: form.careerGoal || '',
    acceptAdjustment: form.acceptAdjustment || '',
    otherNotes: form.otherNotes || ''
  };
}

function loadStoredPreferences() {
  return wx.getStorageSync('studentPreferences') || {};
}

function buildRecommendPayload(profile, options) {
  const opts = options || {};
  const prefs = buildPreferencesPayload(opts.preferences || loadStoredPreferences());
  const personality = opts.personality || wx.getStorageSync('personalityResult') || {};
  const majorTypes = (personality.majorTypes || []);
  const payload = {
    province: profile.province,
    batch: isArtSportsActive(profile) ? resolveArtSportsTargetBatch(profile) : profile.targetBatch,
    score: Number(profile.score),
    rank: Number(profile.rank),
    subject_combination: profile.subjectCombination,
    cities: prefs ? prefs.preferredCities : [],
    major_types: opts.hardFilterMajorTypes ? majorTypes : [],
    preferences: prefs,
    personality_major_types: majorTypes,
    accept_adjustment: true,
    plan_style: opts.planStyle || wx.getStorageSync('volunteerPlanStyle') || 'balanced',
    volunteer_count: opts.volunteerCount || 0
  };
  if (isArtSportsActive(profile)) {
    const resolvedExamType = inferExamTypeFromBatch(profile.targetBatch, profile.examType || profile.exam_type);
    payload.exam_type = resolvedExamType;
    payload.professional_score = Number(profile.professionalScore || profile.professional_score || 0);
    payload.art_sports_formula_id = Number(profile.formulaId || profile.art_sports_formula_id || 0) || null;
    payload.waive_art_sports_batch = false;
    payload.culture_cutoff = profile.cultureCutoff || profile.culture_cutoff || null;
    payload.pro_cutoff = profile.proCutoff || profile.pro_cutoff || null;
  } else {
    payload.exam_type = profile.examType || profile.exam_type || '普通类';
    payload.waive_art_sports_batch = !!(profile.waiveArtSports || profile.waive_art_sports_batch);
  }
  return payload;
}

module.exports = {
  splitText,
  buildPreferencesPayload,
  loadStoredPreferences,
  buildRecommendPayload
};
