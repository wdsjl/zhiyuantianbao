const schools = [
  {
    id: 's001',
    name: '华东理工大学',
    code: '10251',
    city: '上海',
    type: '公办',
    tags: ['双一流', '211'],
    minRank: 18000,
    tuition: 5000,
    duration: '4年',
    majors: ['计算机类', '电子信息类', '化工与制药类'],
    subject: '物理+化学'
  },
  {
    id: 's002',
    name: '南京邮电大学',
    code: '10293',
    city: '南京',
    type: '公办',
    tags: ['双一流'],
    minRank: 26000,
    tuition: 5800,
    duration: '4年',
    majors: ['通信工程', '计算机类', '人工智能'],
    subject: '物理'
  },
  {
    id: 's003',
    name: '浙江工业大学',
    code: '10337',
    city: '杭州',
    type: '公办',
    tags: ['省重点'],
    minRank: 33000,
    tuition: 6000,
    duration: '4年',
    majors: ['机械类', '自动化类', '计算机类'],
    subject: '物理'
  },
  {
    id: 's004',
    name: '重庆邮电大学',
    code: '10617',
    city: '重庆',
    type: '公办',
    tags: ['普通本科'],
    minRank: 43000,
    tuition: 5600,
    duration: '4年',
    majors: ['软件工程', '电子信息类', '自动化类'],
    subject: '物理'
  },
  {
    id: 's005',
    name: '成都锦城学院',
    code: '13903',
    city: '成都',
    type: '民办',
    tags: ['普通本科'],
    minRank: 69000,
    tuition: 17000,
    duration: '4年',
    majors: ['计算机科学与技术', '财务管理', '网络与新媒体'],
    subject: '不限'
  },
  {
    id: 's006',
    name: '武汉职业技术学院',
    code: '10834',
    city: '武汉',
    type: '公办',
    tags: ['高职专科'],
    minRank: 120000,
    tuition: 5000,
    duration: '3年',
    majors: ['软件技术', '电子商务', '机电一体化'],
    subject: '不限'
  }
];

const filterOptions = {
  cities: ['北京', '上海', '广州', '深圳', '杭州', '南京', '武汉', '成都', '西安', '重庆'],
  schoolTypes: ['公办', '民办', '中外合作办学', '独立学院', '职业本科'],
  tags: ['双一流', '985', '211', '省重点', '普通本科', '高职专科'],
  majorTypes: ['计算机类', '电子信息类', '临床医学类', '金融学类', '法学类', '师范类', '电气类', '机械类', '自动化类', '人工智能类'],
  tuitionRanges: ['5000元以下/年', '5000-10000元/年', '10000-20000元/年', '20000-50000元/年', '50000元以上/年'],
  durations: ['3年', '4年', '5年', '本硕连读', '本硕博连读']
};

module.exports = {
  schools,
  filterOptions
};
