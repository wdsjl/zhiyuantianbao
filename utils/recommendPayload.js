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
  return {
    province: profile.province,
    batch: profile.targetBatch,
    score: Number(profile.score),
    rank: Number(profile.rank),
    subject_combination: profile.subjectCombination,
    cities: prefs ? prefs.preferredCities : [],
    major_types: opts.hardFilterMajorTypes ? majorTypes : [],
    preferences: prefs,
    personality_major_types: majorTypes,
    accept_adjustment: true,
    plan_style: opts.planStyle || wx.getStorageSync('volunteerPlanStyle') || 'balanced',
    volunteer_count: opts.volunteerCount || 9
  };
}

module.exports = {
  splitText,
  buildPreferencesPayload,
  loadStoredPreferences,
  buildRecommendPayload
};
