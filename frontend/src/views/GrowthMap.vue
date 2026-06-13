<template>
  <div class="growth-map-page">
    <div class="page-header">
      <t-button theme="default" variant="outline" size="small" @click="$router.push('/intern')">
        <template #icon><t-icon name="chevron-left" /></template>返回看板
      </t-button>
      <h2>🗺️ {{ data.name }} 的成长地图</h2>
    </div>

    <!-- 三阶段卡片 -->
    <div v-for="phase in data.phases" :key="phase.id" :class="['phase-card', `phase-${phase.status}`]">
      <div class="phase-header">
        <div class="phase-title-row">
          <span class="phase-badge" :data-status="phase.status">{{ phaseStatusText(phase.status) }}</span>
          <h3>{{ phase.name }}</h3>
          <t-tag v-if="phase.dateRange" size="small" variant="light">{{ phase.dateRange }}</t-tag>
        </div>
        <t-progress v-if="hasTasks(phase)" :percentage="phaseProgress(phase)" :status="progressStatus(phase)" :stroke-width="8" style="max-width:300px;margin-top:6px" />
      </div>

      <!-- 四维度表格 -->
      <table v-if="hasTasks(phase)" class="dim-table">
        <thead><tr><th>能力维度</th><th>系统任务</th><th>状态</th></tr></thead>
        <tbody>
          <template v-for="dim in phase.dimensions" :key="dim.name">
            <tr class="dim-header"><td colspan="3"><b>{{ dimName(dim.name) }}</b> · 完成{{ dim.completion }}%</td></tr>
            <tr v-for="task in dim.systemTasks" :key="task.id" class="task-tr">
              <td width="40%">{{ task.title }}
                <span v-if="task.description" class="task-desc">— {{ task.description.slice(0, 30) }}...</span>
              </td>
              <td width="30%">
                <t-tag v-if="task.source === 'mentor'" size="extra-small" theme="warning" variant="light">导师布置</t-tag>
                <span v-else-if="task.hours" style="font-size:12px;color:#86909c">~{{ task.hours }}h</span>
              </td>
              <td width="20%">
                <t-tag :theme="taskTheme(task.status)" size="small" variant="light">{{ taskStatusLabel(task.status) }}</t-tag>
              </td>
            </tr>
            <tr v-for="task in dim.customTasks" :key="task.id" class="task-tr custom-task">
              <td>{{ task.title }}</td>
              <td><t-tag size="extra-small" variant="light" theme="primary">自定义</t-tag></td>
              <td><t-tag :theme="taskTheme(task.status)" size="small" variant="light">{{ taskStatusLabel(task.status) }}</t-tag></td>
            </tr>
          </template>
        </tbody>
      </table>

      <div v-else class="empty-phase">暂无任务安排</div>
    </div>

    <!-- 自定义事项汇总 -->
    <t-card title="📝 自定义学习计划" bordered class="custom-section">
      <div v-if="data.customTasks?.length > 0" class="custom-list">
        <div v-for="ct in data.customTasks" :key="ct.id" class="custom-item">
          <t-checkbox :checked="ct.status === 'done'" disabled />
          <span>{{ ct.title }}</span>
          <t-tag v-if="ct.time" size="small" variant="light">{{ ct.time }}</t-tag>
          <t-tag :theme="taskTheme(ct.status)" size="small" variant="light">{{ ct.status === 'done' ? '已完成' : '进行中' }}</t-tag>
        </div>
      </div>
      <div v-else class="empty-hint">还没有自定义学习计划</div>
    </t-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { internApi } from '@/api'

const route = useRoute()
const data = ref({ phases: [], customTasks: [] })

onMounted(async () => {
  const id = route.params.intern_id || 1
  try {
    data.value = await internApi.getGrowthMap(id)
  } catch (e) {
    console.error(e)
  }
})

function hasTasks(p) { return p.dimensions?.some(d => (d.systemTasks?.length || 0) + (d.customTasks?.length || 0) > 0) }
function phaseProgress(p) {
  let done = 0, total = 0
  for (const d of p.dimensions || []) {
    for (const t of d.systemTasks || []) { total++; if (t.status === 'done') done++ }
    for (const t of d.customTasks || []) { total++; if (t.status === 'done') done++ }
  }
  return total ? Math.round(done / total * 100) : 0
}
function progressStatus(p) { return p.status === 'done' ? 'success' : 'active' }

function phaseStatusText(s) {
  return { pending: '未开始', 'in_progress': '进行中', done: '已完成', completed: '已完成', overdue: '逾期' }[s] || s
}
function taskTheme(s) {
  return { done: 'success', completed: 'success', in_progress: 'warning', pending: 'default', overdue: 'danger' }[s] || 'default'
}
function taskStatusLabel(s) {
  return { done: '已完成', completed: '已完成', in_progress: '进行中', pending: '待开始', overdue: '已逾期' }[s] || s
}
function dimName(n) {
  return { '技术': '技术能力', '业务': '业务理解', '协作': '协作沟通', '产出': '独立产出', '产品能力': '产品能力', '销售技能': '销售技能' }[n] || n
}
</script>

<style scoped>
.growth-map-page { padding-bottom: 40px; max-width: 960px; margin: 0 auto; }
.page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.page-header h2 { font-size: 18px; margin: 0; }

.phase-card { border-radius: 10px; padding: 20px; margin-bottom: 16px; border: 1px solid #e7e7e7; transition: all 0.25s; }
.phase-pending { background: #fafafa; opacity: 0.75; }
.phase-in-progress { background: linear-gradient(135deg, #f0f5ff 0%, #fff 100%); border-color: #c4d8ff; box-shadow: 0 2px 12px rgba(0,82,217,0.08); }
.phase-done { background: linear-gradient(135deg, #f0fff4 0%, #fff 100%); border-color: #b7e8c9; }

.phase-header { margin-bottom: 12px; }
.phase-title-row { display: flex; align-items: center; gap: 8px; }
.phase-badge[data-status="pending"] { background: #e7e7e7; color: #86909c; padding: 1px 8px; border-radius: 10px; font-size: 11px; }
.phase-badge[data-status="in-progress"] { background: #0052D9; color: #fff; padding: 1px 8px; border-radius: 10px; font-size: 11px; animation: pulse 2s infinite; }
.phase-badge[data-status="done"] { background: #00A870; color: #fff; padding: 1px 8px; border-radius: 10px; font-size: 11px; }
.phase-title-row h3 { font-size: 15px; margin: 0; }

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.7} }

.dim-table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }
.dim-table th { text-align: left; padding: 6px 10px; background: #f8fafd; color: #86909c; font-weight: 500; border-bottom: 1px solid #eee; }
.dim-table td { padding: 6px 10px; border-bottom: 1px solid #f5f5f5; vertical-align: middle; }
.dim-header td { background: #fafafa; color: #49546E; font-size: 12px; }
.task-desc { color: #86909c; font-size: 11.5px; }
.custom-task { opacity: 0.85; }
.custom-section { border-radius: 8px; margin-top: 8px; }

.custom-list { display: flex; flex-direction: column; gap: 8px; }
.custom-item { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 6px 0; border-bottom: 1px solid #f5f5f5; }
.empty-hint, .empty-phase { text-align: center; padding: 20px; color: #c9cdd4; font-size: 13px; }
</style>
