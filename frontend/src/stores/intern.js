import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as api from '@/api'

export const useInternStore = defineStore('intern', () => {
  // 当前实习生信息（模拟数据）
  const currentIntern = ref({
    id: 1,
    name: '张三',
    role: '前端开发',
    week: 2,
    phase: '融入期',
    avatar: ''
  })

  // 今日任务
  const todayTasks = ref([])

  // 自定义事项
  const customTasks = ref([])

  // AI推荐内容
  const recommendations = ref([])

  // 成长地图数据
  const growthMap = ref(null)

  // 加载状态
  const loading = ref(false)

  // 计算完成率
  const completionRate = computed(() => {
    const allTasks = [...todayTasks.value, ...customTasks.value]
    if (allTasks.length === 0) return 0
    const done = allTasks.filter(t => t.status === 'done').length
    return Math.round((done / allTasks.length) * 100)
  })

  // 获取每日看板数据
  async function fetchDashboard() {
    loading.value = true
    try {
      const [dashboardRes, recRes] = await Promise.all([
        api.getInternDashboard(),
        api.getAIRecommendations(new Date().toISOString().split('T')[0])
      ])
      todayTasks.value = dashboardRes.data.tasks || []
      customTasks.value = dashboardRes.data.customTasks || []
      recommendations.value = recRes.data.recommendations || []
    } catch {
      // 使用模拟数据
      todayTasks.value = [
        { id: 1, title: '完成接口联调文档阅读', duration: '30min', status: 'pending', type: 'system' },
        { id: 2, title: '提交第一个组件PR', duration: '2h', status: 'pending', type: 'system' },
        { id: 3, title: '参加下午3点技术分享会', duration: '1h', status: 'pending', type: 'system' }
      ]
      customTasks.value = [
        { id: 101, title: '找导师请教状态管理方案', time: '9:30-10:00', status: 'done', type: 'custom' },
        { id: 102, title: '整理学习笔记', time: '16:00-17:00', status: 'pending', type: 'custom' }
      ]
      recommendations.value = [
        { id: 1, type: 'case', title: '张同学的同类型PR写法', desc: '包含组件设计、单测、文档三个部分', tag: '优秀案例' },
        { id: 2, type: 'doc', title: '公司内部《接口联调最佳实践》', desc: '与你今日任务"接口联调"直接相关', tag: '相关文档' },
        { id: 3, type: 'video', title: '上周技术分享《状态管理方案对比》', desc: '与你自定义事项"状态管理"高度匹配', tag: '往期录屏' }
      ]
    } finally {
      loading.value = false
    }
  }

  // 获取成长地图
  async function fetchGrowthMap() {
    loading.value = true
    try {
      const res = await api.getGrowthMap(currentIntern.value.id)
      growthMap.value = res.data
    } catch {
      growthMap.value = null
    } finally {
      loading.value = false
    }
  }

  // 添加自定义事项
  async function addCustomTask(task) {
    try {
      await api.addCustomTask(task)
      customTasks.value.push({
        id: Date.now(),
        ...task,
        status: 'pending',
        type: 'custom'
      })
    } catch {
      customTasks.value.push({
        id: Date.now(),
        ...task,
        status: 'pending',
        type: 'custom'
      })
    }
  }

  // 切换任务状态
  function toggleTask(taskId, type) {
    const list = type === 'custom' ? customTasks : todayTasks
    const task = list.value.find(t => t.id === taskId)
    if (task) {
      task.status = task.status === 'done' ? 'pending' : 'done'
    }
  }

  return {
    currentIntern,
    todayTasks,
    customTasks,
    recommendations,
    growthMap,
    loading,
    completionRate,
    fetchDashboard,
    fetchGrowthMap,
    addCustomTask,
    toggleTask
  }
})
