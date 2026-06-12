const { filterOptions } = require('../../utils/mockData');
const { request } = require('../../utils/request');
const { loadActiveProfileSync } = require('../../utils/profileHelper');
const { TYPE_OPTIONS, openAnnouncement } = require('../../utils/announcement');

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
    announcementKeyword: '',
    announcementType: '',
    announcementTypeOptions: TYPE_OPTIONS,
    announcements: [],
    announcementLoading: false
  },
  onLoad() {
    this.fetchSchools();
  },
  onShow() {
    if (this.data.activeTab === 'announcements' && !this.data.announcements.length) {
      this.fetchAnnouncements();
    }
  },
  switchTab(event) {
    const activeTab = event.currentTarget.dataset.tab;
    this.setData({ activeTab });
    if (activeTab === 'announcements') {
      this.fetchAnnouncements();
    }
  },
  formatSchools(list) {
    return list.map((school) => {
      const tags = [];
      if (school.is_985) tags.push('985');
      if (school.is_211) tags.push('211');
      if (school.is_double_first_class) tags.push('双一流');
      if (!tags.length) tags.push(school.education_level || '普通本科');
      return {
        ...school,
        id: school.school_id,
        name: school.school_name,
        code: school.school_code,
        type: school.is_public ? '公办' : '民办',
        tags,
        majorsText: '点击查看招生专业与历年分数',
        subject: school.education_level || '本科',
        minRank: '--',
        tuition: '--',
        duration: school.city || ''
      };
    });
  },
  onKeywordInput(event) {
    this.setData({ keyword: event.detail.value });
  },
  onAnnouncementKeywordInput(event) {
    this.setData({ announcementKeyword: event.detail.value });
  },
  onAnnouncementTypeChange(event) {
    this.setData({ announcementType: event.currentTarget.dataset.type || '' });
    this.fetchAnnouncements();
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
  fetchSchools() {
    const city = this.data.selected.cities.length === 1 ? this.data.selected.cities[0] : '';
    const data = {
      keyword: this.data.keyword,
      city,
      limit: 50,
      offset: 0
    };
    const isPublic = this.getPublicParam();
    const isDoubleFirst = this.getDoubleFirstParam();
    if (isPublic !== undefined) data.is_public = isPublic;
    if (isDoubleFirst !== undefined) data.is_double_first_class = isDoubleFirst;

    this.setData({ loading: true });
    request({ url: '/api/schools', data })
      .then((res) => {
        let list = this.formatSchools(res.list || []);
        list = this.applyClientFilters(list);
        this.setData({ filteredSchools: list, showFilter: false });
        if (!list.length) wx.showToast({ title: '建议放宽筛选条件', icon: 'none' });
      })
      .catch(() => {
        wx.showToast({ title: '接口连接失败，请确认后端已启动', icon: 'none' });
      })
      .finally(() => {
        this.setData({ loading: false });
      });
  },
  fetchAnnouncements() {
    const profile = loadActiveProfileSync();
    const province = profile.province || '河南';
    this.setData({ announcementLoading: true });
    request({
      url: '/api/announcements',
      data: {
        keyword: this.data.announcementKeyword,
        province,
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
  applyClientFilters(list) {
    const { selected } = this.data;
    return list.filter((school) => {
      const cityHit = !selected.cities.length || selected.cities.includes(school.city);
      const typeHit = !selected.schoolTypes.length || selected.schoolTypes.includes(school.type);
      const tagHit = !selected.tags.length || school.tags.some((tag) => selected.tags.includes(tag));
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
  addToVolunteer(event) {
    const school = event.currentTarget.dataset.school;
    if (!school || !school.school_id) return;
    wx.navigateTo({ url: `/pages/school-detail/school-detail?id=${school.school_id}` });
  },
  openAnnouncement(event) {
    openAnnouncement(event.currentTarget.dataset.item);
  }
});
