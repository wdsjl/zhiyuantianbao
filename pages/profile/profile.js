const { request } = require('../../utils/request');

Page({
  data: {
    form: {
      role: '学生',
      name: '',
      phone: '',
      province: '',
      city: '',
      school: '',
      grade: '高三',
      className: '',
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
  onLoad() {
    const stored = wx.getStorageSync('studentProfile');
    const loginUser = wx.getStorageSync('loginUser') || {};
    if (stored) {
      this.setData({
        form: {
          ...this.data.form,
          ...stored,
          openid: stored.openid || loginUser.openid,
          userId: stored.userId || loginUser.user_id
        }
      });
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
  buildLocalOpenid(form) {
    const loginUser = wx.getStorageSync('loginUser') || {};
    return form.openid || loginUser.openid || `local_${form.phone || form.name || 'student'}`;
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
        school_name: form.school,
        grade: form.grade,
        class_name: form.className,
        exam_year: new Date().getFullYear(),
        exam_type: '普通类',
        subject_combination: form.subjectCombination,
        score: Number(form.score),
        rank: Number(form.rank),
        target_batch: form.targetBatch
      }
    })
      .then((res) => {
        const saved = {
          ...form,
          openid: res.openid || openid,
          userId: res.user_id,
          studentId: res.student_id
        };
        const loginUser = wx.getStorageSync('loginUser') || {};
        wx.setStorageSync('loginUser', { ...loginUser, openid: saved.openid, user_id: saved.userId, has_profile: true });
        wx.setStorageSync('studentProfile', saved);
        wx.setStorageSync('currentRole', form.role);
        const finish = () => {
          wx.showToast({ title: '保存成功', icon: 'success' });
          setTimeout(() => {
            wx.switchTab({ url: '/pages/home/home' });
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
              wx.showToast({ title: error.message || '家长绑定失败', icon: 'none' });
            });
          return;
        }
        finish();
      })
      .catch((error) => {
        wx.showToast({ title: error.message || '档案保存失败', icon: 'none' });
      });
  }
});
