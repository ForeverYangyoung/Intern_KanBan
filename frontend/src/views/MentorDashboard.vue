<template>
  <div class="mentor-dashboard">
    <div class="board-header">
      <div class="board-title">
        <h2>📊 带教看板 · 常驻监控</h2>
        <t-badge :count="data.hotList?.length || 0" :max-count="9" v-if="data.hotList?.length">
          <t-icon name="error-circle" size="18px" color="#e34d59" />
        </t-badge>
      </div>
      <div class="board-subtitle">
        <span style="font-size:12px;color:#86909c">
          常驻看板 · 红点未消不丢消息 · 数据截止: {{ reportTime }}
        </span>
        <t-button size="small" variant="outline" @click="refreshBoard" :loading="loading">
          <template #icon><t-icon name="refresh" /></template>刷新看板
        </t-button>
      </div>
    </div>

    <!-- 导师切换 -->
    <div class="mentor-switch">
      <t-radio-group v-model="selectedMentorId" variant="default-filled" size="small" @change="loadBoard">
        <t-radio-button v-for="m in mentors" :key="m.id" :value="m.id">
          {{ m.name }} <t-badge v-if="m.pendingCount" :count="m.pendingCount" size="small" style="margin-left:4px" />
        </t-radio-button>
      </t-radio-group>
    </div>

    <!-- 🔴 待处理预警（红点 + 展开 + Copilot 小抄 + 乐观锁按钮） -->
    <t-card v-if="data.hotList?.length" class="hot-section-card" :bordered="true">
      <template #header>
        <div class="section-header">
          <t-badge dot :count="data.hotList.length">
            <span style="font-size:15px;font-weight:600;color:#e34d59">🔴 待处理 · 崩溃卡点预警</span>
          </t-badge>
          <span style="font-size:12px;color:#86909c">展开可查看崩溃原因与一键决策</span>
        </div>
      </template>

      <t-collapse v-model="expandedAlerts">
        <t-collapse-panel
          v-for="item in data.hotList"
          :key="item.id"
          :value="item.id"
        >
          <template #header>
            <div class="hot-header">
              <t-badge dot>
                <b>{{ item.name }}</b>
              </t-badge>
              <t-tag size="small" :theme="item.alert?.level === 'RED' ? 'danger' : 'warning'" variant="light">
                {{ item.alert?.level === 'RED' ? '红灯' : '黄灯' }}
              </t-tag>
              <t-tag size="small" variant="light">{{ item.stateLabel }}</t-tag>
              <span style="font-size:12px;color:#86909c">{{ item.jobFamily }} · 进度 {{ item.phaseProgress }}</span>
              <t-tag v-if="item.recruiterTag === 'RISK'" size="small" theme="danger" variant="outline">RISK</t-tag>
            </div>
          </template>

          <!-- 崩溃卡点详情 + Copilot 小抄 -->
          <div class="breakdown-section">
            <t-alert theme="error" :title="'崩溃卡点：' + (item.alert?.cheatSheet || '行为数据异常')">
              <template #message>
                <div class="copilot-cheatsheet">
                  <div class="cheatsheet-label">💡 Copilot 导航小抄：</div>
                  <div class="cheatsheet-text">{{ item.alert?.cheatSheet || '系统检测到该实习生在关键里程碑出现滞留，建议导师线下核实具体情况。' }}</div>
                </div>
              </template>
            </t-alert>

            <!-- 一键决策（乐观锁） -->
            <div class="action-buttons">
              <t-button
                size="small" theme="primary"
                :disabled="item.actionSending"
                :loading="item.actionSending"
                @click="doAction(item, 'PUSH_DOC')">
                <template #icon><t-icon name="file-paste" /></template>
                推送学习资料
              </t-button>
              <t-button
                size="small" theme="warning"
                :disabled="item.actionSending"
                :loading="item.actionSending"
                @click="doAction(item, 'CREATE_GROUP')">
                <template #icon><t-icon name="usergroup-add" /></template>
                拉企微协助群
              </t-button>
              <t-button
                size="small" theme="success"
                :disabled="item.actionSending"
                :loading="item.actionSending"
                @click="showEvidenceDialog(item)">
                <template #icon><t-icon name="check" /></template>
                已线下点拨 ✓
              </t-button>
              <t-button
                size="small" variant="outline"
                :disabled="item.actionSending"
                @click="askProgress(item)">
                <template #icon><t-icon name="chat-message" /></template>
                问进度
              </t-button>
            </div>

            <!-- 乐观锁版本提示 -->
            <div v-if="item.actionResult" class="action-result">
              <t-tag :theme="item.actionSuccess ? 'success' : 'danger'" size="small">
                {{ item.actionResult }}
              </t-tag>
            </div>
          </div>
        </t-collapse-panel>
      </t-collapse>
    </t-card>

    <!-- 🟢 正常区（折叠，无红点） -->
    <t-card v-if="data.coldList?.length" :bordered="true">
      <template #header>
        <span style="font-size:15px;font-weight:600;color:#00A870">🟢 正常推进 · {{ data.coldList.length }} 人</span>
      </template>

      <t-collapse :default-value="[]">
        <t-collapse-panel
          v-for="item in data.coldList"
          :key="item.id"
          :value="item.id"
        >
          <template #header>
            <div class="cold-header">
              <span style="font-weight:600">{{ item.name }}</span>
              <t-tag size="small" variant="light">{{ item.stateLabel }}</t-tag>
              <t-tag v-if="item.recruiterTag === 'LIGHTNING'" size="small" theme="success" variant="light">绩优闪电</t-tag>
              <span style="font-size:12px;color:#86909c">{{ item.jobFamily }} · {{ item.phaseProgress }} · {{ item.phasePercent }}%</span>
            </div>
          </template>
          <div class="cold-detail">
            <table class="detail-table">
              <tr><td class="detail-label">当前阶段</td><td>{{ item.currentPhase }}</td></tr>
              <tr><td class="detail-label">入职日期</td><td>{{ item.entryDate }}</td></tr>
              <tr v-if="item.commits !== undefined"><td class="detail-label">绩效快照</td><td>{{ item.commits }}c / {{ item.prs }}pr / {{ item.bugs }}bug</td></tr>
              <tr v-else-if="item.leadsTouched !== undefined"><td class="detail-label">销售数据</td><td>{{ item.leadsTouched }} 线索 / {{ item.callDurationMin }} 分钟</td></tr>
            </table>
          </div>
        </t-collapse-panel>
      </t-collapse>
    </t-card>

    <!-- 空状态 -->
    <t-card v-if="!data.hotList?.length && !data.coldList?.length" :bordered="true" class="empty-card">
      <div class="empty-hint">选择上方导师查看带教实习生</div>
    </t-card>

    <!-- 举证式消红点弹窗（绩效利益捆绑） -->
    <t-dialog
      v-model:visible="evidenceDialog.visible"
      header="📝 举证式消红点 · 绩效素材生成"
      :confirm-btn="{ content: '提交并消除红点', disabled: !evidenceDialog.content.trim() }"
      :on-confirm="submitEvidence"
      width="560px"
    >
      <div style="padding: 8px 0; font-size: 13px; line-height: 1.8; color: #666; margin-bottom: 16px">
        <p>⚠️ <strong>不可空点消红点</strong> — 请输入本次点拨核心内容</p>
        <p style="margin-top: 4px">混元将把您的带教内容转写为 <strong>「组织建设贡献描述」</strong>，可直接用于年终绩效/晋升材料 🏆</p>
      </div>
      <t-textarea
        v-model="evidenceDialog.content"
        placeholder="例：指出了 Redis 连接池 maxIdle 配置问题，并带着看了团队标准示例，实习生已理解并修复"
        :autosize="{ minRows: 3, maxRows: 6 }"
      />
      <div v-if="evidenceDialog.performanceSummary" style="margin-top: 16px; padding: 12px; background: #f0f5ff; border-radius: 6px; border-left: 3px solid #0052d9">
        <div style="font-size: 12px; color: #0052d9; font-weight: 600; margin-bottom: 6px">🏆 混元生成的组织建设贡献描述（已写入绩效素材库）</div>
        <div style="font-size: 13px; line-height: 1.7; color: #333; white-space: pre-wrap">{{ evidenceDialog.performanceSummary }}</div>
      </div>
    </t-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Message } from 'tdesign-vue-next'
import { mentorApi } from '@/api'

const data = ref({ hotList: [], coldList: [] })
const selectedMentorId = ref(1)
const expandedAlerts = ref([])
const loading = ref(false)
const reportTime = ref('')

// 举证式消红点弹窗状态
const evidenceDialog = ref({
  visible: false,
  content: '',
  performanceSummary: '',
  currentItem: null,
})

const mentors = ref([
  { id: 1, name: '陈导师', pendingCount: 0 },
  { id: 2, name: '何导师', pendingCount: 0 },
  { id: 3, name: '齐导师', pendingCount: 0 },
])

onMounted(() => loadBoard())

async function loadBoard() {
  loading.value = true
  try {
    const result = await mentorApi.getDashboard(selectedMentorId.value)
    data.value = result || { hotList: [], coldList: [] }
    reportTime.value = new Date().toLocaleString('zh-CN')

    // 更新导师红点计数
    const m = mentors.value.find(x => x.id === selectedMentorId.value)
    if (m) m.pendingCount = data.value.hotList?.length || 0

    // 自动展开所有待处理项
    expandedAlerts.value = (data.value.hotList || []).map(i => i.id)

    // 初始化每个热项的操作状态
    for (const item of data.value.hotList || []) {
      item.actionSending = false
      item.actionResult = ''
      item.actionSuccess = false
    }
  } catch (e) {
    console.error(e)
    data.value = { hotList: [], coldList: [] }
  } finally {
    loading.value = false
  }
}

async function doAction(item, actionType) {
  // 乐观锁：先标记 pending，发起请求，成功后更新
  item.actionSending = true
  item.actionResult = '正在提交...'
  try {
    const payload = {
      action: actionType,
      intern_id: item.id,
      alert_id: item.alert?.id || null,
      expected_version: item.alert?.version || 1,
    }
    const result = await mentorApi.doAction(payload)
    item.actionSuccess = true
    item.actionResult = result?.message || `${actionType} 已完成`

    if (actionType === 'RESOLVE') {
      // 乐观更新：从热区移除
      data.value.hotList = data.value.hotList.filter(i => i.id !== item.id)
      // 更新导师计数
      const m = mentors.value.find(x => x.id === selectedMentorId.value)
      if (m) m.pendingCount = Math.max(0, m.pendingCount - 1)
    }

    Message.success(item.actionResult)
  } catch (e) {
    item.actionSuccess = false
    const msg = e?.response?.status === 409
      ? '⚠️ 版本冲突：请刷新看板后重试'
      : '操作失败：' + (e?.message || '网络异常')
    item.actionResult = msg
    Message.error(msg)
  } finally {
    item.actionSending = false
  }
}

async function askProgress(item) {
  try {
    const result = await mentorApi.askProgress(item.id)
    Message.success(result?.message || '已发送进度问询')
  } catch (e) {
    Message.error('发送失败')
  }
}

function refreshBoard() { loadBoard() }

// ============================================================
// 举证式消红点 — 绩效利益捆绑
// ============================================================

function showEvidenceDialog(item) {
  evidenceDialog.value = {
    visible: true,
    content: '',
    performanceSummary: '',
    currentItem: item,
  }
}

async function submitEvidence() {
  const item = evidenceDialog.value.currentItem
  if (!item) return

  const content = evidenceDialog.value.content.trim()
  if (!content) {
    Message.warning('请输入带教核心内容')
    return
  }

  // 乐观锁：先标记 pending
  item.actionSending = true
  try {
    const result = await mentorApi.resolveWithEvidence({
      alert_id: item.alert?.id,
      mentor_id: selectedMentorId.value,
      evidence_type: 'TEXT',
      evidence_content: content,
    })

    // 显示生成的绩效素材
    evidenceDialog.value.performanceSummary = result.performance_summary || '绩效素材已生成'

    // 乐观更新：从热区移除
    setTimeout(() => {
      data.value.hotList = data.value.hotList.filter(i => i.id !== item.id)
      const m = mentors.value.find(x => x.id === selectedMentorId.value)
      if (m) m.pendingCount = Math.max(0, m.pendingCount - 1)
      evidenceDialog.value.visible = false
      Message.success('红点已消除，绩效素材已写入素材库 🏆')
    }, 2000)
  } catch (e) {
    item.actionSending = false
    Message.error('提交失败：' + (e?.response?.data?.detail || e.message))
  }
}
</script>

<style scoped>
.mentor-dashboard { padding-bottom: 40px; max-width: 960px; margin: 0 auto; }
.board-header { margin-bottom: 16px; }
.board-title { display: flex; align-items: center; gap: 8px; }
.board-title h2 { font-size: 18px; margin: 0; color: #1d2129; }
.board-subtitle { display: flex; align-items: center; justify-content: space-between; margin-top: 4px; }
.mentor-switch { margin-bottom: 16px; }

.hot-section-card { margin-bottom: 16px; }
.hot-section-card :deep(.t-card__header) { border-bottom: 2px solid #fde2e2; background: #fff8f7; }
.section-header { display: flex; align-items: center; gap: 12px; }

.hot-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cold-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.breakdown-section { padding: 12px 4px; }
.copilot-cheatsheet { margin-top: 4px; }
.cheatsheet-label { font-size: 13px; color: #0052D9; font-weight: 600; }
.cheatsheet-text { font-size: 13px; color: #49546E; margin-top: 4px; line-height: 1.7; }

.action-buttons { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.action-result { margin-top: 8px; }

.cold-detail { padding: 8px 4px; }
.detail-table { border-collapse: collapse; }
.detail-table td { padding: 4px 8px; font-size: 13px; }
.detail-label { color: #86909c; width: 80px; }

.empty-hint { text-align: center; padding: 40px; color: #c9cdd4; font-size: 13px; }
.empty-card { border: 1px dashed #d9d9d9; }
</style>
