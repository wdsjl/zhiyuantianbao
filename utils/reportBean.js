const { getCurrentUserId, requirePermission } = require('./membership');

function confirmReportPermission(reportTitle, permissionCode) {
  const title = reportTitle || 'AI 报告';
  const code = permissionCode || 'personality_deep';
  return requirePermission(code, title, { consume: true });
}

module.exports = {
  confirmReportPermission
};
