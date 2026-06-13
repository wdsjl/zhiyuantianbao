const { request, formatRequestError } = require('../../utils/request');
const {
  SUBJECT_COMBINATIONS,
  TARGET_BATCHES,
  findOptionIndex,
  normalizeSubjectCombination
} = require('../../utils/profileOptions');
const { getBatchMismatchWarning } = require('../../utils/batchHint');

Page({
  data: {
    subjectOptions: SUBJECT_COMBINATIONS,
    targetBatchOptions: TARGET_BATCHES,
    subjectIndex: -1,
    targetBatchIndex: -1,
    batchDataSummary: '',
    batchWarning: '',
    form: {
      role: '学生',
      name: '',
      phone: '',
      province: '',
      city: '',
      subjectCombination: '',
      score: '',
      rank: '',
      targetBatch: '',
      bindCode: '',
      studentId: '',
      userId: '',
      openid: ''
    }
  },
  syncPickerIndices(form) {
    const subjectIndex = findOptionIndex(SUBJECT_COMBINATIONS, form.subjectCombination);
    const targetBatchIndex = findOptionIndex(TARGET_BATCHES, form.targetBatch);
    this.setData({
      subjectIndex: subjectIndex >= 0 ? subjectIndex : 0,
      targetBatchIndex: targetBatchIndex >= 0 ? targetBatchIndex : 0,
      'form.subjectCombination': subjectIndex >= 0 ? SUBJECT_COMBINATIONS[subjectIndex] : form.subjectCombination
    });
  },
  onLoad() {
    const stored = wx.getStorageSync('studentProfile');
    const loginUser = wx.getStorageSync('loginUser') || {};
    if (stored) {
      const form = {
        ...this.data.form,
        ...stored,
        subjectCombination: normalizeSubjectCombination(stored.subjectCombination) || stored.subjectCombination || '',
        openid: stored.openid || loginUser.openid,
        userId: stored.userId || loginUser.user_id
      };
      this.setData({ form });
      this.syncPickerIndices(form);
      this.refreshBatchHints(form);
      return;
    }
    if (loginUser.openid) {
      this.setData({ 'form.openid': loginUser.openid, 'form.userId': loginUser.user_id });
    }
  },
  selectRole(event) {
    this.setData({ 'form.role': event.currentTarget.dataset.role });
  },
  onInput(event) {
    const field = event.currentTarget.dataset.field;
    const form = { ...this.data.form, [field]: event.detail.value };
    this.setData({ [`form.${field}`]: event.detail.value });
    if (field === 'province' || field === 'score' || field === 'rank') {
      this.refreshBatchHints(form);
    } else if (field === 'targetBatch') {
      this.updateBatchWarning(form, this.data.availableBatches || []);
    }
  },
  refreshBatchHints(form) {
    const province = (form && form.province) || '';
    if (!province.trim()) {
      this.setData({ batchDataSummary: '', batchWarning: '', availableBatches: [] });
      return;
    }
    request({ url: '/api/admission-data/batches', data: { province } })
      .then((res) => {
        const batches = res.batches || [];
        const summary = batches.length
          ? batches.slice(0, 4).map((item) => `${item.batch}(${item.school_major_count || item.record_count || 0}条)`).join('、')
          : '暂无录取数据';
        this.setData({
          availableBatches: batches,
          batchDataSummary: `库内批次：${summary}`,
          batchWarning: getBatchMismatchWarning(form, batches)
        });
      })
      .catch(() => {
        this.setData({
          availableBatches: [],
          batchDataSummary: '',
          batchWarning: getBatchMismatchWarning(form, [])
        });
      });
  },
  updateBatchWarning(form, availableBatches) {
    this.setData({ batchWarning: getBatchMismatchWarning(form, availableBatches) });
  },
  onSubjectChange(event) {
    const index = Number(event.detail.value);
    this.setData({
      subjectIndex: index,
      'form.subjectCombination': SUBJECT_COMBINATIONS[index]
    });
  },
  onTargetBatchChange(event) {
    const index = Number(event.detail.value);
    const form = { ...this.data.form, targetBatch: TARGET_BATCHES[index] };
    this.setData({
      targetBatchIndex: index,
      'form.targetBatch': TARGET_BATCHES[index]
    });
    this.updateBatchWarning(form, this.data.availableBatches || []);
  },
  isTempOpenid(openid) {
    return !openid || openid.startsWith('dev_') || openid.startsWith('local_') || openid.startsWith('test_');
  },
  buildLocalOpenid(form) {
    const loginUser = wx.getStorageSync('loginUser') || {};
    const candidates = [loginUser.openid, form.openid].filter(Boolean);
    const realOpenid = candidates.find((id) => !this.isTempOpenid(id));
    if (realOpenid) return realOpenid;
    if (candidates.length) return candidates[0];
    return `local_${form.phone || form.name || 'student'}`;
  },
  showSaveError(message) {
    wx.showModal({
      title: '档案保存失败',
      content: message || '请稍后重试',
      showCancel: false
    });
  },
  finishSave(saved) {
    const { form } = this.data;
    const loginUser = wx.getStorageSync('loginUser') || {};
    wx.setStorageSync('loginUser', { ...loginUser, openid: saved.openid, user_id: saved.userId, has_profile: true });
    wx.setStorageSync('studentProfile', saved);
    wx.setStorageSync('currentRole', form.role);
    const finish = () => {
      wx.showToast({ title: '保存成功', icon: 'success' });
      setTimeout(() => {
        wx.showModal({
          title: '档案已保存',
          content: '下一步建议完成霍兰德职业兴趣测评，系统才能生成更准确的个性化报告。',
          confirmText: '去测评',
          cancelText: '回首页',
          success: (modalRes) => {
            if (modalRes.confirm) {
              wx.navigateTo({ url: '/pages/personality/personality' });
              return;
            }
            wx.switchTab({ url: '/pages/home/home' });
          }
        });
      }, 500);
    };
    if (form.role === '家长' && form.bindCode && saved.userId) {
      request({
        url: '/api/parent-bind',
        method: 'POST',
        data: {
          parent_user_id: Number(saved.userId),
          student_phone: form.bindCode,
          bind_code: form.bindCode
        }
      })
        .then((bindRes) => {
          wx.setStorageSync('boundStudent', bindRes);
          finish();
        })
        .catch((error) => {
          this.showSaveError(formatRequestError(error) || '家长绑定失败');
        });
      return;
    }
    finish();
  },
  saveProfile() {
    const { form } = this.data;
    const required = ['role', 'province', 'subjectCombination', 'score', 'rank', 'targetBatch'];
    const missing = required.some((field) => !form[field]);
    if (missing) {
      wx.showToast({ title: '请完善必填信息', icon: 'none' });
      return;
    }
    if (form.role === '家长' && !form.bindCode) {
      wx.showToast({ title: '请先绑定学生', icon: 'none' });
      return;
    }
    const score = Number(form.score);
    const rank = Number(form.rank);
    if (!Number.isFinite(score) || !Number.isFinite(rank)) {
      wx.showToast({ title: '分数和位次需为有效数字', icon: 'none' });
      return;
    }

    const batchWarning = getBatchMismatchWarning(form, this.data.availableBatches || []);
    if (batchWarning) {
      wx.showModal({
        title: '批次可能不匹配',
        content: `${batchWarning}\n\n是否仍按当前批次保存？`,
        confirmText: '继续保存',
        cancelText: '返回修改',
        success: (res) => {
          if (res.confirm) this.submitProfile(form, score, rank);
        }
      });
      return;
    }

    this.submitProfile(form, score, rank);
  },
  submitProfile(form, score, rank) {
    const openid = this.buildLocalOpenid(form);
    request({
      url: '/api/profile',
      method: 'POST',
      data: {
        openid,
        phone: form.phone,
        role: form.role,
        name: form.name,
        province: form.province,
        city: form.city,
        exam_year: new Date().getFullYear(),
        exam_type: '普通类',
        subject_combination: form.subjectCombination,
        score,
        rank,
        target_batch: form.targetBatch
      }
    })
      .then((res) => {
        this.finishSave({
          ...form,
          openid: res.openid || openid,
          userId: res.user_id,
          studentId: res.student_id
        });
      })
      .catch((error) => {
        const message = formatRequestError(error);
        const isNetworkError = error && error.errMsg && error.errMsg.includes('request:fail');
        if (isNetworkError) {
          const saved = {
            ...form,
            openid,
            userId: form.userId || '',
            studentId: form.studentId || ''
          };
          wx.setStorageSync('studentProfile', saved);
          wx.showModal({
            title: '后端未连接',
            content: '档案已暂存到本地。请在服务器执行 pm2 restart zhiyuan-backend 后重新保存，以写入数据库。',
            showCancel: false
          });
          return;
        }
        this.showSaveError(message || '档案保存失败');
      });
  },
});
