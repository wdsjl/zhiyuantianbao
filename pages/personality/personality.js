const { questions, options, calculateResult } = require('../../utils/personality');

function buildQuestions(answers = {}) {
  return questions.map((question) => ({
    ...question,
    selectedValue: answers[question.id] || 0
  }));
}

Page({
  data: {
    questions: buildQuestions(),
    options,
    answers: {},
    result: null,
    progress: 0
  },
  onLoad() {
    const result = wx.getStorageSync('personalityResult') || null;
    if (result) {
      this.setData({ result });
    }
  },
  selectOption(event) {
    const questionId = event.currentTarget.dataset.questionId;
    const value = event.currentTarget.dataset.value;
    const answers = { ...this.data.answers, [questionId]: value };
    const progress = Math.round((Object.keys(answers).length / questions.length) * 100);
    this.setData({ answers, progress, questions: buildQuestions(answers) });
  },
  submitTest() {
    if (Object.keys(this.data.answers).length < questions.length) {
      wx.showToast({ title: '请完成全部题目', icon: 'none' });
      return;
    }
    const result = calculateResult(this.data.answers);
    wx.setStorageSync('personalityResult', result);
    this.setData({ result });
    wx.showToast({ title: '测评完成', icon: 'success' });
  },
  retest() {
    wx.showModal({
      title: '重新测评',
      content: '重新测评会覆盖当前性格与专业匹配结果，是否继续？',
      success: (res) => {
        if (!res.confirm) return;
        wx.removeStorageSync('personalityResult');
        this.setData({ answers: {}, result: null, progress: 0, questions: buildQuestions() });
      }
    });
  },
  goVolunteer() {
    if (!this.data.result) {
      wx.showToast({ title: '请先完成测评', icon: 'none' });
      return;
    }
    wx.switchTab({ url: '/pages/volunteer/volunteer' });
  }
});
