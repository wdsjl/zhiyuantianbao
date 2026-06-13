const { filterOptions } = require('../../utils/mockData');
const { request } = require('../../utils/request');
const { loadActiveProfileSync } = require('../../utils/profileHelper');
const { TYPE_OPTIONS, openAnnouncement } = require('../../utils/announcement');

const YEAR_OPTIONS = [2026, 2025, 2024];
const BATCH_OPTIONS = ['本科批', '专科批', ''];

Page({
  data: {
    activeTab: 'schools',
    keyword: '',
    showFilter: false,
    loading: false,
    filterOptions,
    selected: {
      cities: [],
      schoolTypes: [],
      tags: [],
      majorTypes: [],
      tuitionRanges: [],
      durations: []
    },
    filteredSchools: [],
    schoolTotal: 0,
    schoolOffset: 0,
    schoolPageSize: 100,
    schoolHasMore: false,
    rankMap: {},
    profileProvince: '河南',
    profileBatch: '本科批',
    announcementKeyword: '',
    announcementType: '',
    announcementTypeOptions: TYPE_OPTIONS,
    announcements: [],
    announcementLoading: false,
    queryMode: 'score',
    queryProvince: '河南',
    queryYear: 2026,
    queryBatch: '本科批',
    queryScore: '',
    queryRank: '',
    queryResult: null,
    queryLoading: false,
    admissionKeyword: '',
    admissionRecords: [],
    admissionLoading: false,
    yearOptions: YEAR_OPTIONS,
    batchOptions: BATCH_OPTIONS
  },
  onLoad() {
    this.syncProfileDefaults();
    this.fetchSchools();
  },
  onShow() {
    this.syncProfileDefaults();
    if (this.data.activeTab === 'announcements' && !this.data.announcements.length) {
      this.fetchAnnouncements();
    }
  },
  onReachBottom() {
    if (this.data.activeTab === 'schools' && this.data.schoolHasMore && !this.data.loading) {
      this.fetchSchools(false);
    }
  },
  syncProfileDefaults() {
    const profile = loadActiveProfileSync();
    const province = profile.province || '河南';
    const batch = profile.targetBatch || profile.batch || '本科批';
    this.setData({
      profileProvince: province,
      profileBatch: batch,
      queryProvince: province,
      queryBatch: batch
    });
  },
  switchTab(event) {
    const activeTab = event.currentTarget.dataset.tab;
    this.setData({ activeTab });
    if (activeTab === 'announcements') {
      this.fetchAnnouncements();
    }
  },
  formatSchools(list, rankMap) {
    return list.map((school) => {
      const tags = [];
      if (school.is_985) tags.push('985');
      if (school.is_211) tags.push('211');
      if (school.is_double_first_class) tags.push('双一流');
      if (!tags.length) tags.push(school.education_level || '普通本科');
      const snapshot = rankMap[school.school_id] || {};
      const minRank = snapshot.best_min_rank || school.best_min_rank;
      const minScore = snapshot.best_min_score || school.best_min_score;
      return {
        ...school,
        id: school.school_id,
        name: school.school_name,
        code: school.school_code,
        type: school.is_public ? '公办' : '民办',
        tags,
        majorsText: snapshot.major_count
          ? (snapshot.best_min_rank
            ? `近年 ${snapshot.major_count} 个专业有录取/计划数据`
            : `${snapshot.plan_major_count || snapshot.major_count} 个招生专业`)
          : '点击查看招生专业与历年分数',
        subject: school.education_level || '本科',
        minRank: minRank ? String(minRank) : '--',
        minScore: minScore ? String(minScore) : '--',
        tuition: '--',
        duration: school.city || ''
      };
    });
  },
  onKeywordInput(event) {
    this.setData({ keyword: event.detail.value });
  },
  onSearchConfirm() {
    this.fetchSchools();
  },
  onAnnouncementKeywordInput(event) {
    this.setData({ announcementKeyword: event.detail.value });
  },
  onAnnouncementTypeChange(event) {
    this.setData({ announcementType: event.currentTarget.dataset.type || '' });
    this.fetchAnnouncements();
  },
  onQueryModeChange(event) {
    this.setData({ queryMode: event.currentTarget.dataset.mode || 'score', queryResult: null });
  },
  onQueryProvinceInput(event) {
    this.setData({ queryProvince: event.detail.value });
  },
  onQueryYearChange(event) {
    this.setData({ queryYear: Number(event.currentTarget.dataset.year) || 2026 });
  },
  onQueryBatchChange(event) {
    this.setData({ queryBatch: event.currentTarget.dataset.batch || '' });
  },
  onQueryScoreInput(event) {
    this.setData({ queryScore: event.detail.value });
  },
  onQueryRankInput(event) {
    this.setData({ queryRank: event.detail.value });
  },
  onAdmissionKeywordInput(event) {
    this.setData({ admissionKeyword: event.detail.value });
  },
  toggleFilter() {
    this.setData({ showFilter: !this.data.showFilter });
  },
  toggleOption(event) {
    const { field, value } = event.currentTarget.dataset;
    const selected = { ...this.data.selected };
    const values = selected[field];
    const index = values.indexOf(value);
    if (index > -1) {
      values.splice(index, 1);
    } else {
      values.push(value);
    }
    this.setData({ selected });
  },
  getPublicParam() {
    const types = this.data.selected.schoolTypes;
    if (types.includes('公办') && !types.includes('民办')) return 1;
    if (types.includes('民办') && !types.includes('公办')) return 0;
    return undefined;
  },
  getDoubleFirstParam() {
    return this.data.selected.tags.includes('双一流') ? 1 : undefined;
  },
  fetchRankSnapshot() {
    return request({
      url: '/api/schools/rank-snapshot',
      data: {
        province: this.data.profileProvince,
        batch: this.data.profileBatch,
        keyword: this.data.keyword || '',
        limit: 5000
      }
    }).then((res) => {
      const rankMap = {};
      (res.list || []).forEach((item) => {
        rankMap[item.school_id] = item;
      });
      this.setData({ rankMap });
      return rankMap;
    }).catch(() => ({}));
  },
  fetchSchools(reset = true) {
    const city = this.data.selected.cities.length === 1 ? this.data.selected.cities[0] : '';
    const offset = reset ? 0 : this.data.schoolOffset;
    const data = {
      keyword: this.data.keyword,
      province: this.data.profileProvince,
      batch: this.data.profileBatch,
      city,
      limit: this.data.schoolPageSize,
      offset
    };
    const isPublic = this.getPublicParam();
    const isDoubleFirst = this.getDoubleFirstParam();
    if (isPublic !== undefined) data.is_public = isPublic;
    if (isDoubleFirst !== undefined) data.is_double_first_class = isDoubleFirst;

    this.setData({ loading: true });
    const rankPromise = reset ? this.fetchRankSnapshot() : Promise.resolve(this.data.rankMap || {});
    rankPromise
      .then((rankMap) => request({ url: '/api/schools', data }))
      .then((res) => {
        let list = res.list || [];
        const total = Number(res.total || 0);
        list = this.applyClientFilters(list);
        const rankMap = this.data.rankMap || {};
        const formatted = this.formatSchools(list, rankMap);
        const merged = reset ? formatted : [...this.data.filteredSchools, ...formatted];
        const nextOffset = offset + (res.list || []).length;
        this.setData({
          filteredSchools: merged,
          schoolTotal: total || merged.length,
          schoolOffset: nextOffset,
          schoolHasMore: nextOffset < (total || merged.length),
          showFilter: false
        });
        if (!merged.length) wx.showToast({ title: '暂无院校数据，请先导入招生计划', icon: 'none' });
      })
      .catch(() => {
        wx.showToast({ title: '接口连接失败，请确认后端已启动', icon: 'none' });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },
  fetchAnnouncements() {
    this.setData({ announcementLoading: true });
    request({
      url: '/api/announcements',
      data: {
        keyword: this.data.announcementKeyword,
        province: this.data.profileProvince,
        year: 2026,
        review_status: 'approved',
        announcement_type: this.data.announcementType || '',
        limit: 100
      }
    })
      .then((res) => {
        this.setData({ announcements: res.list || [] });
      })
      .catch(() => {
        wx.showToast({ title: '公告加载失败', icon: 'none' });
      })
      .finally(() => {
        this.setData({ announcementLoading: false });
      });
  },
  lookupScoreSegment() {
    const { queryMode, queryProvince, queryYear, queryBatch, queryScore, queryRank } = this.data;
    if (!queryProvince) {
      wx.showToast({ title: '请填写省份', icon: 'none' });
      return;
    }
    const data = {
      province: queryProvince,
      year: queryYear,
      batch: queryBatch
    };
    if (queryMode === 'score') {
      if (!queryScore) {
        wx.showToast({ title: '请输入分数', icon: 'none' });
        return;
      }
      data.score = Number(queryScore);
    } else {
      if (!queryRank) {
        wx.showToast({ title: '请输入位次', icon: 'none' });
        return;
      }
      data.rank = Number(queryRank);
    }
    this.setData({ queryLoading: true, queryResult: null });
    request({ url: '/api/score-segments/lookup', data })
      .then((res) => {
        this.setData({ queryResult: res });
      })
      .catch((err) => {
        const msg = (err && err.detail) || '未找到一分一段表，请先在后台导入';
        wx.showToast({ title: msg, icon: 'none' });
      })
      .finally(() => {
        this.setData({ queryLoading: false });
      });
  },
  searchAdmissions() {
    const keyword = (this.data.admissionKeyword || this.data.keyword || '').trim();
    if (!keyword) {
      wx.showToast({ title: '请输入院校或专业名称', icon: 'none' });
      return;
    }
    this.setData({ admissionLoading: true });
    request({
      url: '/api/admissions',
      data: {
        province: this.data.profileProvince,
        batch: this.data.profileBatch,
        keyword,
        limit: 80
      }
    })
      .then((res) => {
        this.setData({ admissionRecords: res.list || [] });
        if (!(res.list || []).length) {
          wx.showToast({ title: '未找到录取数据', icon: 'none' });
        }
      })
      .catch(() => {
        wx.showToast({ title: '录取数据查询失败', icon: 'none' });
      })
      .finally(() => {
        this.setData({ admissionLoading: false });
      });
  },
  applyClientFilters(list) {
    const { selected } = this.data;
    return list.filter((school) => {
      const cityHit = !selected.cities.length || selected.cities.includes(school.city);
      const typeText = school.is_public ? '公办' : '民办';
      const typeHit = !selected.schoolTypes.length || selected.schoolTypes.includes(typeText);
      const tags = [];
      if (school.is_985) tags.push('985');
      if (school.is_211) tags.push('211');
      if (school.is_double_first_class) tags.push('双一流');
      const tagHit = !selected.tags.length || tags.some((tag) => selected.tags.includes(tag));
      return cityHit && typeHit && tagHit;
    });
  },
  applyFilter() {
    this.fetchSchools();
  },
  openSchoolDetail(event) {
    const school = event.currentTarget.dataset.school;
    if (!school || !school.school_id) return;
    wx.navigateTo({ url: `/pages/school-detail/school-detail?id=${school.school_id}` });
  },
  openAdmissionSchool(event) {
    const schoolId = event.currentTarget.dataset.schoolId;
    if (!schoolId) return;
    wx.navigateTo({ url: `/pages/school-detail/school-detail?id=${schoolId}` });
  },
  addToVolunteer(event) {
    const school = event.currentTarget.dataset.school;
    if (!school || !school.school_id) return;
    wx.navigateTo({ url: `/pages/school-detail/school-detail?id=${school.school_id}` });
  },
  openAnnouncement(event) {
    openAnnouncement(event.currentTarget.dataset.item);
  }
});
