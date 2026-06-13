import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as api from '@/api'

export const useMentorStore = defineStore('mentor', () => {
  const interns = ref([])
  const loading = ref(false)

  // 获取导师工作台数据
  async function fetchDashboard() {
    loading.value = true
    try {
      const res = await api.getMentorDashboard()
      interns.value = res.data.interns || []
    } catch {
      // 模拟数据
      interns.value = [
        {
          id: 1,
          name: '张三',
          role: '前端开发',
          week: 2,
          progress: 80,
          status: 'normal',
          recentCommits: 12,
          recentDocs: 45
        },
        {
          id: 2,
          name: '李四',
          role: '后端开发',
          week: 2,
          progress: 75,
          status: 'normal',
          recentCommits: 8,
          recentDocs: 30
        },
        {
          id: 3,
          name: '王五',
          role: '前端开发',
          week: 2,
          progress: 20,
          status: 'warning',
          recentCommits: 0,
          recentDocs: 0,
          alert: '连续3天无代码提交'
        }
      ]
    } finally {
      loading.value = false
    }
  }

  // 一键问进度
  async function askProgress(internId) {
    try {
      await api.askProgress(internId)
    } catch {
      // 模拟
    }
    return true
  }

  // 标记已知晓
  async function markAcknowledged(internId) {
    try {
      await api.markAcknowledged(internId)
    } catch {
      // 模拟
    }
    const intern = interns.value.find(i => i.id === internId)
    if (intern) {
      intern.status = 'acknowledged'
    }
    return true
  }

  // 拆分工作量
  async function splitTask(internId, taskId) {
    try {
      await api.splitTask(internId, taskId)
    } catch {
      // 模拟
    }
    return true
  }

  return {
    interns,
    loading,
    fetchDashboard,
    askProgress,
    markAcknowledged,
    splitTask
  }
})
