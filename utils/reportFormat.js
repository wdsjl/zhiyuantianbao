const FILLER_PATTERNS = [
  /^好的[，,。！!：:\s]+/u,
  /^没问题[，,。！!：:\s]+/u,
  /^当然[，,。！!：:\s]+/u,
  /^嗯[，,。！!：:\s]+/u
];

function getStudentName(profile) {
  return String((profile && (profile.name || profile.studentName || profile.student_name)) || '').trim();
}

function stripReportFiller(report) {
  let content = String(report || '').trim();
  let changed = true;
  while (changed && content) {
    changed = false;
    for (const pattern of FILLER_PATTERNS) {
      const next = content.replace(pattern, '').trim();
      if (next !== content) {
        content = next;
        changed = true;
        break;
      }
    }
  }
  return content;
}

function buildReportGreeting(profile) {
  const name = getStudentName(profile);
  if (!name) return '尊敬的同学、同学家长，您好：';
  return `${name}同学、${name}同学家长，您好：`;
}

function ensureReportGreeting(report, profile) {
  const content = stripReportFiller(report);
  if (!content) return content;
  const name = getStudentName(profile);
  const head = content.slice(0, 40);
  if (head.includes('家长，您好') || (name && head.startsWith(`${name}同学`))) {
    return content;
  }
  return `${buildReportGreeting(profile)}\n\n${content}`;
}

const AI_GENERATED_NOTICE = 'AI生成 · 人工智能生成';
const AI_GENERATED_MARKERS = ['人工智能生成', 'AI生成'];
const SYSTEM_GENERATED_NOTICE = '此报告系系统自动生成（大数据智能匹配）';
const SYSTEM_GENERATED_MARKERS = ['系统自动生成', '大数据智能匹配'];

function hasAiGeneratedNotice(text) {
  const content = String(text || '').trim();
  if (!content) return false;
  const tail = content.slice(-120);
  return AI_GENERATED_MARKERS.some((marker) => tail.includes(marker));
}

function appendAiGeneratedNotice(text) {
  const content = String(text || '').trim();
  if (!content || hasAiGeneratedNotice(content)) return content;
  return `${content}\n\n—— ${AI_GENERATED_NOTICE}`;
}

function formatReportContent(report, profile) {
  return appendAiGeneratedNotice(ensureReportGreeting(stripReportFiller(report), profile));
}

function formatAiContent(text) {
  return appendAiGeneratedNotice(text);
}

function hasSystemGeneratedNotice(text) {
  const content = String(text || '').trim();
  if (!content) return false;
  const tail = content.slice(-120);
  return SYSTEM_GENERATED_MARKERS.some((marker) => tail.includes(marker));
}

function appendSystemGeneratedNotice(text) {
  const content = String(text || '').trim();
  if (!content || hasSystemGeneratedNotice(content)) return content;
  return `${content}\n\n—— ${SYSTEM_GENERATED_NOTICE}`;
}

module.exports = {
  AI_GENERATED_NOTICE,
  SYSTEM_GENERATED_NOTICE,
  buildReportGreeting,
  ensureReportGreeting,
  formatReportContent,
  formatAiContent,
  appendAiGeneratedNotice,
  appendSystemGeneratedNotice,
  hasAiGeneratedNotice,
  hasSystemGeneratedNotice,
  stripReportFiller,
  getStudentName
};
