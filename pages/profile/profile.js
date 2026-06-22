const { request, formatRequestError } = require('../../utils/request');
const {
  SUBJECT_COMBINATIONS,
  TARGET_BATCHES,
  EXAM_TYPES,
  getTargetBatchesForExamType,
  findOptionIndex,
  normalizeSubjectCombination
} = require('../../utils/profileOptions');
const { getBatchMismatchWarning, isArtSportsProfile, isArtSportsBatch } = require('../../utils/batchHint');
const { buildProfileSnapshot, clearDerivedArtifacts } = require('../../utils/profileSnapshot');
const { isHenanArtSportsProvince, defaultFormulaId, isArtSportsActive, buildFormulaPickerData } = require('../../utils/henanArtSports');

Page({
  data: {
    subjectOptions: SUBJECT_COMBINATIONS,
    examTypeOptions: EXAM_TYPES,
    targetBatchOptions: TARGET_BATCHES,
    subjectIndex: -1,
    targetBatchIndex: -1,
    examTypeIndex: 0,
    showArtSportsFields: false,
    isHenan: false,
    trackLabel: '',
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
      examType: '普通类',
      professionalScore: '',
      cultureCutoff: '',
      proCutoff: '',
    formulaId: 5,
    waiveArtSports: false,
    formulaOptions: [],
    formulaHints: [],
      bindCode: '',
      studentId: '',
      userId: '',
      openid: ''
    }
  },
  applyExamType(examType, form) {
    const batches = getTargetBatchesForExamType(examType);
    const isArtSports = examType === '艺术类' || examType === '体育类';
    const formulaId = isArtSports ? defaultFormulaId(examType, '本科') : 5;
    const nextForm = {
      ...form,
      examType,
      targetBatch: batches.includes(form.targetBatch) ? form.targetBatch : batches[0],
      formulaId: form.formulaId || formulaId,
      waiveArtSports: isArtSports ? false : !!form.waiveArtSports
    };
    const examTypeIndex = Math.max(0, EXAM_TYPES.indexOf(examType));
    const targetBatchIndex = findOptionIndex(batches, nextForm.targetBatch);
    this.setData({
      targetBatchOptions: batches,
      showArtSportsFields: isArtSports,
      examTypeIndex,
      targetBatchIndex: targetBatchIndex >= 0 ? targetBatchIndex : 0,
      'form.examType': examType,
      'form.targetBatch': nextForm.targetBatch,
      'form.formulaId': nextForm.formulaId,
      'form.waiveArtSports': nextForm.waiveArtSports
    });
  },
  syncPickerIndices(form) {
    const subjectIndex = findOptionIndex(SUBJECT_COMBINATIONS, form.subjectCombination);
    const batches = this.data.targetBatchOptions || TARGET_BATCHES;
    const targetBatchIndex = findOptionIndex(batches, form.targetBatch);
    this.setData({
      subjectIndex: subjectIndex >= 0 ? subjectIndex : 0,
      targetBatchIndex: targetBatchIndex >= 0 ? targetBatchIndex : 0,
      'form.subjectCombination': subjectIndex >= 0 ? SUBJECT_COMBINATIONS[subjectIndex] : form.subjectCombination
    });
  },
  onLoad(options) {
    const track = (options && options.track) || '';
    const stored = wx.getStorageSync('studentProfile');
    const loginUser = wx.getStorageSync('loginUser') || {};
    let trackExamType = '';
    let trackLabel = '';
    if (track === 'art') {
      trackExamType = '艺术类';
      trackLabel = '艺术报考';
    } else if (track === 'sports') {
      trackExamType = '体育类';
      trackLabel = '体育报考';
    }
    if (stored) {
      const form = {
        ...this.data.form,
        ...stored,
        examType: stored.examType || trackExamType || stored.exam_type || '普通类',
        professionalScore: stored.professionalScore || stored.professional_score || '',
        cultureCutoff: stored.cultureCutoff || stored.culture_cutoff || '',
        proCutoff: stored.proCutoff || stored.pro_cutoff || '',
        formulaId: stored.formulaId || stored.art_sports_formula_id || 5,
        waiveArtSports: !!(stored.waiveArtSports || stored.waive_art_sports_batch),
        subjectCombination: normalizeSubjectCombination(stored.subjectCombination) || stored.subjectCombination || '',
        openid: stored.openid || loginUser.openid,
        userId: stored.userId || loginUser.user_id
      };
      if (trackExamType) form.examType = trackExamType;
      if (!form.province) form.province = '河南';
      this.setData({ form, isHenan: isHenanArtSportsProvince(form.province), trackLabel });
      this.applyExamType(form.examType, form);
      this.loadFormulaOptions(form.examType);
      this.syncPickerIndices(form);
      this.refreshBatchHints(form);
      return;
    }
    const form = { ...this.data.form, openid: loginUser.openid, userId: loginUser.user_id };
    if (trackExamType) {
      form.examType = trackExamType;
      form.province = '河南';
    }
    this.setData({ form, isHenan: isHenanArtSportsProvince(form.province), trackLabel });
    if (trackExamType) this.applyExamType(trackExamType, form);
    if (trackExamType) this.loadFormulaOptions(trackExamType);
  },
  loadFormulaOptions(examType) {
    if (examType !== '艺术类' && examType !== '体育类') {
      this.setData({ formulaOptions: [], formulaHints: [] });
      return;
    }
    request({ url: '/api/henan-art-sports/meta' })
      .then((meta) => {
        const list = examType === '体育类' ? (meta.sports_formulas || []) : (meta.art_formulas || []);
        const picker = buildFormulaPickerData(list);
        this.setData({
          formulaOptions: picker.formulaOptions,
          formulaHints: picker.formulaHints
        });
      })
      .catch(() => {});
  },
  onFormulaChange(event) {
    this.setData({ 'form.formulaId': Number(event.detail.value) + 1 });
  },
  selectRole(event) {
    this.setData({ 'form.role': event.currentTarget.dataset.role });
  },
  onInput(event) {
    const field = event.currentTarget.dataset.field;
    const form = { ...this.data.form, [field]: event.detail.value };
    this.setData({ [`form.${field}`]: event.detail.value });
    if (field === 'province') {
      this.setData({ isHenan: isHenanArtSportsProvince(event.detail.value) });
    }
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
        const artSports = isArtSportsProfile(form) && isArtSportsBatch(form.targetBatch);
        const summary = artSports
          ? '艺体志愿按综合分对标生成；可在后台「录取数据导入」上传艺考/体育批次以扩充院校池。'
          : (batches.length
            ? batches.slice(0, 4).map((item) => `${item.batch}(${item.school_major_count || item.record_count || 0}条)`).join('、')
            : '暂无录取数据');
        this.setData({
          availableBatches: batches,
          batchDataSummary: artSports ? summary : `库内批次：${summary}`,
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
    const batch = this.data.targetBatchOptions[index];
    let form = { ...this.data.form, targetBatch: batch };
    if (batch.includes('艺术') && form.examType !== '艺术类') {
      this.applyExamType('艺术类', form);
      this.loadFormulaOptions('艺术类');
      this.updateBatchWarning({ ...form, examType: '艺术类' }, this.data.availableBatches || []);
      return;
    }
    if (batch.includes('体育') && form.examType !== '体育类') {
      this.applyExamType('体育类', form);
      this.loadFormulaOptions('体育类');
      this.updateBatchWarning({ ...form, examType: '体育类' }, this.data.availableBatches || []);
      return;
    }
    this.setData({
      targetBatchIndex: index,
      'form.targetBatch': batch
    });
    this.updateBatchWarning(form, this.data.availableBatches || []);
  },
  onExamTypeChange(event) {
    const index = Number(event.detail.value);
    const examType = EXAM_TYPES[index];
    const form = { ...this.data.form, examType };
    this.applyExamType(examType, form);
    this.loadFormulaOptions(examType);
    this.updateBatchWarning(form, this.data.availableBatches || []);
  },
  onWaiveArtSportsChange(event) {
    const checked = event.detail.value.length > 0;
    this.setData({ 'form.waiveArtSports': checked });
    this.updateBatchWarning(this.data.form, this.data.availableBatches || []);
    if (checked && (this.data.form.examType === '艺术类' || this.data.form.examType === '体育类')) {
      wx.showToast({ title: '将按普通类48志愿生成', icon: 'none', duration: 2500 });
    }
  },
  goArtSportsZone(event) {
    const track = (event && event.currentTarget && event.currentTarget.dataset.track)
      || (this.data.form.examType === '体育类' ? 'sports' : 'art');
    const url = track === 'sports' ? '/pages/sports-zone/sports-zone' : '/pages/art-zone/art-zone';
    wx.navigateTo({ url });
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
    const previousProfile = wx.getStorageSync('studentProfile') || {};
    const profileChanged = Boolean(
      previousProfile.score
      && previousProfile.rank
      && buildProfileSnapshot(previousProfile) !== buildProfileSnapshot(saved)
    );
    if (profileChanged) {
      clearDerivedArtifacts();
    }
    wx.setStorageSync('loginUser', { ...loginUser, openid: saved.openid, user_id: saved.userId, has_profile: true });
    wx.setStorageSync('studentProfile', saved);
    wx.setStorageSync('currentRole', form.role);
    const finish = () => {
      wx.showToast({ title: '保存成功', icon: 'success' });
      setTimeout(() => {
        const nextHint = profileChanged
          ? '分数或位次已更新，之前的检索结果和志愿方案已清空。请先查看「可报院校」，再智能生成最终志愿。'
          : '下一步可检索所有可报院校专业，再完成测评与智能填报。';
        wx.showModal({
          title: profileChanged ? '档案已更新' : '档案已保存',
          content: nextHint,
          confirmText: profileChanged ? '查看可报院校' : '去检索',
          cancelText: '回首页',
          success: (modalRes) => {
            const examType = saved.examType || '普通类';
            if (modalRes.confirm) {
              if (examType === '艺术类' && !saved.waiveArtSports) {
                wx.navigateTo({ url: '/pages/art-zone/art-zone' });
                return;
              }
              if (examType === '体育类' && !saved.waiveArtSports) {
                wx.navigateTo({ url: '/pages/sports-zone/sports-zone' });
                return;
              }
              wx.navigateTo({ url: '/pages/eligible-pool/eligible-pool' });
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
    const artSportsActive = isArtSportsActive({ ...form, province: form.province });
    const required = ['role', 'province', 'subjectCombination', 'score', 'targetBatch'];
    if (!artSportsActive) required.push('rank');
    const missing = required.some((field) => !form[field] && form[field] !== 0);
    if (missing) {
      wx.showToast({ title: '请完善必填信息', icon: 'none' });
      return;
    }
    if (form.role === '家长' && !form.bindCode) {
      wx.showToast({ title: '请先绑定学生', icon: 'none' });
      return;
    }
    const score = Number(form.score);
    const rank = artSportsActive ? Number(form.rank || 0) : Number(form.rank);
    if (!Number.isFinite(score) || (!artSportsActive && !Number.isFinite(rank))) {
      wx.showToast({ title: artSportsActive ? '分数需为有效数字' : '分数和位次需为有效数字', icon: 'none' });
      return;
    }

    if (form.examType !== '普通类' && !form.waiveArtSports && !form.professionalScore) {
      wx.showToast({ title: '请填写专业统考分', icon: 'none' });
      return;
    }

    const openid = this.buildLocalOpenid(form);
    const payload = {
      openid,
      phone: form.phone,
      role: form.role,
      name: form.name,
      province: form.province,
      city: form.city,
      exam_year: new Date().getFullYear(),
      exam_type: form.examType || '普通类',
      subject_combination: form.subjectCombination,
      score,
      rank,
      target_batch: form.targetBatch,
      professional_score: form.professionalScore ? Number(form.professionalScore) : null,
      art_sports_formula_id: form.formulaId ? Number(form.formulaId) : null,
      waive_art_sports_batch: !!form.waiveArtSports,
      culture_cutoff: form.cultureCutoff ? Number(form.cultureCutoff) : null,
      pro_cutoff: form.proCutoff ? Number(form.proCutoff) : null
    };
    request({
      url: '/api/profile',
      method: 'POST',
      data: payload
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
  }
});
