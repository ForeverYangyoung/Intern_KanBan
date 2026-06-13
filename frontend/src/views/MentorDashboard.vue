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
          常驻看板 · 一键知晓不阻塞 · 自愿记录得绩效积分 · 数据截止: {{ reportTime }}
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

    <!-- 🔴 待处理预警（新工作流：一键知晓 + 自愿记录得积分） -->
    <t-card v-if="data.hotList?.length" class="hot-section-card" :bordered="true">
      <template #header>
        <div class="section-header">
          <t-badge dot :count="data.hotList.length">
            <span style="font-size:15px;font-weight:600;color:#e34d59">🔴 待处理 · 崩溃卡点预警</span>
          </t-badge>
          <span style="font-size:12px;color:#86909c">每位实习生展开后可操作</span>
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
              <span style="font-size:12px;color:#86909c">{{ item.jobFamily }} · {{ item.phaseProgress }}</span>
              <t-tag v-if="item.recruiterTag === 'RISK'" size="small" theme="danger" variant="outline">RISK</t-tag>
              <t-tag v-if="item.acknowledged" size="small" theme="success" variant="light">✓ 已阅</t-tag>
            </div>
          </template>

          <!-- 崩溃卡点详情 -->
          <div class="breakdown-section">
            <t-alert theme="error" :title="'系统检测到异常：' + (item.alert?.cheatSheet || '行为数据异常')">
              <template #message>
                <div class="data-context">
                  <div class="context-label">📋 数据上下文（AI提炼，仅供参考）：</div>
                  <div class="context-text">{{ item.alert?.cheatSheet || '该实习生当前阶段里程碑出现停滞。' }}</div>
                </div>
              </template>
            </t-alert>

            <!-- ==== 新工作流：三按钮 ==== -->
            <div class="workflow-section">
              <!-- 步骤1: [已阅，知晓] — 一键消除红点，不阻塞 -->
              <t-button
                v-if="!item.acknowledged"
                size="small" theme="primary" variant="outline"
                :disabled="item.actionSending"
                :loading="item.actionSending && item.pendingAction === 'ack'"
                @click="acknowledge(item)">
                <template #icon><t-icon name="check" /></template>
                已阅，知晓 ✓
              </t-button>

              <!-- 步骤2: [记录带教要点] — 自愿操作，可得绩效积分 -->
              <t-button
                v-if="item.acknowledged && !item.evidenceSubmitted"
                size="small" theme="success"
                :disabled="item.actionSending"
                :loading="item.actionSending && item.pendingAction === 'evidence'"
                @click="showQuickEvidence(item)">
                <template #icon><t-icon name="edit" /></template>
                📝 记录带教要点（+1绩效积分）
              </t-button>

              <!-- 已记录绩效素材 -->
              <t-tag v-if="item.evidenceSubmitted" size="small" theme="success" variant="light">
                🏆 绩效素材已写入
              </t-tag>

              <!-- 辅助操作 -->
              <t-button
                size="small" theme="default" variant="outline"
                :disabled="item.actionSending"
                @click="doAction(item, 'PUSH_DOC')">
                <template #icon><t-icon name="file-paste" /></template>
                推送资料
              </t-button>
              <t-button
                size="small" theme="default" variant="outline"
                :disabled="item.actionSending"
                @click="doAction(item, 'CREATE_GROUP')">
                <template #icon><t-icon name="usergroup-add" /></template>
                拉群
              </t-button>
            </div>

            <!-- 绩效积分预览牌 -->
            <div v-if="item.acknowledged && !item.evidenceSubmitted" class="incentive-banner">
              <div class="incentive-icon">🏆</div>
              <div class="incentive-text">
                <strong>记录带教要点，即可获得绩效积分</strong>
                <p style="margin:2px 0 0;font-size:12px;color:#86909c">
                  用一句话记录本次点拨核心，AI 将自动润色为"组织建设贡献描述"，
                  直接写入你的年终绩效素材库——让带教成为你的加分项，而非负担。
                </p>
              </div>
            </div>

            <!-- 快速记录弹窗（内嵌，非强制阻断） -->
            <div v-if="item.showEvidenceInput" class="inline-evidence">
              <t-textarea
                v-model="item.evidenceText"
                placeholder="一句话记录带教核心（可选）"
                :autosize="{ minRows: 2, maxRows: 3 }"
                style="margin-bottom:8px"
              />
              <div class="evidence-actions">
                <!-- 语音输入（模拟 ASR） -->
                <t-button size="small" variant="outline" theme="warning"
                  :disabled="item.voiceRecording"
                  :loading="item.voiceRecording"
                  @click="simulateVoice(item)">
                  <template #icon>🎤</template>
                  {{ item.voiceRecording ? '识别中...' : '语音输入' }}
                </t-button>
                <t-button size="small" theme="success" :disabled="!item.evidenceText?.trim()"
                  @click="submitEvidence(item)">
                  💾 提交记录（得积分）
                </t-button>
                <t-button size="small" variant="text" theme="default"
                  @click="item.showEvidenceInput = false">
                  跳过
                </t-button>
              </div>
              <div v-if="item.performanceSummary" class="perf-result">
                <div class="perf-label">🏆 AI润色后的绩效素材：</div>
                <div class="perf-text">{{ item.performanceSummary }}</div>
              </div>
            </div>

            <!-- 操作反馈 -->
            <div v-if="item.actionResult" class="action-result">
              <t-tag :theme="item.actionSuccess ? 'success' : 'danger'" size="small">
                {{ item.actionResult }}
              </t-tag>
            </div>
          </div>
        </t-collapse-panel>
      </t-collapse>
    </t-card>

    <!-- 🟢 正常区 -->
    <t-card v-if="data.coldList?.length" :bordered="true">
      <template #header>
        <span style="font-size:15px;font-weight:600;color:#00A870">🟢 正常推进 · {{ data.coldList.length }} 人</span>
      </template>
      <t-collapse :default-value="[]">
        <t-collapse-panel v-for="item in data.coldList" :key="item.id" :value="item.id">
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

    <t-card v-if="!data.hotList?.length && !data.coldList?.length" :bordered="true" class="empty-card">
      <div class="empty-hint">选择上方导师查看带教实习生</div>
    </t-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import { mentorApi } from '@/api'

const data = ref({ hotList: [], coldList: [] })
const selectedMentorId = ref(1)
const expandedAlerts = ref([])
const loading = ref(false)
const reportTime = ref('')

const mentors = ref([
  { id: 1, name: '王建国', pendingCount: 0 },
  { id: 2, name: '李思琪', pendingCount: 0 },
  { id: 3, name: '张伟明', pendingCount: 0 },
])

onMounted(() => loadBoard())

async function loadBoard() {
  loading.value = true
  try {
    const result = await mentorApi.getDashboard(selectedMentorId.value)
    data.value = result || { hotList: [], coldList: [] }
    reportTime.value = new Date().toLocaleString('zh-CN')

    const m = mentors.value.find(x => x.id === selectedMentorId.value)
    if (m) m.pendingCount = data.value.hotList?.length || 0

    expandedAlerts.value = (data.value.hotList || []).map(i => i.id)

    for (const item of data.value.hotList || []) {
      item.actionSending = false
      item.actionResult = ''
      item.actionSuccess = false
      item.pendingAction = ''
      item.acknowledged = false
      item.evidenceSubmitted = false
      item.showEvidenceInput = false
      item.evidenceText = ''
      item.performanceSummary = ''
    }
  } catch (e) {
    console.error(e)
    data.value = { hotList: [], coldList: [] }
  } finally {
    loading.value = false
  }
}

// ===== 新工作流：一键知晓（不阻塞） =====
async function acknowledge(item) {
  item.pendingAction = 'ack'
  item.actionSending = true
  try {
    await mentorApi.doAction({
      action: 'RESOLVE',
      intern_id: item.id,
      alert_id: item.alert?.id || null,
      expected_version: item.alert?.version || 1,
    })
    item.acknowledged = true
    item.actionSuccess = true
    item.actionResult = '✓ 已阅知晓，红点消除'

    const m = mentors.value.find(x => x.id === selectedMentorId.value)
    if (m) m.pendingCount = Math.max(0, m.pendingCount - 1)

    // 延迟移除热区，给用户时间看到反馈
    setTimeout(() => {
      data.value.hotList = data.value.hotList.filter(i => i.id !== item.id)
    }, 1500)

    MessagePlugin.success('已阅知晓！可自愿记录带教要点获取绩效积分')
  } catch (e) {
    item.actionSuccess = false
    item.actionResult = '操作失败，请重试'
    MessagePlugin.error('操作失败')
  } finally {
    item.actionSending = false
    item.pendingAction = ''
  }
}

// ===== 新工作流：快速记录带教要点（自愿，不强制） =====
function showQuickEvidence(item) {
  item.showEvidenceInput = true
  item.evidenceText = ''
  item.performanceSummary = ''
  item.voiceRecording = false
}

// 模拟语音识别：点击后 1.5s 假装 ASR 转写，自动填入一段带教内容
async function simulateVoice(item) {
  item.voiceRecording = true
  await new Promise(r => setTimeout(r, 1500))
  item.voiceRecording = false
  item.evidenceText = '针对 ' + item.name + ' 当前' + (item.alert?.level === 'RED' ? '严重' : '') + '卡点问题，已线下 1v1 辅导，指出了问题根因并给出改进方案，实习生已理解并承诺本周内完成修复。'
  MessagePlugin.success('🎤 语音识别完成，可修改后提交')
}

async function submitEvidence(item) {
  const content = (item.evidenceText || '').trim()
  if (!content) return
  item.pendingAction = 'evidence'
  item.actionSending = true
  try {
    const result = await mentorApi.resolveWithEvidence({
      alert_id: item.alert?.id,
      mentor_id: selectedMentorId.value,
      evidence_type: 'TEXT',
      evidence_content: content,
    })
    item.evidenceSubmitted = true
    item.showEvidenceInput = false
    item.performanceSummary = result.performance_summary || '绩效素材已生成'
    item.actionSuccess = true
    item.actionResult = '🏆 绩效素材已写入素材库'
    MessagePlugin.success('带教记录已保存，绩效积分+1 🏆')
  } catch (e) {
    item.actionSuccess = false
    MessagePlugin.error('提交失败：' + (e?.response?.data?.detail || e.message))
  } finally {
    item.actionSending = false
    item.pendingAction = ''
  }
}

// 辅助操作
async function doAction(item, actionType) {
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
    MessagePlugin.success(item.actionResult)
  } catch (e) {
    item.actionSuccess = false
    item.actionResult = e?.response?.status === 409
      ? '⚠️ 版本冲突：请刷新看板后重试'
      : '操作失败：' + (e?.message || '网络异常')
    MessagePlugin.error(item.actionResult)
  } finally {
    item.actionSending = false
  }
}

function refreshBoard() { loadBoard() }
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
.data-context { margin-top: 4px; }
.context-label { font-size: 13px; color: #0052D9; font-weight: 600; }
.context-text { font-size: 13px; color: #49546E; margin-top: 4px; line-height: 1.7; }

/* ===== 新工作流 ===== */
.workflow-section { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; align-items: center; }

.incentive-banner { display: flex; gap: 12px; align-items: flex-start; margin-top: 12px;
  padding: 14px 16px; background: linear-gradient(135deg, #fff7e6, #fffbf0);
  border: 1px solid #ffe7ba; border-radius: 8px; font-size: 13px; }
.incentive-icon { font-size: 24px; flex-shrink: 0; }
.incentive-text { flex: 1; line-height: 1.6; color: #49546e; }

.inline-evidence { margin-top: 12px; padding: 12px; background: #f8fafd; border-radius: 8px; border: 1px solid #e7f0ff; }
.evidence-actions { display: flex; gap: 8px; align-items: center; }

.perf-result { margin-top: 10px; padding: 10px 12px; background: #e8f8f0; border-radius: 6px; border-left: 3px solid #00a870; }
.perf-label { font-size: 12px; color: #00a870; font-weight: 600; margin-bottom: 4px; }
.perf-text { font-size: 13px; line-height: 1.7; color: #333; white-space: pre-wrap; }

.action-result { margin-top: 8px; }
.cold-detail { padding: 8px 4px; }
.detail-table { border-collapse: collapse; }
.detail-table td { padding: 4px 8px; font-size: 13px; }
.detail-label { color: #86909c; width: 80px; }

.empty-hint { text-align: center; padding: 40px; color: #c9cdd4; font-size: 13px; }
.empty-card { border: 1px dashed #d9d9d9; }
</style>
