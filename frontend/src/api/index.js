/**
 * API 层 — 对接后端所有接口
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// ============================================================
// 实习生端
// ============================================================

export const internApi = {
  /** 看板数据（含成长时间线） */
  getDashboard(internId) {
    return api.get('/intern/dashboard', { params: internId ? { intern_id: internId } : {} })
      .then(r => r.data)
  },

  /** 所有实习生列表 */
  listInterns() {
    return api.get('/intern/list').then(r => r.data)
  },

  /** 成长地图 */
  getGrowthMap(internId) {
    return api.get(`/intern/${internId}/growth-map`).then(r => r.data)
  },

  /** 添加自定义事项 */
  addCustomTask(data) {
    return api.post('/intern/custom-task', data).then(r => r.data)
  },

  /** 切换任务完成状态 */
  toggleTask(taskId) {
    return api.put(`/intern/toggle-task/${taskId}`).then(r => r.data)
  },

  /** 销售反向确认提交（§13.3 补丁二） */
  submitReverseConfirm(internId, text) {
    return api.post('/intern/reverse-confirm', { intern_id: internId, text }).then(r => r.data)
  },

  /** 获取活跃崩溃事件（Copilot 弹窗） */
  getActiveBreakdowns(internId) {
    return api.get(`/intern/${internId}/active-breakdowns`).then(r => r.data)
  },

  /** 关闭 Copilot 弹窗 */
  dismissBreakdown(internId, eventId) {
    return api.post(`/intern/${internId}/dismiss-breakdown/${eventId}`).then(r => r.data)
  },

  /** 获取成长错题本 */
  getErrorBook(internId) {
    return api.get(`/intern/${internId}/error-book`).then(r => r.data)
  },
}

// ============================================================
// 导师端
// ============================================================

export const mentorApi = {
  /** 导师看板（冷热隔离） */
  getDashboard(mentorId = 1) {
    return api.get('/mentor/dashboard', { params: { mentor_id: mentorId } }).then(r => r.data)
  },

  /** 一键决策 */
  doAction(data) {
    return api.post('/mentor/action', data).then(r => r.data)
  },

  /** 一键问进度 */
  askProgress(internId) {
    return api.post(`/mentor/ask-progress/${internId}`).then(r => r.data)
  },

  /** 标记预警已知晓 */
  markAcknowledged(alertId) {
    return api.put(`/mentor/mark-acknowledged/${alertId}`).then(r => r.data)
  },

  /** 举证式消红点（绩效利益捆绑） */
  resolveWithEvidence(data) {
    return api.post('/mentor/resolve-with-evidence', data).then(r => r.data)
  },
}

// ============================================================
// HR端
// ============================================================

export const hrApi = {
  /** 周报（常模排名） */
  weeklyReport() {
    return api.get('/hr/weekly-report').then(r => r.data)
  },

  /** 风控打标 */
  riskTags() {
    return api.get('/hr/risk-tags').then(r => r.data)
  },
}

// ============================================================
// AI服务
// ============================================================

export const aiApi = {
  recommendations() {
    return api.get('/ai/recommendations').then(r => r.data)
  },
  dailyInsight(internId) {
    return api.get(`/ai/daily-insight/${internId}`).then(r => r.data)
  },
}

// ============================================================
// 上帝视角沙盒
// ============================================================

export const sandboxApi = {
  /** 模拟事件注入 */
  simulate(internId, event) {
    return api.post('/sandbox/simulate', { intern_id: internId, event }).then(r => r.data)
  },

  /** 获取所有实习生（供沙盒选择） */
  getInterns() {
    return api.get('/sandbox/interns').then(r => r.data)
  },

  /** 获取模拟历史 */
  getRuns() {
    return api.get('/sandbox/runs').then(r => r.data)
  },
}

export default api
