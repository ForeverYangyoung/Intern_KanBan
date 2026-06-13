<template>
  <div class="sandbox-page">
    <!-- 顶部标题栏 -->
    <div class="sandbox-header">
      <div class="header-left">
        <t-button theme="default" variant="text" @click="$router.push('/')">
          ← 返回
        </t-button>
        <h2>🎮 上帝视角沙盒 <span class="badge">Demo 评委专用</span></h2>
      </div>
      <div class="header-right">
        <t-tag theme="warning" variant="light">模拟模式</t-tag>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="sandbox-body">
      <!-- 左侧：角色切换 + 事件模拟 -->
      <div class="sandbox-left">
        <t-card title="👤 切换视角" bordered>
          <t-radio-group v-model="currentRole" @change="onRoleSwitch">
            <t-radio-button value="intern">实习生</t-radio-button>
            <t-radio-button value="mentor">导师</t-radio-button>
            <t-radio-button value="hr">HR</t-radio-button>
          </t-radio-group>

          <div v-if="currentRole === 'intern'" class="role-detail" style="margin-top:16px">
            <p>当前视角：<strong>{{ currentInternName }}</strong></p>
            <p>岗位：{{ currentInternJobFamily }} | 阶段：{{ currentInternState }}</p>
            <t-tag :theme="tagTheme">{{ currentInternTag }}</t-tag>
          </div>
        </t-card>

        <t-card title="⚡ 一键模拟事件" bordered style="margin-top:16px">
          <p class="hint">选择实习生，然后点击按钮模拟崩溃卡点事件：</p>

          <div class="intern-select" style="margin-bottom:16px">
            <t-select v-model="selectedInternId" placeholder="选择实习生" clearable>
              <t-option
                v-for="i in internList"
                :key="i.id"
                :value="i.id"
                :label="`${i.name}（${jobFamilyLabel(i.job_family)}）`"
              />
            </t-select>
          </div>

          <div class="event-buttons">
            <t-button
              theme="danger"
              variant="outline"
              :disabled="!selectedInternId"
              @click="simulate('BUILD_FAIL_3X')"
            >
              🔧 连续3次编译失败
              <template #hint>研发 · 触发白天轨 Copilot</template>
            </t-button>

            <t-button
              theme="warning"
              variant="outline"
              :disabled="!selectedInternId"
              @click="simulate('PRD_COMMENT_STUCK')"
            >
              📝 PRD评论僵局
              <template #hint>产品 · 语义争议未收敛</template>
            </t-button>

            <t-button
              theme="danger"
              variant="outline"
              :disabled="!selectedInternId"
              @click="simulate('CRM_REJECT_3D')"
            >
              📞 CRM连续3天拒收
              <template #hint>销售 · 黄色提示非直接判失联</template>
            </t-button>

            <t-button
              theme="warning"
              variant="outline"
              :disabled="!selectedInternId"
              @click="simulate('CRM_SILENT_3D')"
            >
              💤 CRM静默3天
              <template #hint>销售 · 有触达无有效通话</template>
            </t-button>
          </div>
        </t-card>
      </div>

      <!-- 右侧：实时观测日志 -->
      <div class="sandbox-right">
        <t-card title="📊 实时观测" bordered>
          <div v-if="lastResult" class="result-panel">
            <t-alert theme="success" style="margin-bottom:16px">
              模拟成功！事件：<strong>{{ lastResult.event }}</strong>
            </t-alert>

            <div class="result-section">
              <h4>🎯 双轨分流结果</h4>
              <t-list :split="true">
                <t-list-item>
                  <t-list-item-meta
                    title="轨道"
                    :description="lastResult.track === 'REALTIME' ? '⚡ 白天轨（实时）' : '🌙 深夜轨（批处理）'"
                  />
                </t-list-item>
                <t-list-item>
                  <t-list-item-meta
                    title="Copilot"
                    :description="lastResult.copilot_triggered ? '✅ 已触发弹窗' : '❌ 未触发'"
                  />
                </t-list-item>
                <t-list-item>
                  <t-list-item-meta
                    title="导师预警"
                    :description="lastResult.alert_level === 'RED' ? '🔴 RED 级' : '🟡 YELLOW 级'"
                  />
                </t-list-item>
                <t-list-item>
                  <t-list-item-meta
                    title="通知导师"
                    :description="lastResult.mentor_notified ? '✅ 已推送' : '❌ 未推送'"
                  />
                </t-list-item>
              </t-list>
            </div>

            <div v-if="lastResult.copilot_message" class="copilot-preview" style="margin-top:16px">
              <h4>💬 Copilot 弹窗预览</h4>
              <div class="copilot-bubble">
                {{ lastResult.copilot_message }}
              </div>
            </div>
          </div>

          <div v-else class="empty-state">
            <t-icon name="play-circle" size="48px" color="#c9cdd4" />
            <p>点击左侧按钮开始模拟</p>
          </div>
        </t-card>

        <!-- 模拟历史 -->
        <t-card title="📜 模拟历史" bordered style="margin-top:16px">
          <t-list v-if="runHistory.length" :split="true">
            <t-list-item v-for="r in runHistory" :key="r.id">
              <t-list-item-meta
                :title="`${r.event_type}`"
                :description="`实习生 #${r.intern_id} · ${formatTime(r.created_at)}`"
              />
            </t-list-item>
          </t-list>
          <p v-else class="empty-text">暂无模拟记录</p>
        </t-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from 'tdesign-vue-next'
import { sandboxApi } from '../api'

const router = useRouter()

// 状态
const currentRole = ref('intern')
const internList = ref([])
const selectedInternId = ref(null)
const lastResult = ref(null)
const runHistory = ref([])

// 计算属性
const currentIntern = computed(() =>
  internList.value.find(i => i.id === selectedInternId.value)
)
const currentInternName = computed(() => currentIntern.value?.name || '-')
const currentInternJobFamily = computed(() => {
  const jf = currentIntern.value?.job_family
  return jf === 'RD' ? '研发' : jf === 'PM' ? '产品' : jf === 'SALES' ? '销售' : '-'
})
const currentInternState = computed(() => {
  const s = currentIntern.value?.current_state
  return s === 'ONBOARDING' ? '融入期' : s === 'RAMP_UP' ? '上手期' : s === 'INDEPENDENT' ? '独立期' : '-'
})
const currentInternTag = computed(() => {
  const t = currentIntern.value?.recruiter_tag
  return t === 'LIGHTNING' ? '⚡ 绩优闪电' : t === 'RISK' ? '🔴 红灯风险' : '🟢 正常稳健'
})
const tagTheme = computed(() => {
  const t = currentIntern.value?.recruiter_tag
  return t === 'LIGHTNING' ? 'success' : t === 'RISK' ? 'danger' : 'default'
})

// 方法
function jobFamilyLabel(jf) {
  return jf === 'RD' ? '研发' : jf === 'PM' ? '产品' : jf === 'SALES' ? '销售' : jf
}

function formatTime(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function loadInterns() {
  try {
    const res = await sandboxApi.getInterns()
    internList.value = res.data || res
  } catch (e) {
    console.error('加载实习生列表失败', e)
  }
}

async function loadHistory() {
  try {
    const res = await sandboxApi.getRuns()
    runHistory.value = res.data || res
  } catch (e) {
    console.error('加载模拟历史失败', e)
  }
}

async function simulate(eventType) {
  if (!selectedInternId.value) {
    MessagePlugin.warning('请先选择实习生')
    return
  }
  try {
    const res = await sandboxApi.simulate(selectedInternId.value, eventType)
    lastResult.value = res.data || res
    MessagePlugin.success(`模拟成功：${eventType}`)
    loadHistory()
  } catch (e) {
    MessagePlugin.error(`模拟失败：${e.response?.data?.detail || e.message}`)
  }
}

function onRoleSwitch(role) {
  if (role === 'intern') {
    router.push('/intern')
  } else if (role === 'mentor') {
    router.push('/mentor')
  } else if (role === 'hr') {
    router.push('/hr')
  }
}

onMounted(() => {
  loadInterns()
  loadHistory()
})
</script>

<style scoped>
.sandbox-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}
.sandbox-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e7e7e7;
}
.sandbox-header h2 {
  margin: 0;
  font-size: 20px;
}
.badge {
  font-size: 12px;
  background: #fff3e0;
  color: #ed7b2f;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
}
.sandbox-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
.event-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hint {
  color: #888;
  font-size: 13px;
  margin-bottom: 12px;
}
.result-panel {
  /* padding: 8px; */
}
.result-section h4 {
  margin: 12px 0 8px;
  font-size: 14px;
  color: #333;
}
.copilot-bubble {
  background: #f0f5ff;
  border-left: 3px solid #0052d9;
  padding: 12px 16px;
  border-radius: 4px;
  font-size: 14px;
  line-height: 1.6;
}
.empty-state {
  text-align: center;
  padding: 48px 0;
  color: #c9cdd4;
}
.empty-text {
  text-align: center;
  color: #c9cdd4;
  padding: 24px 0;
}
.role-detail {
  padding: 12px;
  background: #f9f9f9;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.8;
}
@media (max-width: 900px) {
  .sandbox-body {
    grid-template-columns: 1fr;
  }
}
</style>
