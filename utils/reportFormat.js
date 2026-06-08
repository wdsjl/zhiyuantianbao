function getStudentName(profile) {
  return String((profile && (profile.name || profile.studentName || profile.student_name)) || '').trim();
}

function buildReportGreeting(profile) {
  const name = getStudentName(profile);
  if (!name) return '尊敬的同学、同学家长，您好：';
  return `${name}同学、${name}同学家长，您好：`;
}

function ensureReportGreeting(report, profile) {
  const content = String(report || '').trim();
  if (!content) return content;
  const name = getStudentName(profile);
  const head = content.slice(0, 40);
  if (head.includes('家长，您好') || (name && head.startsWith(`${name}同学`))) {
    return content;
  }
  return `${buildReportGreeting(profile)}\n\n${content}`;
}

module.exports = {
  buildReportGreeting,
  ensureReportGreeting,
  getStudentName
};
