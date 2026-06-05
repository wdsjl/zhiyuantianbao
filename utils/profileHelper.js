const { request } = require('./request');

function mapBoundStudent(bound, stored) {
  return {
    ...stored,
    studentId: bound.student_id,
    name: bound.name || bound.student_name,
    studentName: bound.name || bound.student_name,
    province: bound.province || stored.province,
    school: bound.school_name || stored.school,
    className: bound.class_name || stored.className,
    score: bound.score,
    rank: bound.rank,
    targetBatch: bound.target_batch || stored.targetBatch,
    subjectCombination: stored.subjectCombination,
    isParentView: true
  };
}

function loadActiveProfileSync() {
  const stored = wx.getStorageSync('studentProfile') || {};
  const role = stored.role || wx.getStorageSync('currentRole');
  if (role === '家长') {
    const bound = wx.getStorageSync('boundStudent');
    if (bound && (bound.student_id || bound.studentId)) {
      return mapBoundStudent(bound, stored);
    }
  }
  return stored;
}

function refreshActiveProfile() {
  const stored = wx.getStorageSync('studentProfile') || {};
  const role = stored.role || wx.getStorageSync('currentRole');
  if (role !== '家长' || !stored.userId) {
    return Promise.resolve(stored);
  }
  return request({ url: '/api/parent-bind', data: { parent_user_id: Number(stored.userId) } })
    .then((res) => {
      const bound = (res.list || [])[0];
      if (!bound) return stored;
      wx.setStorageSync('boundStudent', bound);
      const profile = mapBoundStudent(bound, stored);
      return profile;
    })
    .catch(() => stored);
}

module.exports = {
  loadActiveProfileSync,
  refreshActiveProfile
};
