const { request, formatRequestError } = require('../../utils/request');

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
          wx.showToast({ title: formatRequestError(error) || '家长绑定失败', icon: 'none', duration: 3000 });
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
        school_name: form.school,
        grade: form.grade,
        class_name: form.className,
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
        wx.showToast({ title: message || '档案保存失败', icon: 'none', duration: 3000 });
      });
  }
});
