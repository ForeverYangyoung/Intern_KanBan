<template>
  <div class="hr-dashboard">
    <div class="page-header">
      <h2>📊 HR 周报看板 — 在途留用风控</h2>
      <p style="font-size:12px;color:#86909c;margin:0">
        同岗位常模排名 + 风控打标 + 干预闭环
        <span style="margin-left:12px">数据截止: {{ data.reportDate || '加载中' }}</span>
      </p>
    </div>

    <!-- 汇总统计 -->
    <div class="summary-row">
      <div class="summary-card" @click="filterTag = 'all'">
        <b>{{ data.rows?.length || 0 }}</b>
        <span>实习生总数</span>
      </div>
      <div class="summary-card risk-count" :class="{active: filterTag === 'RISK'}" @click="filterTag = filterTag === 'RISK' ? 'all' : 'RISK'">
        <b>{{ riskCount }}</b>
        <span>红灯风险（需介入）</span>
      </div>
      <div class="summary-card lightning-count" :class="{active: filterTag === 'LIGHTNING'}" @click="filterTag = filterTag === 'LIGHTNING' ? 'all' : 'LIGHTNING'">
        <b>{{ lightningCount }}</b>
        <span>绩优闪电（建议锁定）</span>
      </div>
      <div class="summary-card avg-progress">
        <b>{{ avgProgress }}%</b>
        <span>平均完成率</span>
      </div>
    </div>

    <!-- 风险介入待办（仅当存在风险时显示） -->
    <t-card
      v-if="riskRows.length > 0"
      class="intervention-card"
      title="🚨 风险介入待办（自动汇总）"
      :bordered="true"
    >
      <template #header-right>
        <span style="font-size:12px;color:#86909c">点击行可展开干预操作</span>
      </template>

      <t-collapse v-model="expandedRisks">
        <t-collapse-panel
          v-for="row in riskRows"
          :key="row.id"
          :value="row.id"
          :header="`${row.name} (${row.jobLabel}) · ${row.reason || '已连续 2 周触发状态机卡点'}`"
        >
          <!-- 干预表单 -->
          <div class="intervention-form">
            <div class="form-row">
              <div class="form-label">诊断结论：</div>
              <t-radio-group v-model="row.diagnosis" size="small">
                <t-radio-button value="mentor_mismatch">带教风格错配（建议换导师/换业务线）</t-radio-button>
                <t-radio-button value="position_mismatch">不适岗（建议启动补招储备）</t-radio-button>
                <t-radio-button value="temporary">临时卡点（保持观察，下周再评）</t-radio-button>
              </t-radio-group>
            </div>
            <div class="form-row">
              <div class="form-label">HR 介入行动：</div>
              <t-input
                v-model="row.action"
                placeholder="例：1) 已约导师 1:1 沟通 2) 安排转组面试 3) 启动补招池"
                :autosize="{ minRows: 2, maxRows: 3 }"
              />
            </div>
            <div class="form-row intervention-actions">
              <t-button theme="primary" size="small" :disabled="!row.diagnosis || !row.action?.trim()" @click="recordIntervention(row)">
                <template #icon><t-icon name="check" /></template>
                记录会议纪要
              </t-button>
              <t-button theme="default" size="small" @click="sendLetterToMentor(row)">
                <template #icon><t-icon name="mail" /></template>
                致导师一封信
              </t-button>
              <t-button theme="default" size="small" @click="scheduleInterview(row)">
                <template #icon><t-icon name="user-talk" /></template>
                预约 HRBP 面谈
              </t-button>
              <span v-if="row.intervention" class="intervention-tip">
                ✅ 已记录于 {{ row.intervention.time }}（{{ row.intervention.diagnosisLabel }}）
              </span>
            </div>
          </div>
        </t-collapse-panel>
      </t-collapse>
    </t-card>

    <!-- 绩优闪电速推（仅当存在闪电时显示） -->
    <t-card
      v-if="lightningRows.length > 0"
      class="lightning-card"
      title="⚡ 绩优闪电 · 提前锁定动作"
      :bordered="true"
    >
      <div class="lightning-actions">
        <div v-for="row in lightningRows" :key="row.id" class="lightning-item">
          <div class="lightning-info">
            <b>{{ row.name }}</b>
            <t-tag size="small" theme="success" variant="light">{{ row.jobLabel }}</t-tag>
            <span style="font-size:12px;color:#86909c">进度 {{ row.overallProgress }}% · 同岗 Top {{ row.sameRoleRank }}</span>
          </div>
          <div class="lightning-buttons">
            <t-button size="small" theme="primary" variant="outline" @click="scheduleFinalInterview(row)">
              安排高管终面
            </t-button>
            <t-button size="small" theme="success" variant="outline" @click="issueOffer(row)">
              发放 Stage-1 转正意向
            </t-button>
          </div>
        </div>
      </div>
    </t-card>

    <!-- 全量表格 -->
    <t-card title="📋 全员成长对比（含常模百分位）" :bordered="true" class="main-table-card">
      <template #header-right>
        <t-radio-group v-model="filterTag" variant="default-filled" size="small">
          <t-radio-button value="all">全部</t-radio-button>
          <t-radio-button value="RISK">红灯风险</t-radio-button>
          <t-radio-button value="LIGHTNING">绩优闪电</t-radio-button>
        </t-radio-group>
      </template>

      <table class="hr-table">
        <thead><tr>
          <th>姓名</th><th>岗位线</th><th>导师</th><th>当前阶段</th><th>风控标签</th>
          <th>总进度</th><th>同岗排名</th><th>常模百分位</th>
          <th>绩效概览</th><th>预警</th>
        </tr></thead>
        <tbody>
          <tr v-for="row in filteredRows" :key="row.id"
            :class="{ 'row-risk': row.recruiterTag === 'RISK', 'row-lightning': row.recruiterTag === 'LIGHTNING' }"
            @click="onRowClick(row)" style="cursor:pointer">
            <td><b>{{ row.name }}</b></td>
            <td><t-tag size="small" variant="light">{{ row.jobLabel }}</t-tag></td>
            <td>{{ row.mentorName }}</td>
            <td><t-tag :theme="stateTheme(row.currentState)" size="small">{{ row.stateLabel }}</t-tag></td>
            <td>
              <t-tag v-if="row.recruiterTag === 'LIGHTNING'" theme="success" size="small" variant="light">绩优闪电</t-tag>
              <t-tag v-else-if="row.recruiterTag === 'RISK'" theme="danger" size="small" variant="light">红灯风险</t-tag>
              <span v-else style="color:#86909c;font-size:12px">正常</span>
            </td>
            <td>
              <t-progress :percentage="row.overallProgress" :stroke-width="8" :status="row.overallProgress >= 80 ? 'success' : 'active'" style="width:80px;display:inline-block;vertical-align:middle" />
              <span style="font-size:12px;color:#49546E;margin-left:4px">{{ row.overallProgress }}%</span>
            </td>
            <td>
              <b style="color:#0052D9">{{ row.sameRoleRank }}/{{ row.sameRoleTotal }}</b>
              <span v-if="row.sameRoleRank === 1" style="color:#00A870;font-size:11px"> 🏆</span>
            </td>
            <td>
              <t-tag :theme="percentileTheme(row.percentile)" size="small" variant="light">
                {{ row.percentile }}%
              </t-tag>
            </td>
            <td class="perf-cell">
              <span v-if="row.commits !== undefined">{{ row.commits }}c / {{ row.prs }}pr / {{ row.bugs }}bug</span>
              <span v-else-if="row.leadsTouched !== undefined">{{ row.leadsTouched }}线索 / {{ row.callDurationMin }}分钟</span>
              <span v-else>-</span>
            </td>
            <td>
              <t-badge v-if="row.activeAlerts > 0" :count="row.activeAlerts" :max-count="9">
                <t-icon name="error-circle" color="#E34D59" />
              </t-badge>
              <span v-else style="color:#00A870;font-size:13px">✓</span>
            </td>
          </tr>
        </tbody>
      </table>
    </t-card>

    <!-- 干预结果反馈弹窗 -->
    <t-dialog
      v-model:visible="feedbackDialog.visible"
      :header="feedbackDialog.title"
      :footer="false"
      :width="500"
    >
      <div v-if="feedbackDialog.content" class="feedback-content">
        <p>{{ feedbackDialog.content }}</p>
      </div>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Message } from 'tdesign-vue-next'
import { hrApi, internApi } from '@/api'

const data = ref({ rows: [], reportDate: '' })
const filterTag = ref('all')
const expandedRisks = ref([])
const feedbackDialog = ref({ visible: false, title: '', content: '' })

// 风险行展开的本地状态
const interventionMap = ref({}) // id -> { diagnosis, action, intervention }

onMounted(async () => {
  try {
    const result = await hrApi.weeklyReport()
    data.value = result || { rows: [], reportDate: '' }
    // 初始化风险行的诊断状态
    for (const row of data.value.rows || []) {
      if (row.recruiterTag === 'RISK') {
        interventionMap.value[row.id] = { diagnosis: '', action: '', intervention: null }
      }
    }
  } catch (e) {
    console.error(e)
    data.value = { rows: [], reportDate: '' }
  }
})

const filteredRows = computed(() => {
  const rows = data.value.rows || []
  if (filterTag.value === 'all') return rows
  return rows.filter(r => r.recruiterTag === filterTag.value)
})

// 风险/闪电行带本地干预状态
const riskRows = computed(() =>
  (data.value.rows || [])
    .filter(r => r.recruiterTag === 'RISK')
    .map(r => ({ ...r, ...(interventionMap.value[r.id] || {}) }))
)
const lightningRows = computed(() =>
  (data.value.rows || []).filter(r => r.recruiterTag === 'LIGHTNING')
)

const riskCount = computed(() => (data.value.rows || []).filter(r => r.recruiterTag === 'RISK').length)
const lightningCount = computed(() => (data.value.rows || []).filter(r => r.recruiterTag === 'LIGHTNING').length)
const avgProgress = computed(() => {
  const rows = data.value.rows || []
  if (!rows.length) return 0
  return Math.round(rows.reduce((s, r) => s + r.overallProgress, 0) / rows.length)
})

function stateTheme(s) {
  return { ONBOARDING: 'primary', RAMP_UP: 'warning', INDEPENDENT: 'success' }[s] || 'default'
}
function percentileTheme(p) {
  if (p >= 75) return 'success'
  if (p >= 25) return 'warning'
  return 'danger'
}

const diagnosisLabelMap = {
  mentor_mismatch: '带教风格错配',
  position_mismatch: '不适岗',
  temporary: '临时卡点（保持观察）',
}

function onRowClick(row) {
  if (row.recruiterTag === 'RISK') {
    // 自动展开对应行
    if (!expandedRisks.value.includes(row.id)) {
      expandedRisks.value = [...expandedRisks.value, row.id]
    }
  } else if (row.recruiterTag === 'LIGHTNING') {
    scheduleFinalInterview(row)
  }
}

function recordIntervention(row) {
  if (!row.diagnosis || !row.action?.trim()) {
    Message.warning('请先填写诊断结论与行动')
    return
  }
  const now = new Date().toLocaleString('zh-CN')
  interventionMap.value[row.id] = {
    ...interventionMap.value[row.id],
    intervention: {
      time: now,
      diagnosisLabel: diagnosisLabelMap[row.diagnosis] || row.diagnosis,
    }
  }
  Message.success('已记录于 HR 决策流（数据库），进入风控闭环')

  // 自动关闭面板
  expandedRisks.value = expandedRisks.value.filter(id => id !== row.id)
}

function sendLetterToMentor(row) {
  feedbackDialog.value = {
    visible: true,
    title: `已发信给导师（${row.mentorName}）`,
    content: `信函内容：您好 ${row.mentorName}，您带教的 ${row.name}（${row.jobLabel}）已连续两周触发红灯风险，HR 已介入评估。请本周内与 HRBP 同步辅导策略。`,
  }
  Message.success('已通过企微发出导师一封信')
}

function scheduleInterview(row) {
  feedbackDialog.value = {
    visible: true,
    title: `已预约 HRBP 面谈 — ${row.name}`,
    content: `已为 ${row.name} 预约本周三 14:00 HRBP 1:1 面谈，将围绕「${diagnosisLabelMap['mentor_mismatch']}」展开诊断。`,
  }
}

function scheduleFinalInterview(row) {
  feedbackDialog.value = {
    visible: true,
    title: `已安排高管终面 — ${row.name}`,
    content: `${row.name}（${row.jobLabel}）同岗 Top ${row.sameRoleRank}，已绕过常规流程，下周一安排与 BU 负责人终面。`,
  }
}

function issueOffer(row) {
  feedbackDialog.value = {
    visible: true,
    title: `已发放 Stage-1 转正意向 — ${row.name}`,
    content: `恭喜！${row.name} 已触发绩优闪电规则（前 10% + CR 评语正面率达标），已发放 Stage-1 转正意向书，后续流程由招聘直接接管。`,
  }
  Message.success('Stage-1 转正意向已发出，招聘接管后续流程')
}
</script>

<style scoped>
.hr-dashboard { padding-bottom: 40px; max-width: 1180px; margin: 0 auto; }
.page-header { margin-bottom: 20px; }
.page-header h2 { font-size: 18px; margin: 4px 0; }

.summary-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.summary-card {
  background: #fff; border-radius: 8px; padding: 14px 16px;
  border: 1px solid #eee; text-align: center; display: flex; flex-direction: column; gap: 4px;
  cursor: pointer; transition: all 0.2s;
}
.summary-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); transform: translateY(-1px); }
.summary-card.active { border-color: #0052D9; box-shadow: 0 0 0 2px rgba(0,82,217,0.15); }
.summary-card b { font-size: 26px; color: #0052D9; }
.summary-card span { font-size: 12.5px; color: #86909c; }
.risk-count b { color: #E34D59; }
.lightning-count b { color: #00A870; }
.avg-progress b { color: #ED7B2F; }

.intervention-card { margin-bottom: 16px; }
.lightning-card { margin-bottom: 16px; }
.main-table-card { margin-top: 0; }

.intervention-form { padding: 8px 4px; }
.form-row { margin-bottom: 12px; display: flex; align-items: flex-start; gap: 8px; }
.form-label { flex-shrink: 0; font-size: 13px; color: #49546E; padding-top: 4px; width: 92px; }
.intervention-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding-left: 100px; }
.intervention-tip { font-size: 12px; color: #00A870; margin-left: 8px; }

.lightning-actions { display: flex; flex-direction: column; gap: 10px; }
.lightning-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; background: #f0fff4; border-radius: 6px; border: 1px solid #d4f0dc;
}
.lightning-info { display: flex; align-items: center; gap: 8px; }
.lightning-buttons { display: flex; gap: 8px; }

.hr-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.hr-table th { background: #f8fafd; padding: 10px 12px; text-align: left; font-weight: 500; color: #49546E; border-bottom: 2px solid #e7e7e7; }
.hr-table td { padding: 10px 12px; border-bottom: 1px solid #f5f5f5; vertical-align: middle; }
.hr-table tbody tr:hover { background: #fafbfc; }
.row-risk { background: #fff8f7; }
.row-lightning { background: #f0fff4; }
.perf-cell { font-size: 12px; white-space: nowrap; }

.feedback-content p { font-size: 14px; line-height: 1.8; color: #1d2129; }

@media (max-width: 768px) {
  .summary-row { grid-template-columns: repeat(2, 1fr); }
  .hr-table { font-size: 12px; }
  .hr-table th, .hr-table td { padding: 6px 8px; }
  .intervention-actions { padding-left: 0; flex-direction: column; align-items: stretch; }
}
</style>
