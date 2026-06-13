<template>
  <div class="growth-map-page">
    <div class="page-header">
      <t-button theme="default" variant="outline" size="small" @click="$router.push('/intern')">
        <template #icon><t-icon name="chevron-left" /></template>返回看板
      </t-button>
      <h2>{{ data.name }} 的成长地图</h2>
    </div>

    <!-- ===== DAG 状态机拓扑图 ===== -->
    <div class="dag-section">
      <h3 class="section-title">⚡ 状态机 DAG 拓扑（事件驱动，非打勾）</h3>
      <p class="dag-subtitle">当前状态：<t-tag :theme="stateTheme(data.currentState)" variant="light">{{ stateLabel(data.currentState) }}</t-tag>，打标：<t-tag :theme="tagTheme(data.recruiterTag)" size="small" variant="light">{{ tagLabel(data.recruiterTag) }}</t-tag></p>

      <div class="dag-graph">
        <!-- DAG 节点: ONBOARDING → RAMP_UP → INDEPENDENT -->
        <div class="dag-node-wrapper" v-for="(node, idx) in dagNodes" :key="node.state">
          <!-- 前置边 -->
          <div v-if="idx > 0" class="dag-edge" :class="{ active: dagNodes[idx-1].status === 'completed' }">
            <div class="edge-line"></div>
            <div class="edge-arrow">▶</div>
          </div>

          <div :class="['dag-node', node.status]">
            <div class="node-icon">
              <t-icon v-if="node.status === 'completed'" name="check-circle-filled" size="28px" />
              <t-icon v-else-if="node.status === 'active'" name="loading" size="28px" />
              <t-icon v-else name="circle" size="28px" />
            </div>
            <div class="node-body">
              <div class="node-title">{{ node.name }}</div>
              <div class="node-meta">{{ node.statusText }}</div>
              <t-progress v-if="node.status === 'active'" :percentage="node.progress" :color="{ from: '#0052D9', to: '#00A870' }" :stroke-width="6" style="max-width:200px;margin-top:4px" />
            </div>
          </div>
        </div>
      </div>

      <!-- 当前阶段的里程碑 DAG 子图 -->
      <div v-if="currentMilestones.length > 0" class="milestone-dag">
        <h4 class="ms-title">{{ data.currentState === 'INDEPENDENT' ? '🏆' : data.currentState === 'RAMP_UP' ? '📈' : '🏁' }} 当前阶段里程碑（{{ data.completedCount }}/{{ data.totalCount }}）</h4>
        <div class="ms-grid">
          <div v-for="ms in currentMilestones" :key="ms.name" :class="['ms-node', ms.done ? 'done' : 'pending']">
            <div class="ms-dot">
              <t-icon :name="ms.done ? 'check-circle-filled' : 'error-circle'" :size="ms.done ? '18px' : '16px'" />
            </div>
            <div class="ms-info">
              <div class="ms-name">{{ ms.name }}</div>
              <div class="ms-event">触发条件：{{ ms.triggerEvent }} × {{ ms.requiredCount }}</div>
              <div class="ms-progress-bar">
                <div class="ms-fill" :style="{ width: ms.progressPct + '%' }" :class="{ done: ms.done }"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 后续阶段预览 (折叠) -->
    <t-collapse v-if="futurePhases.length > 0" class="future-collapse">
      <t-collapse-panel header="🗓️ 后续阶段里程碑预览" value="future">
        <div v-for="(phase, pi) in futurePhases" :key="pi" style="margin-bottom:12px">
          <div style="font-size:13px;font-weight:600;color:#555;margin-bottom:6px">
            {{ phase.name }}（{{ phase.milestones.length }} 个里程碑）
          </div>
          <div class="ms-grid" style="opacity:0.7">
            <div v-for="ms in phase.milestones" :key="ms.name" class="ms-node pending" style="pointer-events:none">
              <div class="ms-dot"><t-icon name="lock-on" size="14px" /></div>
              <div class="ms-info">
                <div class="ms-name">{{ ms.name }}</div>
                <div class="ms-event">触发条件：{{ ms.triggerEvent }} × {{ ms.requiredCount }}</div>
              </div>
            </div>
          </div>
        </div>
      </t-collapse-panel>
    </t-collapse>

    <!-- 绩效趋势图 (数据驱动，非AI决策) -->
    <t-card title="📊 绩效趋势（纯数据快照，非AI打分）" bordered class="chart-section" v-if="hasSnapshots">
      <div ref="chartRef" style="width:100%;height:280px"></div>
    </t-card>

    <!-- 自定义学习计划 -->
    <t-card title="📝 自定义学习计划" bordered class="custom-section">
      <div v-if="data.customTasks?.length > 0" class="custom-list">
        <div v-for="ct in data.customTasks" :key="ct.id" class="custom-item">
          <t-tag :theme="ct.status === 'done' ? 'success' : 'warning'" size="small" variant="light">
            {{ ct.status === 'done' ? '✓' : '…' }}
          </t-tag>
          <span>{{ ct.title }}</span>
          <t-tag v-if="ct.time" size="small" variant="outline">{{ ct.time }}</t-tag>
        </div>
      </div>
      <div v-else class="empty-hint">还没有自定义学习计划</div>
    </t-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { internApi } from '@/api'

const route = useRoute()
const chartRef = ref(null)
const data = ref({
  name: '', currentState: 'ONBOARDING', recruiterTag: 'STEADY',
  jobFamily: 'RD', completedCount: 0, totalCount: 0,
  phases: [], customTasks: [], snapshots: []
})

const dagNodes = ref([])
const currentMilestones = ref([])
const futurePhases = ref([])

onMounted(async () => {
  const id = route.params.intern_id || 1
  try {
    const res = await internApi.getGrowthMap(id)
    data.value = res
    buildDAG(res)
    // Build chart after DOM ready
    nextTick(() => buildChart(res))
  } catch (e) { console.error(e) }
})

// ===== DAG 构建 =====
function buildDAG(res) {
  const stateOrder = ['ONBOARDING', 'RAMP_UP', 'INDEPENDENT']
  const stateNames = { ONBOARDING: '融入期', RAMP_UP: '上手期', INDEPENDENT: '独立期' }
  const currentIdx = stateOrder.indexOf(res.currentState)

  dagNodes.value = stateOrder.map((s, idx) => {
    let status, statusText, progress = 0
    if (idx < currentIdx) {
      status = 'completed'
      statusText = '✅ 已完成'
      progress = 100
    } else if (idx === currentIdx) {
      status = 'active'
      statusText = `⚡ 进行中 · ${res.completedCount}/${res.totalCount}`
      progress = res.totalCount > 0 ? Math.round(res.completedCount / res.totalCount * 100) : 0
    } else {
      status = 'pending'
      statusText = '🔒 待解锁'
      progress = 0
    }
    return { state: s, name: stateNames[s], status, statusText, progress }
  })

  // 当前阶段里程碑
  const currentPhase = (res.phases || []).find(p => p.status === 'in_progress' || p.status === 'pending')
  if (currentPhase) {
    currentMilestones.value = (currentPhase.dimensions || []).flatMap(dim =>
      (dim.systemTasks || []).concat(dim.customTasks || [])
    ).slice(0, 8).map(ms => ({
      name: ms.title || ms.name || '',
      triggerEvent: ms.source || 'system',
      requiredCount: 1,
      done: ms.status === 'done' || ms.status === 'completed',
      progressPct: ms.status === 'done' || ms.status === 'completed' ? 100 : 0
    }))
  }

  // 后续阶段预览
  futurePhases.value = (res.phases || [])
    .filter(p => p.status === 'pending')
    .slice(0, 2)
    .map(p => ({
      name: p.name,
      milestones: (p.dimensions || []).flatMap(d =>
        (d.systemTasks || []).concat(d.customTasks || [])
      ).slice(0, 4).map(ms => ({
        name: ms.title || ms.name || '',
        triggerEvent: ms.source || 'system',
        requiredCount: 1
      }))
    }))
}

// ===== 绩效趋势图（ECharts） =====
const hasSnapshots = ref(false)
async function buildChart(res) {
  const snaps = res.snapshots || []
  if (snaps.length === 0 || !chartRef.value) return
  hasSnapshots.value = true
  const echartsModule = await import('echarts')
  const echarts = echartsModule.default || echartsModule
  const chart = echarts.init(chartRef.value)
  const dates = snaps.map(s => s.snapshot_date || s.date || '')
  const colors = ['#0052D9', '#00A870', '#E37318']
  const series = []

  if (res.jobFamily === 'RD' || res.jobFamily === 'RD') {
    series.push(
      { name: 'Commit数', type: 'line', data: snaps.map(s => s.commit_count || s.commits || 0), smooth: true, symbol: 'circle', symbolSize: 6, lineStyle: { color: colors[0], width: 2 }, itemStyle: { color: colors[0] } },
      { name: 'PR合入', type: 'line', data: snaps.map(s => s.pr_merged_count || s.prs || 0), smooth: true, symbol: 'diamond', symbolSize: 7, lineStyle: { color: colors[1], width: 2 }, itemStyle: { color: colors[1] } },
      { name: 'Bug修复', type: 'bar', data: snaps.map(s => s.bug_resolved_count || s.bugs || 0), barWidth: 12, itemStyle: { color: colors[2], borderRadius: [4, 4, 0, 0] } }
    )
  } else if (res.jobFamily === 'SALES') {
    series.push(
      { name: '触达线索', type: 'bar', data: snaps.map(s => s.crm_leads_touched || s.leadsTouched || 0), barWidth: 16, itemStyle: { color: colors[0], borderRadius: [4, 4, 0, 0] } },
      { name: '通话时长(min)', type: 'line', data: snaps.map(s => Math.round((s.effective_call_duration || s.callDurationMin || 0) / 60) || (s.callDurationMin || 0)), smooth: true, symbol: 'circle', symbolSize: 6, yAxisIndex: 1, lineStyle: { color: colors[1], width: 2 } }
    )
  }

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    grid: { top: 15, right: res.jobFamily === 'SALES' ? 50 : 15, bottom: 35, left: 15 },
    xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10, rotate: 30 } },
    yAxis: [
      { type: 'value', name: '数量', axisLabel: { fontSize: 10 } },
      ...(res.jobFamily === 'SALES' ? [{ type: 'value', name: '分钟', axisLabel: { fontSize: 10 } }] : [])
    ],
    series
  })
}

// Helpers
function stateLabel(s) {
  return { ONBOARDING: '融入期', RAMP_UP: '上手期', INDEPENDENT: '独立期' }[s] || s
}
function stateTheme(s) {
  return { ONBOARDING: 'warning', RAMP_UP: 'primary', INDEPENDENT: 'success' }[s] || 'default'
}
function tagLabel(t) {
  return { LIGHTNING: '⚡绩优闪电', STEADY: '正常稳健', RISK: '⚠️红灯风险' }[t] || t
}
function tagTheme(t) {
  return { LIGHTNING: 'success', STEADY: 'default', RISK: 'danger' }[t] || 'default'
}
</script>

<style scoped>
.growth-map-page { padding-bottom: 40px; max-width: 960px; margin: 0 auto; }
.page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.page-header h2 { font-size: 18px; margin: 0; }

/* DAG Section */
.dag-section { background: linear-gradient(135deg, #f8faff 0%, #fff 100%); border-radius: 12px; padding: 24px; margin-bottom: 20px; border: 1px solid #e0e7ff; }
.section-title { font-size: 16px; margin: 0 0 4px; color: #1d2129; }
.dag-subtitle { font-size: 12px; color: #86909c; margin: 0 0 20px; }

.dag-graph { display: flex; align-items: center; gap: 0; justify-content: center; margin-bottom: 24px; flex-wrap: wrap; }
.dag-node-wrapper { display: flex; align-items: center; }
.dag-edge { display: flex; align-items: center; gap: 0; opacity: 0.3; transition: all 0.5s; }
.dag-edge.active { opacity: 1; }
.edge-line { width: 40px; height: 2px; background: linear-gradient(90deg, #00a870, #0052d9); border-radius: 1px; }
.edge-arrow { color: #0052d9; font-size: 14px; margin-left: -2px; }
.dag-node { display: flex; align-items: center; gap: 12px; padding: 16px 20px; border-radius: 12px; background: #f5f5f5; border: 2px solid #e7e7e7; min-width: 180px; transition: all 0.35s; }
.dag-node.completed { background: linear-gradient(135deg, #e6fff0, #f0fff4); border-color: #00a870; }
.dag-node.completed .node-icon { color: #00a870; }
.dag-node.active { background: linear-gradient(135deg, #e8f0ff, #f0f5ff); border-color: #0052d9; box-shadow: 0 2px 16px rgba(0,82,217,0.15); }
.dag-node.active .node-icon { color: #0052d9; animation: spin 2s linear infinite; }
.dag-node.pending { opacity: 0.55; }
.node-icon { flex-shrink: 0; }
.node-title { font-size: 15px; font-weight: 700; color: #1d2129; }
.node-meta { font-size: 11px; color: #86909c; margin-top: 2px; }
@keyframes spin { 0%{transform:rotate(0)} 100%{transform:rotate(360deg)} }

/* Milestone sub-DAG */
.milestone-dag { border-top: 1px dashed #d0d5ff; padding-top: 20px; }
.ms-title { font-size: 14px; margin: 0 0 14px; color: #49546e; }
.ms-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }
.ms-node { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 8px; border: 1px solid #e7e7e7; background: #fff; transition: all 0.25s; }
.ms-node.done { border-color: #b7ebc9; background: #f6fff9; }
.ms-node.pending { opacity: 0.7; }
.ms-dot { flex-shrink: 0; }
.ms-node.done .ms-dot { color: #00a870; }
.ms-node.pending .ms-dot { color: #c9cdd4; }
.ms-info { flex: 1; min-width: 0; }
.ms-name { font-size: 13px; font-weight: 600; color: #1d2129; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ms-event { font-size: 11px; color: #86909c; margin-top: 2px; }
.ms-progress-bar { margin-top: 6px; height: 4px; background: #eee; border-radius: 2px; overflow: hidden; }
.ms-fill { height: 100%; background: #e0e0e0; border-radius: 2px; transition: width 0.6s; }
.ms-fill.done { background: linear-gradient(90deg, #0052d9, #00a870); }

/* Future phases collapse */
.future-collapse { margin-bottom: 20px; border-radius: 8px; }

/* Chart */
.chart-section { border-radius: 8px; margin-bottom: 20px; }

/* Custom tasks */
.custom-section { border-radius: 8px; }
.custom-list { display: flex; flex-direction: column; gap: 8px; }
.custom-item { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 6px 0; border-bottom: 1px solid #f5f5f5; }
.empty-hint { text-align: center; padding: 40px; color: #c9cdd4; font-size: 13px; }
</style>
