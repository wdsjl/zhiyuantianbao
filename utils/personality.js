const typeMeta = {
  R: {
    name: '现实型',
    desc: '偏好动手实践、工程实现和具体问题解决，适合技术应用、工程制造、信息技术等方向。',
    majorTypes: ['计算机类', '电子信息类', '自动化类', '机械类', '土木类'],
    majors: ['计算机科学与技术', '软件工程', '通信工程', '自动化', '机械设计制造及其自动化']
  },
  I: {
    name: '研究型',
    desc: '偏好逻辑分析、探索规律和独立研究，适合理学、医学、人工智能、数据科学等方向。',
    majorTypes: ['计算机类', '数学类', '物理学类', '生物科学类', '临床医学类'],
    majors: ['人工智能', '数据科学与大数据技术', '数学与应用数学', '生物科学', '临床医学']
  },
  A: {
    name: '艺术型',
    desc: '偏好创意表达、审美设计和内容创作，适合设计、传媒、建筑、人文艺术等方向。',
    majorTypes: ['设计学类', '新闻传播学类', '建筑类', '戏剧与影视学类', '美术学类'],
    majors: ['视觉传达设计', '数字媒体艺术', '新闻学', '建筑学', '广播电视编导']
  },
  S: {
    name: '社会型',
    desc: '偏好沟通协作、帮助他人和公共服务，适合教育、医学、心理、管理服务等方向。',
    majorTypes: ['教育学类', '心理学类', '护理学类', '公共管理类', '社会学类'],
    majors: ['师范类专业', '心理学', '护理学', '社会工作', '公共事业管理']
  },
  E: {
    name: '企业型',
    desc: '偏好组织领导、商业决策和资源协调，适合经管、金融、法学、市场运营等方向。',
    majorTypes: ['工商管理类', '金融学类', '经济学类', '法学类', '电子商务类'],
    majors: ['工商管理', '金融学', '经济学', '法学', '电子商务']
  },
  C: {
    name: '常规型',
    desc: '偏好数据规则、流程管理和稳定执行，适合会计、统计、信息管理、档案管理等方向。',
    majorTypes: ['会计学类', '统计学类', '管理科学与工程类', '图书情报与档案管理类', '财政学类'],
    majors: ['会计学', '统计学', '信息管理与信息系统', '审计学', '财政学']
  }
};

const questions = [
  { id: 1, text: '我喜欢拆解、组装、调试设备或动手解决实际问题。', type: 'R' },
  { id: 2, text: '我喜欢研究规律、分析原因，并用逻辑推理找到答案。', type: 'I' },
  { id: 3, text: '我喜欢设计、写作、影像、音乐或其他创意表达。', type: 'A' },
  { id: 4, text: '我愿意倾听别人、帮助别人解决学习或生活问题。', type: 'S' },
  { id: 5, text: '我喜欢组织活动、表达观点、带领团队达成目标。', type: 'E' },
  { id: 6, text: '我做事重视规则、流程、细节和准确性。', type: 'C' },
  { id: 7, text: '相比纯理论学习，我更喜欢能看见成果的工程或技术任务。', type: 'R' },
  { id: 8, text: '面对复杂问题，我愿意花时间查资料、建模型或做实验。', type: 'I' },
  { id: 9, text: '我希望未来工作能体现个人风格、审美或原创想法。', type: 'A' },
  { id: 10, text: '我喜欢与人合作，愿意从事教育、咨询、医疗或公共服务类工作。', type: 'S' },
  { id: 11, text: '我对商业、管理、谈判、创业或市场竞争比较感兴趣。', type: 'E' },
  { id: 12, text: '我喜欢整理数据、核对信息，并把事情安排得井井有条。', type: 'C' }
];

const options = [
  { label: '非常符合', value: 5 },
  { label: '比较符合', value: 4 },
  { label: '一般', value: 3 },
  { label: '不太符合', value: 2 },
  { label: '完全不符合', value: 1 }
];

function calculateResult(answers) {
  const scores = { R: 0, I: 0, A: 0, S: 0, E: 0, C: 0 };
  questions.forEach((question) => {
    scores[question.type] += Number(answers[question.id] || 0);
  });
  const sorted = Object.keys(scores).sort((a, b) => scores[b] - scores[a]);
  const topTypes = sorted.slice(0, 3);
  const majorTypeSet = new Set();
  const majorSet = new Set();
  topTypes.forEach((type) => {
    typeMeta[type].majorTypes.forEach((item) => majorTypeSet.add(item));
    typeMeta[type].majors.forEach((item) => majorSet.add(item));
  });
  return {
    scores,
    topTypes,
    code: topTypes.join(''),
    primaryType: typeMeta[topTypes[0]],
    typeDetails: topTypes.map((type) => ({ code: type, ...typeMeta[type], score: scores[type] })),
    majorTypes: Array.from(majorTypeSet).slice(0, 8),
    majors: Array.from(majorSet).slice(0, 10),
    createdAt: new Date().toLocaleString()
  };
}

module.exports = {
  questions,
  options,
  typeMeta,
  calculateResult
};
