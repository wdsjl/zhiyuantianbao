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

const EXAM_TYPES = ['普通类', '艺术类', '体育类'];

const ART_TARGET_BATCHES = ['艺术本科批', '艺术专科批'];
const SPORTS_TARGET_BATCHES = ['体育本科批', '体育专科批'];

function getTargetBatchesForExamType(examType) {
  if (examType === '艺术类') return ART_TARGET_BATCHES;
  if (examType === '体育类') return SPORTS_TARGET_BATCHES;
  return TARGET_BATCHES;
}

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

function findOptionIndex(options, value) {
  if (!value) return -1;
  const normalized = normalizeSubjectCombination(value);
  const index = options.indexOf(normalized);
  if (index >= 0) return index;
  return options.findIndex((item) => item.replace(/\s/g, '') === normalized.replace(/\s/g, ''));
}

module.exports = {
  SUBJECT_COMBINATIONS,
  TARGET_BATCHES,
  EXAM_TYPES,
  ART_TARGET_BATCHES,
  SPORTS_TARGET_BATCHES,
  getTargetBatchesForExamType,
  findOptionIndex,
  normalizeSubjectCombination
};
