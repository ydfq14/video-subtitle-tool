<template>
  <div class="app">
    <!-- 标题栏 -->
    <header class="header">
      <div class="header__brand">
        <span class="header__logo">🎬</span>
        <h1 class="header__title">智能字幕工坊</h1>
      </div>
      <div class="header__subtitle">纯本地处理，保护隐私</div>
    </header>

    <!-- 步骤指示器 -->
    <nav class="steps-nav">
      <div
        v-for="(step, index) in steps"
        :key="index"
        class="steps-nav__item"
        :class="{
          'steps-nav__item--active': store.currentStep === step.id,
          'steps-nav__item--completed': store.currentStep > step.id
        }"
      >
        <div class="steps-nav__node">
          <span v-if="store.currentStep > step.id">✓</span>
          <span v-else>{{ step.id }}</span>
        </div>
        <div class="steps-nav__label">{{ step.label }}</div>
        <div v-if="index < steps.length - 1" class="steps-nav__line"></div>
      </div>
    </nav>

    <!-- 主工作区 -->
    <main class="main">
      <StepUpload v-if="store.currentStep === 1" @next="store.nextStep" />
      <StepProcess v-else-if="store.currentStep === 2" @next="store.nextStep" @prev="store.prevStep" />
      <StepExport v-else-if="store.currentStep === 3" @prev="store.prevStep" />
    </main>

    <!-- 底部状态栏 -->
    <footer class="footer">
      <div class="footer__status">
        <span class="status-indicator" :class="`status-indicator--${store.status}`"></span>
        <span class="status-text">{{ statusText }}</span>
      </div>

      <div v-if="store.isProcessing" class="footer__progress">
        <div class="progress-bar">
          <div class="progress-bar__fill" :style="{ width: `${store.progress}%` }"></div>
        </div>
        <span class="progress-text">{{ store.progress }}%</span>
      </div>

      <button class="btn btn--ghost footer__log-btn" @click="showLogs = !showLogs">
        <span>📋</span> 日志 {{ showLogs ? '▲' : '▼' }}
      </button>
    </footer>

    <!-- 日志面板 -->
    <div v-if="showLogs" class="log-panel">
      <div class="log-panel__header">
        <span>处理日志</span>
        <button class="btn btn--ghost" @click="showLogs = false">关闭</button>
      </div>
      <div class="log-panel__content">
        <div
          v-for="log in store.logs"
          :key="log.id"
          class="log-entry"
          :class="`log-entry--${log.level}`"
        >
          <span class="log-entry__time">[{{ formatTime(log.timestamp) }}]</span>
          <span v-if="log.code" class="log-entry__code">[{{ log.code }}]</span>
          <span class="log-entry__message">{{ log.message }}</span>
        </div>
        <div v-if="store.logs.length === 0" class="log-entry log-entry--info">暂无日志</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useProjectStore } from './stores/project'
import StepUpload from './components/StepUpload.vue'
import StepProcess from './components/StepProcess.vue'
import StepExport from './components/StepExport.vue'

const store = useProjectStore()
const showLogs = ref(false)

const steps = [
  { id: 1, label: '上传视频' },
  { id: 2, label: '识别与翻译' },
  { id: 3, label: '预览合并' }
]

const statusText = computed(() => {
  switch (store.status) {
    case 'idle': return '就绪'
    case 'uploading': return '上传中...'
    case 'processing': return '处理中...'
    case 'completed': return '处理完成'
    case 'error': return `错误: ${store.error?.message || '未知错误'}`
    default: return ''
  }
})

function formatTime(date) {
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
  store.addLog('info', '智能字幕工坊已就绪（纯Web版）')
})
</script>

<style lang="scss" scoped>
.app {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: $bg-main;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $spacing-md $spacing-lg;
  background: $bg-card;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);

  &__brand {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
  }

  &__logo {
    font-size: 28px;
  }

  &__title {
    font-size: 20px;
    font-weight: 600;
    color: $primary;
  }

  &__subtitle {
    font-size: 12px;
    color: $text-secondary;
    background: rgba($success, 0.1);
    padding: 4px 12px;
    border-radius: 12px;
  }
}

.steps-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $spacing-xl $spacing-lg;
  background: $bg-card;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);

  &__item {
    display: flex;
    align-items: center;
    position: relative;

    &--active {
      .steps-nav__node {
        background: $accent;
        color: white;
        animation: pulse 2s infinite;
      }
      .steps-nav__label {
        color: $accent;
        font-weight: 600;
      }
    }

    &--completed {
      .steps-nav__node {
        background: $success;
        color: white;
      }
      .steps-nav__label {
        color: $success;
      }
      .steps-nav__line {
        background: $success;
      }
    }
  }

  &__node {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: $text-secondary;
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    transition: $transition;
  }

  &__label {
    margin-left: $spacing-sm;
    font-size: 14px;
    color: $text-secondary;
    transition: $transition;
  }

  &__line {
    width: 60px;
    height: 2px;
    background: rgba(0, 0, 0, 0.15);
    margin: 0 $spacing-md;
    transition: $transition;
  }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba($accent, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba($accent, 0); }
}

.main {
  flex: 1;
  overflow-y: auto;
  padding: $spacing-xl;
}

.footer {
  display: flex;
  align-items: center;
  gap: $spacing-lg;
  padding: $spacing-md $spacing-lg;
  background: $bg-card;
  border-top: 1px solid rgba(0, 0, 0, 0.08);

  &__status {
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    min-width: 200px;
  }

  &__progress {
    flex: 1;
    display: flex;
    align-items: center;
    gap: $spacing-md;
  }

  &__log-btn {
    padding: 6px 12px;
    font-size: 12px;
  }
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;

  &--idle { background: $text-secondary; }
  &--uploading,
  &--processing { background: $accent; animation: blink 1s infinite; }
  &--completed { background: $success; }
  &--error { background: $error; }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  font-size: 13px;
  color: $text-secondary;
}

.progress-bar {
  flex: 1;
  height: 4px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
  overflow: hidden;

  &__fill {
    height: 100%;
    background: linear-gradient(90deg, $accent, lighten($accent, 10%));
    background-size: 20px 20px;
    animation: stripes 1s linear infinite;
    transition: width 0.3s ease;
  }
}

@keyframes stripes {
  0% { background-position: 0 0; }
  100% { background-position: 20px 0; }
}

.progress-text {
  font-size: 12px;
  color: $text-secondary;
  min-width: 40px;
  text-align: right;
}

.log-panel {
  position: fixed;
  bottom: 60px;
  left: $spacing-lg;
  right: $spacing-lg;
  max-height: 300px;
  background: $bg-card;
  border-radius: $radius-lg;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  z-index: 100;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $spacing-sm $spacing-md;
    background: $primary;
    color: white;
    font-weight: 500;
  }

  &__content {
    max-height: 250px;
    overflow-y: auto;
    padding: $spacing-sm;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
  }
}

.log-entry {
  padding: 4px $spacing-sm;
  border-radius: 4px;
  margin-bottom: 2px;

  &--info { color: $text-secondary; }
  &--success { color: $success; background: rgba($success, 0.1); }
  &--warning { color: $warning; background: rgba($warning, 0.1); }
  &--error { color: $error; background: rgba($error, 0.1); }

  &__time {
    color: $text-secondary;
    margin-right: $spacing-sm;
  }

  &__code {
    color: $accent;
    margin-right: $spacing-sm;
    font-weight: 600;
  }

  &__message {
    word-break: break-all;
  }
}
</style>
