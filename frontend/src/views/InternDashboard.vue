<template>
  <div class="dashboard">
    <!-- 顶部 -->
    <div class="top-bar">
      <div class="top-left">
        <t-avatar size="40px">{{ (dashboard.intern?.name || '?')[0] }}</t-avatar>
        <div>
          <div class="top-name">{{ dashboard.intern?.name || '加载中...' }}</div>
          <div class="top-meta">
            第{{ dashboard.intern?.weekNum || '?' }}周 · 入职{{ dashboard.intern?.daysSinceEntry || 0 }}天
            · 总进度 {{ dashboard.completionRate || 0 }}%
          </div>
        </div>
        <t-tag :theme="stateTheme" variant="light">{{ dashboard.intern?.phase || '-' }}</t-tag>
        <t-tag v-if="dashboard.intern?.recruiterTag === 'LIGHTNING'" theme="success" variant="light">绩优闪电</t-tag>
        <t-tag v-if="dashboard.intern?.recruiterTag === 'RISK'" theme="danger" variant="light">红灯风险</t-tag>
      </div>
      <t-select v-model="selectedInternId" placeholder="切换实习生" size="small" style="width:200px"
        :options="internOptions" @change="switchIntern" />
    </div>

    <!-- 销售反向确认 -->
    <t-alert v-if="showReverseConfirm" theme="error" title="行为失联 · 请补录今日线下工作" :close="false" style="margin-bottom:16px">
      <template #message>
        <div style="font-size:13px;line-height:1.8;margin-bottom:8px">
          CRM 已 <b>48 小时</b>无数字足迹。AI 做 Copilot 真实性提示（非欺诈定罪），通过后解除阻断。
        </div>
        <t-textarea v-model="reverseConfirmText"
          placeholder="例：今日外呼 5 家（XX科技/YY金融），2 家意向，已约周三回访..."
          :autosize="{ minRows: 2, maxRows: 4 }" />
        <div style="margin-top:8px;display:flex;align-items:center;gap:12px">
          <t-button theme="primary" size="small" :disabled="!reverseConfirmText.trim()" @click="submitReverseConfirm">
            提交 Copilot 审计
          </t-button>
          <span v-if="lastReverseConfirmAt" style="font-size:12px;color:#86909c">上次提交：{{ lastReverseConfirmAt }}</span>
        </div>
      </template>
    </t-alert>

    <!-- 双栏 -->
    <div class="two-col">
      <!-- 左：任务列表 -->
      <div class="col">
        <t-card title="待办任务" :bordered="true">
          <div v-if="!currentTasks.length" style="text-align:center;padding:32px;color:#bbb">暂无待办任务</div>
          <div v-for="t in currentTasks" :key="t.id" class="task-item" :class="{ done: t.status === 'done' }" @click="onToggle(t)">
            <div class="cb-box" :class="{ checked: t.status === 'done' }">
              <svg v-if="t.status === 'done'" viewBox="0 0 24 24" width="14" height="14"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" fill="#fff"/></svg>
            </div>
            <div style="flex:1;min-width:0">
              <div class="task-title">{{ t.title }}</div>
              <div style="display:flex;gap:4px;margin-top:2px;flex-wrap:wrap">
                <t-tag size="small" variant="light">{{ t.dimension }}</t-tag>
                <t-tag v-if="t.duration" size="small" variant="light">{{ t.duration }}</t-tag>
                <t-tag v-if="t.source === 'mentor'" size="small" variant="light" theme="warning">导师</t-tag>
              </div>
            </div>
          </div>
        </t-card>

        <t-card title="自定义事项" :bordered="true" style="margin-top:16px">
          <template #actions>
            <t-button variant="text" size="small" @click="showAddDialog = true">+ 添加</t-button>
          </template>
          <div v-if="!customList.length" style="text-align:center;padding:24px;color:#bbb">还没有自定义事项</div>
          <div v-for="ct in customList" :key="ct.id" class="task-item" :class="{ done: ct.status === 'done' }" @click="onToggle(ct)">
            <div class="cb-box" :class="{ checked: ct.status === 'done' }">
              <svg v-if="ct.status === 'done'" viewBox="0 0 24 24" width="14" height="14"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" fill="#fff"/></svg>
            </div>
            <span style="flex:1;min-width:0">{{ ct.title }}</span>
            <t-tag v-if="ct.time" size="small" variant="light">{{ ct.time }}</t-tag>
          </div>
        </t-card>

        <!-- Copilot -->
        <t-card title="🤖 Copilot 提问" :bordered="true" style="margin-top:16px">
          <t-textarea v-model="copilotQuestion" placeholder="遇到卡点了？问问 Copilot..."
            :autosize="{ minRows: 2, maxRows: 4 }" />
          <t-button theme="primary" size="small" style="margin-top:8px"
            :disabled="!copilotQuestion.trim() || copilotLoading"
            :loading="copilotLoading" @click="askCopilot">提问</t-button>
          <div v-if="copilotAnswer" style="margin-top:12px;background:#f6f8fa;border-radius:6px;padding:12px;font-size:13px;line-height:1.8;white-space:pre-wrap">{{ copilotAnswer }}</div>
        </t-card>
      </div>

      <!-- 右：图表 + 状态 -->
      <div class="col">
        <!-- 绩效趋势 -->
        <t-card title="绩效趋势" :bordered="true" v-if="trendData.length">
          <div ref="chartRef" style="height:280px"></div>
        </t-card>

        <!-- AI 洞察 -->
        <t-card title="AI 洞察" :bordered="true" style="margin-top:16px">
          <div v-if="dashboard.stateMachine" style="font-size:13px;line-height:1.8">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              当前状态：<t-tag :theme="stateTheme" size="small">{{ dashboard.intern?.phase }}</t-tag>
              <span style="color:#0052D9;font-weight:500">{{ stateInsight }}</span>
            </div>

            <div v-if="dashboard.stateMachine.completed_events?.length" style="margin-top:8px">
              <div style="color:#86909c;font-size:12px;margin-bottom:4px">已完成里程碑</div>
              <t-tag v-for="e in dashboard.stateMachine.completed_events.slice(-3)" :key="e"
                size="small" theme="success" variant="light" style="margin:2px">{{ e }}</t-tag>
            </div>

            <div v-if="dashboard.stateMachine.next_milestones?.length" style="margin-top:8px">
              <div style="color:#86909c;font-size:12px;margin-bottom:4px">下一目标</div>
              <div v-for="m in dashboard.stateMachine.next_milestones.slice(0,3)" :key="m.name"
                style="padding:2px 0;font-size:13px">
                <t-icon name="flag" size="14px" style="margin-right:4px;color:#ED7B2F" />{{ m.name }}
              </div>
            </div>
          </div>
          <div v-else style="text-align:center;padding:24px;color:#bbb">暂无数据</div>
        </t-card>
      </div>
    </div>

    <!-- 弹窗 -->
    <t-dialog v-model:visible="showAddDialog" header="添加自定义事项" :confirm-btn="{ content: '确定' }" @confirm="handleAddCustom">
      <t-form :data="newTask">
        <t-form-item label="标题"><t-input v-model="newTask.title" placeholder="你想做什么？" /></t-form-item>
        <t-form-item label="时间"><t-input v-model="newTask.time" placeholder="例: 周末2h/周" /></t-form-item>
      </t-form>
    </t-dialog>

    <!-- Copilot 实时弹窗（白天轨响应） -->
    <div v-if="copilotPopup.visible" class="copilot-overlay" @click.self="copilotPopup.visible = false">
      <div class="copilot-modal">
        <div class="copilot-header">
          <span class="copilot-icon">⚠️</span>
          <span class="copilot-title">实习能量站 · Copilot 导航</span>
          <t-button theme="default" variant="text" size="small" @click="dismissCopilot" style="margin-left:auto">✕</t-button>
        </div>
        <div class="copilot-body">
          <div class="copilot-alert">
            {{ copilotPopup.message }}
          </div>
          <div v-if="copilotPopup.suggestion" class="copilot-suggestion">
            {{ copilotPopup.suggestion }}
          </div>
        </div>
        <div class="copilot-actions">
          <t-button theme="primary" size="small" @click="copilotAskMore">
            问我具体问题
          </t-button>
          <t-button theme="default" variant="outline" size="small" @click="dismissCopilot">
            稍后处理
          </t-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onBeforeUnmount } from 'vue'
import { Message } from 'tdesign-vue-next'
import { internApi } from '@/api'

const dashboard = ref({})
const internList = ref([])
const selectedInternId = ref(null)
const showAddDialog = ref(false)
const newTask = ref({ title: '', time: '' })
const chartRef = ref(null)
let chartInstance = null

const reverseConfirmText = ref('')
const lastReverseConfirmAt = ref('')
const copilotQuestion = ref('')
const copilotAnswer = ref('')
const copilotLoading = ref(false)

// Copilot 弹窗状态
const copilotPopup = ref({
  visible: false,
  message: '',
  suggestion: '',
  eventId: null,
})
let copilotTimer = null

// computed
const currentTasks = computed(() => dashboard.value.tasks || [])
const customList = computed(() => dashboard.value.customTasks || [])
const trendData = computed(() => dashboard.value.weeklyTrend || [])
const stateTheme = computed(() =>
  ({ ONBOARDING: 'primary', RAMP_UP: 'warning', INDEPENDENT: 'success' })[dashboard.value.intern?.currentState] || 'default'
)
const stateInsight = computed(() => ({
  ONBOARDING: '熟悉环境与规范，保持学习节奏',
  RAMP_UP: '进入上手期，开始独立承担小需求',
  INDEPENDENT: '独立期，可承担核心模块 Owner',
})[dashboard.value.intern?.currentState] || '')
const showReverseConfirm = computed(() =>
  dashboard.value.intern?.jobFamily === 'SALES' &&
  dashboard.value.intern?.recruiterTag === 'RISK'
)
const internOptions = computed(() =>
  (internList.value || []).map(i => ({ label: `${i.name} (${i.jobFamily})`, value: i.id }))
)

async function loadData(id) {
  try {
    dashboard.value = await internApi.getDashboard(id) || {}
    await nextTick()
    drawChart()
  } catch (e) { dashboard.value = {} }
}
async function loadInternList() {
  try {
    internList.value = (await internApi.listInterns()) || []
    if (!selectedInternId.value && internList.value.length) selectedInternId.value = internList.value[0].id
  } catch (e) { internList.value = [] }
}
function switchIntern(id) { loadData(id) }

async function onToggle(task) {
  // 根据当前状态决定目标状态
  const isDone = task.status === 'done'
  const newStatus = isDone ? 'in_progress' : 'done'
  const oldStatus = task.status
  task.status = newStatus
  try {
    await internApi.toggleTask(task.id)
    Message.success(isDone ? '已取消完成' : '已完成 ✓')
  } catch (e) {
    task.status = oldStatus
    Message.error('操作失败，请重试')
  }
}

async function handleAddCustom() {
  if (!newTask.value.title.trim()) return
  await internApi.addCustomTask({ title: newTask.value.title, time: newTask.value.time })
  showAddDialog.value = false
  newTask.value = { title: '', time: '' }
  Message.success('已添加')
  loadData(selectedInternId.value)
}

async function submitReverseConfirm() {
  if (!reverseConfirmText.value.trim()) return
  try {
    const r = await internApi.submitReverseConfirm(selectedInternId.value, reverseConfirmText.value)
    if (r.passed) {
      Message.success('Copilot：话术可信，阻断已解除')
      lastReverseConfirmAt.value = new Date().toLocaleString('zh-CN')
      reverseConfirmText.value = ''
    } else Message.error(r.reason)
  } catch (e) { Message.error('提交失败') }
}

async function askCopilot() {
  const q = copilotQuestion.value.trim()
  if (!q) return
  copilotLoading.value = true
  copilotAnswer.value = ''
  await new Promise(r => setTimeout(r, 800))
  copilotAnswer.value = `关于「${q.slice(0,30)}...」：
1. 先查阅团队 Wiki 知识库
2. 在工蜂 Issue 里搜索类似问题
3. 如仍卡住，建议问导师～`
  copilotLoading.value = false
}

function drawChart() {
  if (!chartRef.value || !trendData.value.length) return
  import('echarts').then(echarts => {
    if (chartInstance) { chartInstance.dispose(); chartInstance = null }
    chartInstance = echarts.init(chartRef.value)
    const d = trendData.value
    const jf = dashboard.value.intern?.jobFamily
    const weeks = d.map(x => x.week?.slice(5))

    let series = [], yAxis = []
    if (jf === 'RD') {
      series = [
        { name: 'Commits', type: 'line', data: d.map(x => x.commits), smooth: true, symbol: 'circle', symbolSize: 4 },
        { name: 'PR合入', type: 'line', data: d.map(x => x.prs), smooth: true, symbol: 'diamond', symbolSize: 4 },
        { name: 'Bug修复', type: 'line', data: d.map(x => x.bugs), smooth: true, symbol: 'triangle', symbolSize: 4 },
      ]
      yAxis = [{ type: 'value' }]
    } else if (jf === 'SALES') {
      series = [
        { name: '线索', type: 'bar', data: d.map(x => x.leadsTouched), barWidth: '40%' },
        { name: '通话(分)', type: 'line', data: d.map(x => x.callDuration), smooth: true, yAxisIndex: 1 },
      ]
      yAxis = [{ type: 'value' }, { type: 'value' }]
    }

    chartInstance.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      grid: { top: 10, bottom: 30, left: 50, right: 20 },
      xAxis: { type: 'category', data: weeks, axisLabel: { fontSize: 10 } },
      yAxis, series,
      color: ['#0052D9', '#ED7B2F', '#00A870'],
      animationDuration: 400,
    })
  })
}

watch(trendData, () => nextTick(drawChart))

onMounted(async () => {
  await loadInternList()
  if (selectedInternId.value) loadData(selectedInternId.value)
  // 启动 Copilot 轮询（每 5 秒检查一次活跃崩溃事件）
  startCopilotPolling()
})
onBeforeUnmount(() => {
  if (chartInstance) { chartInstance.dispose(); chartInstance = null }
  stopCopilotPolling()
})

// ============================================================
// Copilot 弹窗逻辑（白天轨实时响应）
// ============================================================

function startCopilotPolling() {
  stopCopilotPolling()
  checkCopilot()  // 立即检查一次
  copilotTimer = setInterval(checkCopilot, 5000)
}

function stopCopilotPolling() {
  if (copilotTimer) {
    clearInterval(copilotTimer)
    copilotTimer = null
  }
}

async function checkCopilot() {
  if (!selectedInternId.value) return
  try {
    const res = await internApi.getActiveBreakdowns(selectedInternId.value)
    if (res.hasActive && res.events?.length) {
      const event = res.events[0]
      const resp = event.copilotResponse || {}
      copilotPopup.value = {
        visible: true,
        message: resp.copilot_text || resp.root_cause || '检测到异常行为，AI 正在分析...',
        suggestion: resp.suggestion || '',
        eventId: event.id,
      }
    }
  } catch (e) {
    // 静默失败，不影响主流程
  }
}

function dismissCopilot() {
  copilotPopup.value.visible = false
  if (copilotPopup.value.eventId) {
    internApi.dismissBreakdown(selectedInternId.value, copilotPopup.value.eventId)
      .catch(() => {})
  }
}

function copilotAskMore() {
  copilotPopup.value.visible = false
  // 滚动到 Copilot 提问区域
  const el = document.querySelector('.col .t-card:nth-child(3)')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  // 聚焦到提问输入框
  setTimeout(() => {
    const textarea = document.querySelector('.col .t-card:nth-child(3) textarea')
    if (textarea) textarea.focus()
  }, 300)
}
</script>

<style scoped>
.dashboard { max-width: 1100px; margin: 0 auto; padding-bottom: 40px; }

.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  background: #0052D9; border-radius: 8px; padding: 20px 24px;
  color: #fff; margin-bottom: 16px;
}
.top-left { display: flex; align-items: center; gap: 12px; }
.top-name { font-size: 17px; font-weight: 700; }
.top-meta { font-size: 12px; opacity: 0.8; margin-top: 2px; }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 800px) { .two-col { grid-template-columns: 1fr; } }

.task-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 0; border-bottom: 1px solid #f3f3f3;
  cursor: pointer;
  transition: background 0.15s;
}
.task-item:hover { background: #fafafa; margin: 0 -12px; padding: 10px 12px; border-radius: 6px; }
.task-item:last-child { border-bottom: none; }
.task-item.done .task-title { text-decoration: line-through; color: #999; }
.task-title { font-size: 14px; color: #1d2129; }

/* 纯 div 勾选框 — 零依赖，100% 可靠 */
.cb-box {
  width: 18px; height: 18px; min-width: 18px;
  border: 2px solid #c9cdd4; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; transition: all 0.15s ease;
}
.task-item:hover .cb-box { border-color: #0052D9; }
.cb-box.checked {
  background: #0052D9; border-color: #0052D9;
}

/* Copilot 弹窗 */
.copilot-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.copilot-modal {
  background: #fff;
  border-radius: 12px;
  width: 480px;
  max-width: 90vw;
  box-shadow: 0 12px 48px rgba(0,0,0,0.25);
  overflow: hidden;
  animation: slideUp 0.25s ease;
}
@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
.copilot-header {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  background: #f0f5ff;
  border-bottom: 1px solid #d4e3ff;
  gap: 8px;
}
.copilot-icon {
  font-size: 20px;
}
.copilot-title {
  font-size: 15px;
  font-weight: 600;
  color: #0052d9;
}
.copilot-body {
  padding: 20px;
}
.copilot-alert {
  background: #fff3e0;
  border-left: 4px solid #ed7b2f;
  padding: 12px 16px;
  border-radius: 6px;
  font-size: 14px;
  line-height: 1.7;
  color: #4a2600;
  white-space: pre-wrap;
}
.copilot-suggestion {
  margin-top: 12px;
  padding: 12px 16px;
  background: #f6f8fa;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: #333;
}
.copilot-actions {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: #f9f9f9;
  border-top: 1px solid #eee;
  justify-content: flex-end;
}
</style>
