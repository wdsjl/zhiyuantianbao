const { request } = require('../../utils/request');

Page({
  data: {
    meta: null,
    form: {
      cultureScore: '',
      professionalScore: '',
      cultureCutoff: '',
      proCutoff: '',
      batchLevel: '本科',
      formulaId: 3,
      waive: false
    },
    batchLevels: ['本科', '专科'],
    formulaOptions: [],
    result: null,
    matchResult: null,
    loading: false
  },
  onLoad() {
    this.loadMeta();
    const profile = wx.getStorageSync('studentProfile') || {};
    const patch = {};
    if (profile.score) patch['form.cultureScore'] = String(profile.score);
    if (profile.professionalScore || profile.professional_score) {
      patch['form.professionalScore'] = String(profile.professionalScore || profile.professional_score);
    }
    if (profile.cultureCutoff || profile.culture_cutoff) {
      patch['form.cultureCutoff'] = String(profile.cultureCutoff || profile.culture_cutoff);
    }
    if (profile.proCutoff || profile.pro_cutoff) {
      patch['form.proCutoff'] = String(profile.proCutoff || profile.pro_cutoff);
    }
    if (profile.formulaId || profile.art_sports_formula_id) {
      patch['form.formulaId'] = Number(profile.formulaId || profile.art_sports_formula_id) || 3;
    }
    if (Object.keys(patch).length) this.setData(patch);
  },
  loadMeta() {
    request({ url: '/api/henan-art-sports/meta' })
      .then((meta) => {
        this.setData({
          meta,
          formulaOptions: (meta.sports_formulas || []).map((item) => `${item.id}. ${item.label}`)
        });
      })
      .catch(() => wx.showToast({ title: '规则加载失败', icon: 'none' }));
  },
  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
  },
  onBatchChange(e) {
    const batchLevel = this.data.batchLevels[Number(e.detail.value)];
    const formulaId = 3;
    this.setData({ 'form.batchLevel': batchLevel, 'form.formulaId': formulaId });
  },
  onFormulaChange(e) {
    this.setData({ 'form.formulaId': Number(e.detail.value) + 1 });
  },
  onWaiveChange(e) {
    this.setData({ 'form.waive': e.detail.value.length > 0 });
  },
  calc() {
    const f = this.data.form;
    this.setData({ loading: true, result: null, matchResult: null });
    request({
      url: '/api/henan-art-sports/calculate',
      method: 'POST',
      data: {
        category: '体育类',
        culture_score: Number(f.cultureScore),
        professional_score: Number(f.professionalScore),
        formula_id: Number(f.formulaId),
        batch_level: f.batchLevel,
        culture_cutoff: f.cultureCutoff ? Number(f.cultureCutoff) : null,
        pro_cutoff: f.proCutoff ? Number(f.proCutoff) : null,
        waive_art_sports_batch: f.waive
      }
    })
      .then((result) => this.setData({ result }))
      .catch((err) => wx.showToast({ title: (err && err.message) || '计算失败', icon: 'none' }))
      .finally(() => this.setData({ loading: false }));
  },
  match() {
    const f = this.data.form;
    this.setData({ loading: true, matchResult: null });
    request({
      url: '/api/henan-art-sports/match',
      method: 'POST',
      data: {
        category: '体育类',
        culture_score: Number(f.cultureScore),
        professional_score: Number(f.professionalScore),
        formula_id: Number(f.formulaId),
        batch_level: f.batchLevel,
        culture_cutoff: f.cultureCutoff ? Number(f.cultureCutoff) : null,
        pro_cutoff: f.proCutoff ? Number(f.proCutoff) : null,
        waive_art_sports_batch: f.waive
      }
    })
      .then((matchResult) => this.setData({ matchResult, result: matchResult }))
      .catch((err) => wx.showToast({ title: (err && err.message) || '匹配失败', icon: 'none' }))
      .finally(() => this.setData({ loading: false }));
  },
  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile?track=sports' });
  },
  goEligiblePool() {
    wx.navigateTo({ url: '/pages/eligible-pool/eligible-pool' });
  },
  goVolunteer() {
    wx.switchTab({ url: '/pages/volunteer/volunteer' });
  }
});
