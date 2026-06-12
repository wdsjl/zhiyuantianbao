const { request } = require('../../utils/request');
const { loadActiveProfileSync } = require('../../utils/profileHelper');
const { requirePermission } = require('../../utils/membership');
const { openAnnouncement } = require('../../utils/announcement');

Page({
  data: {
    schoolId: 0,
    school: null,
    plans: [],
    announcements: [],
    loading: false
  },
  onLoad(options) {
    const schoolId = Number(options.id || options.schoolId);
    if (!schoolId) {
      wx.showToast({ title: '院校参数无效', icon: 'none' });
      return;
    }
    this.setData({ schoolId });
    this.fetchSchoolDetail();
  },
  fetchSchoolDetail() {
    const profile = loadActiveProfileSync();
    this.setData({ loading: true });
    Promise.all([
      request({ url: `/api/schools/${this.data.schoolId}` }),
      request({
        url: '/api/admissions',
        data: {
          school_id: this.data.schoolId,
          province: profile.province || '',
          limit: 200
        }
      })
    ])
      .then(([schoolRes, admissionRes]) => {
        const school = schoolRes.school || null;
        if (school && school.school_name) {
          request({
            url: '/api/announcements',
            data: {
              school_name: school.school_name,
              province: profile.province || '河南',
              year: 2026,
              review_status: 'approved',
              limit: 20
            }
          })
            .then((announcementRes) => {
              this.setData({ announcements: announcementRes.list || [] });
            })
            .catch(() => {});
        }
        const plans = (schoolRes.plans || []).map((plan, index) => ({
          ...plan,
          planKey: `${plan.major_id}-${plan.year}-${index}`
        }));
        const admissionMap = {};
        (admissionRes.list || []).forEach((item) => {
          const key = `${item.major_id}-${item.year}`;
          if (!admissionMap[key]) admissionMap[key] = item;
        });
        const mergedPlans = plans.map((plan) => {
          const admission = admissionMap[`${plan.major_id}-${plan.year}`];
          return {
            ...plan,
            min_score: admission ? admission.min_score : null,
            min_rank: admission ? admission.min_rank : null
          };
        });
        this.setData({ school, plans: mergedPlans });
      })
      .catch(() => {
        wx.showToast({ title: '院校详情加载失败', icon: 'none' });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },
  openAnnouncement(event) {
    openAnnouncement(event.currentTarget.dataset.item);
  },
  addMajorToPlan(event) {
    const plan = event.currentTarget.dataset.plan;
    const profile = loadActiveProfileSync();
    if (!profile.rank || !profile.score) {
      wx.showModal({
        title: '请先完善档案',
        content: '手动加入志愿需要分数和位次，用于估算冲稳保档位。',
        confirmText: '去完善',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: '/pages/profile/profile' });
        }
      });
      return;
    }
    requirePermission('manual_simulation', '手动志愿模拟', { consume: true }).then((allowed) => {
      if (!allowed) return;
      const school = this.data.school;
      const userRank = Number(profile.rank);
      const minRank = plan.min_rank ? Number(plan.min_rank) : null;
      let gradientType = '稳';
      if (minRank !== null) {
        const gap = minRank - userRank;
        if (gap < -6000) gradientType = '冲';
        else if (gap < 8000) gradientType = '稳';
        else if (gap < 35000) gradientType = '保';
        else gradientType = '垫';
      }
      wx.setStorageSync('pendingPlanAppend', {
        schoolId: school.school_id,
        schoolName: school.school_name,
        schoolCode: school.school_code,
        majorId: plan.major_id,
        majorName: plan.major_name,
        majorCode: plan.major_code,
        majorType: plan.major_type || '',
        city: school.city,
        schoolType: school.school_type,
        tuition: plan.tuition,
        duration: plan.duration,
        gradientType,
        isAdjustable: true,
        riskLevel: gradientType === '冲' ? '中' : '低',
        riskReason: '手动加入的志愿，建议生成方案后执行风险排查。'
      });
      wx.showToast({ title: '已加入志愿', icon: 'success' });
      setTimeout(() => {
        wx.switchTab({ url: '/pages/volunteer/volunteer' });
      }, 500);
    });
  }
});
