function normalizeInviteCode(code) {
  return String(code || '').trim().toUpperCase();
}

// 微信默认启动 scene（如 1001=发现栏），不是达人推广码
const WECHAT_LAUNCH_SCENES = new Set([
  '1001', '1005', '1006', '1007', '1008', '1010', '1011', '1012', '1013',
  '1014', '1017', '1019', '1020', '1022', '1023', '1024', '1025', '1026',
  '1027', '1028', '1029', '1030', '1031', '1032', '1034', '1035', '1036',
  '1037', '1038', '1039', '1042', '1043', '1044', '1045', '1046', '1047',
  '1048', '1049', '1052', '1053', '1054', '1055', '1056', '1057', '1058',
  '1059', '1060', '1064', '1065', '1067', '1068', '1069', '1071', '1072',
  '1073', '1074', '1077', '1078', '1079', '1081', '1082', '1084', '1088',
  '1089', '1090', '1091', '1092', '1095', '1096', '1097', '1099', '1102',
  '1103', '1104', '1106', '1107', '1113', '1114', '1119', '1120', '1121',
  '1124', '1125', '1126', '1129', '1131', '1133', '1135', '1144', '1145',
  '1146', '1148', '1150', '1151', '1152', '1153', '1154', '1155', '1157',
  '1158', '1160', '1167', '1168', '1169', '1171', '1173', '1175', '1176',
  '1177', '1178', '1179', '1181', '1183', '1184', '1185', '1186', '1187',
  '1189', '1191', '1192', '1193', '1194', '1195', '1196', '1197', '1198',
  '1199', '1200', '1201', '1202', '1203', '1204', '1205', '1206', '1207',
  '1208', '1212', '1216', '1220', '1223', '1224', '1225', '1226', '1227',
  '1228', '1230', '1231', '1232', '1233', '1234', '1235', '1236', '1237',
  '1238', '1239', '1240', '1241', '1242', '1243', '1244', '1245', '1248',
  '1252', '1254', '1255', '1256', '1257', '1258', '1259', '1260', '1261',
  '1262', '1263', '1264', '1265', '1266', '1267', '1268', '1269', '1270',
  '1271', '1272', '1273', '1274', '1275', '1276', '1277', '1278', '1279',
  '1280', '1281', '1282', '1283', '1284', '1285', '1286', '1287', '1288',
  '1289', '1290', '1291', '1292', '1293', '1294', '1295', '1296', '1297',
  '1298', '1299', '1300', '1301', '1302', '1303', '1304', '1305', '1306',
  '1307', '1308', '1309', '1310'
]);

function isLikelyInviteCode(code) {
  const text = normalizeInviteCode(code);
  if (!text) return false;
  if (WECHAT_LAUNCH_SCENES.has(text)) return false;
  if (/^B[A-Z0-9]{6}$/.test(text)) return true;
  // 仅当 URL 参数显式传入达人 ID 时接受纯数字（至少 5 位，避免误判 scene）
  if (/^\d{5,10}$/.test(text)) return true;
  return false;
}

function captureInviteFromLaunch(options) {
  options = options || {};
  let code = '';
  const query = options.query || {};
  if (query.invite || query.agent || query.agent_id || query['达人ID']) {
    code = query.invite || query.agent || query.agent_id || query['达人ID'];
  } else if (options.scene) {
    try {
      code = decodeURIComponent(options.scene);
    } catch (error) {
      code = options.scene;
    }
    // 扫码 scene 只接受 B 开头的正式推广码，忽略 1001 等微信场景值
    code = normalizeInviteCode(code);
    if (!/^B[A-Z0-9]{6}$/.test(code)) {
      return;
    }
    wx.setStorageSync('pendingInviteCode', code);
    return;
  }
  code = normalizeInviteCode(code);
  if (isLikelyInviteCode(code)) {
    wx.setStorageSync('pendingInviteCode', code);
  }
}

function cleanupInvalidInviteCode() {
  const code = getPendingInviteCode();
  if (code && !isLikelyInviteCode(code)) {
    clearPendingInviteCode();
  }
}

function getPendingInviteCode() {
  const code = normalizeInviteCode(wx.getStorageSync('pendingInviteCode') || '');
  if (code && !isLikelyInviteCode(code)) {
    clearPendingInviteCode();
    return '';
  }
  return code;
}

function clearPendingInviteCode() {
  wx.removeStorageSync('pendingInviteCode');
}

module.exports = {
  normalizeInviteCode,
  isLikelyInviteCode,
  captureInviteFromLaunch,
  cleanupInvalidInviteCode,
  getPendingInviteCode,
  clearPendingInviteCode
};
