const MODEL_VERSION = 2;
const MODEL_NAME = 'holland_riasec';

const typeMeta = {
  R: {
    code: 'R',
    name: '现实型',
    hollandName: 'Realistic',
    desc: '偏好动手实践、工程实现和具体问题解决，适合技术应用、工程制造、信息技术等方向。',
    workStyle: '喜欢使用工具、设备或技术手段完成具体任务，重视可看见的成果。',
    environments: ['实验室', '工程现场', '技术车间', '户外项目'],
    strengths: ['动手能力强', '务实稳重', '擅长解决具体问题', '执行力突出'],
    cautions: ['纯理论、久坐型工作可能缺乏动力', '过度关注细节时需兼顾沟通协作'],
    majorTypes: ['计算机类', '电子信息类', '自动化类', '机械类', '土木类'],
    majors: ['计算机科学与技术', '软件工程', '通信工程', '自动化', '机械设计制造及其自动化'],
    careers: ['软件工程师', '机械工程师', '电气工程师', '建筑师', '运维工程师']
  },
  I: {
    code: 'I',
    name: '研究型',
    hollandName: 'Investigative',
    desc: '偏好逻辑分析、探索规律和独立研究，适合理学、医学、人工智能、数据科学等方向。',
    workStyle: '喜欢独立思考、分析数据、探索未知，重视逻辑与证据。',
    environments: ['科研院所', '高校实验室', '医院研究岗', '数据分析团队'],
    strengths: ['逻辑思维强', '好奇心旺盛', '善于分析归纳', '学习能力强'],
    cautions: ['长期单打独斗时需主动沟通', '选择专业需兼顾就业市场现实'],
    majorTypes: ['计算机类', '数学类', '物理学类', '生物科学类', '临床医学类'],
    majors: ['人工智能', '数据科学与大数据技术', '数学与应用数学', '生物科学', '临床医学'],
    careers: ['数据分析师', '算法工程师', '科研人员', '医生', '生物信息工程师']
  },
  A: {
    code: 'A',
    name: '艺术型',
    hollandName: 'Artistic',
    desc: '偏好创意表达、审美设计和内容创作，适合设计、传媒、建筑、人文艺术等方向。',
    workStyle: '重视自我表达、审美判断和创造性输出，不喜欢刻板重复。',
    environments: ['设计工作室', '媒体机构', '文化创意产业', '品牌策划团队'],
    strengths: ['创造力强', '审美敏锐', '表达能力强', '善于突破常规'],
    cautions: ['需平衡兴趣与就业稳定性', '部分创意专业对作品集要求较高'],
    majorTypes: ['设计学类', '新闻传播学类', '建筑类', '戏剧与影视学类', '美术学类'],
    majors: ['视觉传达设计', '数字媒体艺术', '新闻学', '建筑学', '广播电视编导'],
    careers: ['UI/UX 设计师', '新媒体运营', '建筑师', '编导', '品牌策划']
  },
  S: {
    code: 'S',
    name: '社会型',
    hollandName: 'Social',
    desc: '偏好沟通协作、帮助他人和公共服务，适合教育、医学、心理、管理服务等方向。',
    workStyle: '喜欢与人互动、传授知识、提供支持，重视人际价值与社会意义。',
    environments: ['学校', '医院', '社区服务', '咨询辅导机构'],
    strengths: ['共情能力强', '善于沟通', '有耐心', '团队协作好'],
    cautions: ['情绪消耗较大的岗位需做好心理调适', '选专业时关注职业发展空间'],
    majorTypes: ['教育学类', '心理学类', '护理学类', '公共管理类', '社会学类'],
    majors: ['师范类专业', '心理学', '护理学', '社会工作', '公共事业管理'],
    careers: ['教师', '心理咨询师', '护士', '社会工作者', '人力资源']
  },
  E: {
    code: 'E',
    name: '企业型',
    hollandName: 'Enterprising',
    desc: '偏好组织领导、商业决策和资源协调，适合经管、金融、法学、市场运营等方向。',
    workStyle: '喜欢影响他人、组织资源、承担决策，追求目标达成与影响力。',
    environments: ['企业管理层', '金融机构', '创业公司', '市场与销售团队'],
    strengths: ['领导力强', '目标导向', '善于说服', '抗压能力较好'],
    cautions: ['热门商科竞争激烈，需结合分数位次理性选择', '避免只看名头忽视专业内涵'],
    majorTypes: ['工商管理类', '金融学类', '经济学类', '法学类', '电子商务类'],
    majors: ['工商管理', '金融学', '经济学', '法学', '电子商务'],
    careers: ['产品经理', '投资分析师', '律师', '市场营销', '创业者']
  },
  C: {
    code: 'C',
    name: '常规型',
    hollandName: 'Conventional',
    desc: '偏好数据规则、流程管理和稳定执行，适合会计、统计、信息管理、档案管理等方向。',
    workStyle: '喜欢有条理、可预期的工作，重视规则、准确性和效率。',
    environments: ['财务部门', '政府机关', '银行', '档案与信息系统部门'],
    strengths: ['细致严谨', '责任心强', '擅长流程管理', '数据处理能力好'],
    cautions: ['过于求稳可能错过交叉学科机会', '可适度关注技术+管理复合型专业'],
    majorTypes: ['会计学类', '统计学类', '管理科学与工程类', '图书情报与档案管理类', '财政学类'],
    majors: ['会计学', '统计学', '信息管理与信息系统', '审计学', '财政学'],
    careers: ['会计师', '审计师', '统计师', '公务员', '信息管理专员']
  }
};

const questions = [
  { id: 1, text: '我喜欢拆解、组装、调试设备或动手解决实际问题。', type: 'R' },
  { id: 2, text: '相比纯理论学习，我更喜欢能看见成果的工程或技术任务。', type: 'R' },
  { id: 3, text: '我愿意学习使用工具、仪器或软件完成具体操作。', type: 'R' },
  { id: 4, text: '我对机械、电子、建筑或信息技术类实践项目感兴趣。', type: 'R' },
  { id: 5, text: '遇到故障时，我更愿意亲自排查并修复。', type: 'R' },
  { id: 6, text: '我喜欢研究规律、分析原因，并用逻辑推理找到答案。', type: 'I' },
  { id: 7, text: '面对复杂问题，我愿意花时间查资料、建模型或做实验。', type: 'I' },
  { id: 8, text: '我对数学、科学原理或前沿技术探索有持续兴趣。', type: 'I' },
  { id: 9, text: '我享受独立思考和深度分析，而不是频繁社交。', type: 'I' },
  { id: 10, text: '我喜欢通过数据、证据和实验验证自己的观点。', type: 'I' },
  { id: 11, text: '我喜欢设计、写作、影像、音乐或其他创意表达。', type: 'A' },
  { id: 12, text: '我希望未来工作能体现个人风格、审美或原创想法。', type: 'A' },
  { id: 13, text: '我对视觉设计、内容创作或艺术表现类活动有兴趣。', type: 'A' },
  { id: 14, text: '我不满足于照搬模板，更愿意尝试新的表达方式。', type: 'A' },
  { id: 15, text: '我能从作品、设计或故事中获得较强成就感。', type: 'A' },
  { id: 16, text: '我愿意倾听别人、帮助别人解决学习或生活问题。', type: 'S' },
  { id: 17, text: '我喜欢与人合作，愿意从事教育、咨询、医疗或公共服务类工作。', type: 'S' },
  { id: 18, text: '我在团队中更愿意承担协调、陪伴或支持他人的角色。', type: 'S' },
  { id: 19, text: '我对理解他人情绪、提供建议或辅导他人有兴趣。', type: 'S' },
  { id: 20, text: '我认为工作的社会价值和帮助他人很重要。', type: 'S' },
  { id: 21, text: '我喜欢组织活动、表达观点、带领团队达成目标。', type: 'E' },
  { id: 22, text: '我对商业、管理、谈判、创业或市场竞争比较感兴趣。', type: 'E' },
  { id: 23, text: '我愿意在公开场合表达观点并争取他人认同。', type: 'E' },
  { id: 24, text: '我喜欢制定计划、分配任务并推动事情落地。', type: 'E' },
  { id: 25, text: '我对影响决策、整合资源或开拓市场有热情。', type: 'E' },
  { id: 26, text: '我做事重视规则、流程、细节和准确性。', type: 'C' },
  { id: 27, text: '我喜欢整理数据、核对信息，并把事情安排得井井有条。', type: 'C' },
  { id: 28, text: '我擅长在稳定环境中按标准完成高质量工作。', type: 'C' },
  { id: 29, text: '我对财务、统计、档案或信息管理类事务不排斥。', type: 'C' },
  { id: 30, text: '我更信任有章可循、责任清晰的工作方式。', type: 'C' }
];

const options = [
  { label: '非常符合', value: 5 },
  { label: '比较符合', value: 4 },
  { label: '一般', value: 3 },
  { label: '不太符合', value: 2 },
  { label: '完全不符合', value: 1 }
];

function maxScorePerType() {
  const counts = {};
  questions.forEach((question) => {
    counts[question.type] = (counts[question.type] || 0) + 1;
  });
  return Object.fromEntries(Object.keys(typeMeta).map((code) => [code, counts[code] * 5]));
}

function buildTypeDetail(code, score, rank) {
  const meta = typeMeta[code];
  const maxScore = maxScorePerType()[code] || 25;
  return {
    code,
    rank,
    name: meta.name,
    hollandName: meta.hollandName,
    desc: meta.desc,
    workStyle: meta.workStyle,
    environments: meta.environments,
    strengths: meta.strengths,
    cautions: meta.cautions,
    majorTypes: meta.majorTypes,
    majors: meta.majors,
    careers: meta.careers,
    score,
    maxScore,
    percent: Math.round((score / maxScore) * 100)
  };
}

function uniqueList(items, limit) {
  const result = [];
  const seen = new Set();
  items.forEach((item) => {
    if (!item || seen.has(item)) return;
    seen.add(item);
    result.push(item);
  });
  return result.slice(0, limit);
}

function buildCareerReport(result) {
  const primary = result.typeDetails[0];
  const secondary = result.typeDetails[1];
  const tertiary = result.typeDetails[2];
  return {
    title: `霍兰德职业兴趣报告 · ${result.code}`,
    summary: `你的前三兴趣类型为 ${primary.name}、${secondary.name}、${tertiary.name}（${result.code}）。${primary.desc}`,
    profile: {
      primary: primary.name,
      secondary: secondary.name,
      tertiary: tertiary.name,
      code: result.code,
      workStyle: primary.workStyle
    },
    sections: [
      {
        key: 'strengths',
        title: '核心优势',
        items: uniqueList([].concat(primary.strengths, secondary.strengths), 6)
      },
      {
        key: 'environments',
        title: '适合的工作环境',
        items: uniqueList([].concat(primary.environments, secondary.environments), 6)
      },
      {
        key: 'majors',
        title: '推荐专业大类',
        items: result.majorTypes
      },
      {
        key: 'careers',
        title: '可参考的职业方向',
        items: result.careers
      },
      {
        key: 'cautions',
        title: '填报提醒',
        items: uniqueList([].concat(primary.cautions, secondary.cautions, [
          '职业兴趣测评仅作辅助参考，不能替代分数位次与选科要求。',
          '建议结合家庭资源、城市偏好和就业趋势综合决策。'
        ]), 5)
      }
    ]
  };
}

function buildAiContext(result) {
  const report = result.careerReport || buildCareerReport(result);
  const typeLines = result.typeDetails.map((item) => (
    `${item.code}${item.name}(${item.percent}%): ${item.workStyle}；优势：${item.strengths.join('、')}；适合环境：${item.environments.join('、')}`
  ));
  return {
    model: MODEL_NAME,
    version: MODEL_VERSION,
    hollandCode: result.code,
    primaryType: result.typeDetails[0] && result.typeDetails[0].name,
    secondaryType: result.typeDetails[1] && result.typeDetails[1].name,
    tertiaryType: result.typeDetails[2] && result.typeDetails[2].name,
    scores: result.scores,
    normalizedScores: result.normalizedScores,
    majorTypes: result.majorTypes,
    majors: result.majors,
    careers: result.careers,
    strengths: report.sections.find((section) => section.key === 'strengths').items,
    cautions: report.sections.find((section) => section.key === 'cautions').items,
    summary: report.summary,
    typeAnalysis: typeLines,
    disclaimer: '霍兰德职业兴趣测评仅用于辅助专业方向筛选，不构成录取承诺。'
  };
}

function buildReportSummary(result) {
  const aiContext = buildAiContext(result);
  return [
    `霍兰德代码：${aiContext.hollandCode}`,
    `主-次-辅类型：${aiContext.primaryType} / ${aiContext.secondaryType} / ${aiContext.tertiaryType}`,
    aiContext.summary,
    `推荐专业大类：${aiContext.majorTypes.join('、')}`,
    `可参考职业：${aiContext.careers.join('、')}`,
    `核心优势：${aiContext.strengths.join('、')}`,
    `填报提醒：${aiContext.cautions.join('；')}`
  ].join('\n');
}

function calculateResult(answers) {
  const scores = { R: 0, I: 0, A: 0, S: 0, E: 0, C: 0 };
  const maxMap = maxScorePerType();
  questions.forEach((question) => {
    scores[question.type] += Number(answers[question.id] || 0);
  });
  const normalizedScores = Object.fromEntries(
    Object.keys(scores).map((code) => [code, Math.round((scores[code] / maxMap[code]) * 100)])
  );
  const sorted = Object.keys(scores).sort((a, b) => scores[b] - scores[a] || a.localeCompare(b));
  const topTypes = sorted.slice(0, 3);
  const typeDetails = topTypes.map((code, index) => buildTypeDetail(code, scores[code], index + 1));
  const majorTypeSet = new Set();
  const majorSet = new Set();
  const careerSet = new Set();
  topTypes.forEach((type) => {
    typeMeta[type].majorTypes.forEach((item) => majorTypeSet.add(item));
    typeMeta[type].majors.forEach((item) => majorSet.add(item));
    typeMeta[type].careers.forEach((item) => careerSet.add(item));
  });
  const result = {
    version: MODEL_VERSION,
    model: MODEL_NAME,
    scores,
    normalizedScores,
    topTypes,
    code: topTypes.join(''),
    primaryType: typeDetails[0],
    secondaryType: typeDetails[1],
    tertiaryType: typeDetails[2],
    typeDetails,
    majorTypes: Array.from(majorTypeSet).slice(0, 10),
    majors: Array.from(majorSet).slice(0, 12),
    careers: Array.from(careerSet).slice(0, 10),
    answers,
    createdAt: new Date().toLocaleString()
  };
  result.careerReport = buildCareerReport(result);
  result.aiContext = buildAiContext(result);
  result.reportSummary = buildReportSummary(result);
  return result;
}

function migrateLegacyResult(result) {
  if (!result || result.version >= MODEL_VERSION) return result;
  const answers = result.answers || {};
  if (Object.keys(answers).length >= questions.length) {
    return calculateResult(answers);
  }
  return {
    ...result,
    version: result.version || 1,
    aiContext: buildAiContext({
      ...result,
      typeDetails: result.typeDetails || (result.topTypes || []).map((code, index) => buildTypeDetail(code, (result.scores || {})[code] || 0, index + 1)),
      careers: result.careers || []
    }),
    reportSummary: result.reportSummary || buildReportSummary({
      ...result,
      typeDetails: result.typeDetails || [],
      careers: result.careers || [],
      majorTypes: result.majorTypes || []
    })
  };
}

module.exports = {
  MODEL_VERSION,
  MODEL_NAME,
  questions,
  options,
  typeMeta,
  calculateResult,
  buildCareerReport,
  buildAiContext,
  buildReportSummary,
  migrateLegacyResult
};
