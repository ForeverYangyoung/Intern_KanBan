<template>
  <div id="app-root">
    <!-- 角色切换栏 -->
    <t-header class="app-header">
      <div class="header-left">
        <span class="logo">🌱 实习能量站</span>
        <span class="subtitle">新人成长导航智能看板</span>
      </div>
      <div class="header-right">
        <t-radio-group v-model="currentRole" variant="default-filled" size="small">
          <t-radio-button value="intern">实习生</t-radio-button>
          <t-radio-button value="mentor">导师</t-radio-button>
          <t-radio-button value="hr">HR</t-radio-button>
        </t-radio-group>
        <t-button
          theme="warning"
          variant="outline"
          size="small"
          style="margin-left:12px"
          @click="router.push('/sandbox')"
        >
          🎮 沙盒
        </t-button>
      </div>
    </t-header>

    <!-- 内容区 -->
    <div class="app-body">
      <router-view :key="currentRole" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const currentRole = ref('intern')

watch(currentRole, (role) => {
  router.push(`/${role}`)
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  background: #f5f7fa;
  color: #1d2129;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e7e7e7;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  color: #0052d9;
}

.subtitle {
  font-size: 13px;
  color: #86909c;
}

.header-right {
  display: flex;
  align-items: center;
}

.app-body {
  max-width: 1200px;
  margin: 24px auto;
  padding: 0 24px;
}
</style>
