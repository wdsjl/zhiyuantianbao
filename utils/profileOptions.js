const PROVINCE_NAME = '河南';
const PROVINCE_DISPLAY = '河南省';

const HENAN_CITIES = [
  '郑州市',
  '开封市',
  '洛阳市',
  '平顶山市',
  '安阳市',
  '鹤壁市',
  '新乡市',
  '焦作市',
  '濮阳市',
  '许昌市',
  '漯河市',
  '三门峡市',
  '南阳市',
  '商丘市',
  '信阳市',
  '周口市',
  '驻马店市',
  '济源市'
];

const SUBJECT_COMBINATIONS = [
  '物理+化学+生物',
  '物理+化学+地理',
  '物理+化学+政治',
  '物理+生物+地理',
  '物理+生物+政治',
  '物理+地理+政治',
  '历史+政治+地理',
  '历史+政治+化学',
  '历史+政治+生物',
  '历史+地理+化学',
  '历史+地理+生物',
  '历史+化学+生物'
];

const TARGET_BATCHES = [
  '本科批',
  '本科提前批',
  '专科批',
  '专科提前批'
];

const LEGACY_SUBJECT_MAP = {
  物理化学生物: '物理+化学+生物',
  物理化学地理: '物理+化学+地理',
  物理化学政治: '物理+化学+政治',
  物理生物地理: '物理+生物+地理',
  物理生物政治: '物理+生物+政治',
  物理地理政治: '物理+地理+政治',
  历史政治地理: '历史+政治+地理',
  历史政治化学: '历史+政治+化学',
  历史政治生物: '历史+政治+生物',
  历史地理化学: '历史+地理+化学',
  历史地理生物: '历史+地理+生物',
  历史化学生物: '历史+化学+生物'
};

function normalizeSubjectCombination(value) {
  if (!value) return '';
  const text = String(value).trim();
  if (LEGACY_SUBJECT_MAP[text.replace(/\s/g, '')]) {
    return LEGACY_SUBJECT_MAP[text.replace(/\s/g, '')];
  }
  return text.replace(/\s/g, '').replace(/、/g, '+');
}

function normalizeHenanCity(value) {
  if (!value) return '';
  const text = String(value).trim().replace(/\s/g, '');
  if (!text) return '';
  const matched = HENAN_CITIES.find((city) => city === text || city.replace(/市$/, '') === text.replace(/市$/, ''));
  return matched || text;
}

function findOptionIndex(options, value) {
  if (!value) return -1;
  const normalized = normalizeSubjectCombination(value);
  const index = options.indexOf(normalized);
  if (index >= 0) return index;
  return options.findIndex((item) => item.replace(/\s/g, '') === normalized.replace(/\s/g, ''));
}

module.exports = {
  PROVINCE_NAME,
  PROVINCE_DISPLAY,
  HENAN_CITIES,
  SUBJECT_COMBINATIONS,
  TARGET_BATCHES,
  findOptionIndex,
  normalizeSubjectCombination,
  normalizeHenanCity
};
