const { request, formatRequestError } = require('../../utils/request');
const {
  SUBJECT_COMBINATIONS,
  TARGET_BATCHES,
  findOptionIndex,
  normalizeSubjectCombination
} = require('../../utils/profileOptions');

Page({
  data: {
    subjectOptions: SUBJECT_COMBINATIONS,
    targetBatchOptions: TARGET_BATCHES,
    subjectIndex: -1,
    targetBatchIndex: -1,
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
    this.setData({ [`form.${field}`]: event.detail.value });
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
    this.setData({
      targetBatchIndex: index,
      'form.targetBatch': TARGET_BATCHES[index]
    });
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
          const { BASE_URL } = require('../../utils/request');
          const domainHint = (error.errMsg || '').includes('domain list')
            ? '请在微信公众平台 → 开发管理 → 开发设置 → 服务器域名，request 合法域名填写：https://api.zntb.lhyun.net（须带 https://，末尾不要加分号）。'
            : `请确认小程序已更新代码（接口 ${BASE_URL}），服务器 pm2 status 中 zhiyuan-backend 为 online，并在浏览器打开 ${BASE_URL}/health 应显示 {"status":"ok"}。`;
          wx.showModal({
            title: '无法连接后端',
            content: `档案已暂存到本地。\n\n${domainHint}\n\n技术信息：${message}`,
            showCancel: false
          });
          return;
        }
        this.showSaveError(message || '档案保存失败');
      });
  }
});
