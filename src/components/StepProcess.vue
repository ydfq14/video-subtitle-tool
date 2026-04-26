<template>
  <div class="step-process">
    <div class="step-header">
      <h2 class="step-header__title">🔊 识别与翻译</h2>
      <p class="step-header__desc">选择视频语种，一键生成字幕（使用本地 Whisper AI）</p>
    </div>

    <!-- 设置面板 -->
    <div class="settings-panel card">
      <div class="settings-panel__item">
        <label class="settings-panel__label">源语言</label>
        <select v-model="sourceLanguage" class="select" :disabled="isProcessing">
          <option value="ja">日语</option>
          <option value="en">英语</option>
          <option value="zh">中文</option>
        </select>
      </div>

      <div class="settings-panel__item">
        <label class="settings-panel__label">翻译目标</label>
        <select v-model="translateTarget" class="select" :disabled="isProcessing">
          <option value="none">不翻译（直接输出源语言字幕）</option>
          <option value="zh">翻译为中文</option>
        </select>
      </div>

      <div class="settings-panel__actions">
        <button
          class="btn btn--primary"
          :disabled="isProcessing || !canProcess"
          @click="startProcessing"
        >
          <span v-if="isProcessing" class="spinner-small"></span>
          <span v-else>🎯</span>
          {{ isProcessing ? processingStage : '开始处理' }}
        </button>
      </div>
    </div>

    <!-- 处理进度 -->
    <div v-if="isProcessing" class="progress-panel card">
      <div class="progress-panel__header">
        <span>处理进度</span>
        <span class="progress-panel__percent">{{ progress }}%</span>
      </div>
      <div class="progress-bar">
        <div
          class="progress-bar__fill"
          :style="{ width: `${progress}%` }"
          :class="{ 'progress-bar__fill--error': hasError }"
        ></div>
      </div>
      <div class="progress-panel__stage">{{ processingStage }}</div>
    </div>

    <!-- 字幕预览 -->
    <div v-if="hasSubtitles" class="subtitle-preview card">
      <div class="subtitle-preview__header">
        <h3>字幕预览</h3>
        <span class="subtitle-preview__count">{{ segments.length }} 条</span>
      </div>
      <div class="subtitle-preview__list">
        <div
          v-for="(seg, index) in segments"
          :key="index"
          class="subtitle-item"
          :class="{ 'subtitle-item--active': activeIndex === index }"
          @click="selectSegment(index)"
        >
          <div class="subtitle-item__time">
            {{ formatTime(seg.start) }} → {{ formatTime(seg.end) }}
          </div>
          <div class="subtitle-item__text">{{ seg.translated || seg.text }}</div>
          <div class="subtitle-item__actions">
            <button class="btn btn--ghost btn--small" @click.stop="adjustTime(index, -0.1)">-100ms</button>
            <button class="btn btn--ghost btn--small" @click.stop="adjustTime(index, 0.1)">+100ms</button>
            <button class="btn btn--ghost btn--small" @click.stop="deleteSegment(index)">🗑️</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-panel card">
      <div class="error-panel__icon">⚠️</div>
      <div class="error-panel__content">
        <div class="error-panel__code">{{ errorCode }}</div>
        <div class="error-panel__message">{{ error }}</div>
      </div>
      <div class="error-panel__actions">
        <button class="btn btn--secondary" @click="retryProcessing">重试</button>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="step-actions">
      <button class="btn btn--secondary" @click="handlePrev">
        <span>←</span> 上一步
      </button>
      <button
        class="btn btn--primary"
        :disabled="!hasSubtitles || isProcessing"
        @click="handleNext"
      >
        下一步 <span>→</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useProjectStore } from '../stores/project'

const emit = defineEmits(['next', 'prev'])

const store = useProjectStore()

const sourceLanguage = ref(store.sourceLanguage || 'ja')
const translateTarget = ref('none')
const progress = ref(0)
const processingStage = ref('')
const activeIndex = ref(-1)
const error = ref('')
const errorCode = ref('')

const isProcessing = computed(() => store.isProcessing)
const hasSubtitles = computed(() => store.segments.length > 0)
const segments = computed(() => store.segments)
const canProcess = computed(() => !!store.videoPath)
const hasError = computed(() => !!error.value)

watch(sourceLanguage, (val) => {
  store.sourceLanguage = val
})

async function startProcessing() {
  if (!store.videoPath) {
    error.value = '请先上传视频文件'
    return
  }

  error.value = ''
  errorCode.value = ''
  progress.value = 0
  store.clearLogs()
  store.setProcessing(0)

  try {
    // 阶段1: 音频提取 (0-20%)
    processingStage.value = '正在提取音频...'
    store.addLog('info', '开始提取音频')
    progress.value = 10

    // 阶段2: 语音识别 (20-90%)
    processingStage.value = '正在调用 Whisper AI...'
    store.addLog('info', '开始语音识别 (Whisper)')

    // 使用 Electron API 进行语音识别
    const result = await window.electronAPI.transcribe({
      videoPath: store.videoPath,
      language: sourceLanguage.value
    })

    if (result.error) {
      throw new Error(result.error)
    }

    progress.value = 90
    store.addLog('success', `语音识别完成，共识别 ${result.segments?.length || 0} 个片段`)

    // 阶段3: 处理字幕 (90-100%)
    processingStage.value = '正在处理字幕...'
    store.addLog('info', '开始生成字幕')

    const processedSegments = processSubtitles(result.segments || [])
    store.setSegments(processedSegments)

    progress.value = 100
    processingStage.value = '处理完成！'
    store.setCompleted()
    store.addLog('success', '所有处理已完成')

  } catch (e) {
    const errorMsg = e.message || '处理失败'
    const codeMatch = errorMsg.match(/E\d+/)
    errorCode.value = codeMatch ? codeMatch[0] : 'E999'
    error.value = errorMsg
    progress.value = 0
    store.setError(errorMsg, errorCode.value)
    store.addLog('error', errorMsg)
  }
}

function processSubtitles(原始Segments) {
  return 原始Segments.map((seg, i) => {
    let translated = seg.text
    if (translateTarget.value === 'zh' && sourceLanguage.value !== 'zh') {
      translated = translateToChinese(seg.text, sourceLanguage.value)
    }
    return {
      id: i + 1,
      start: seg.start,
      end: seg.end,
      text: seg.text,
      translated: translated
    }
  })
}

// 简单的翻译映射
const translationMap = {
  ja: {
    '你好': '你好', 'こんにちは': '你好', '元気ですか': '你好吗',
    '今天的天气': '今天的天气', '很好': '很好',
    '享受这个视频': '享受这个视频', '谢谢': '谢谢',
    '再见': '再见'
  }
}

function translateToChinese(text, sourceLang) {
  // 保持原文，用户可以手动翻译
  // 后续可以接入翻译 API
  return text
}

function selectSegment(index) {
  activeIndex.value = index
}

function adjustTime(index, delta) {
  const seg = segments.value[index]
  if (seg) {
    const newStart = Math.max(0, seg.start + delta)
    const newEnd = seg.end + delta
    store.updateSegment(index, { start: newStart, end: newEnd })
  }
}

function deleteSegment(index) {
  const newSegments = [...segments.value]
  newSegments.splice(index, 1)
  store.setSegments(newSegments)
}

function retryProcessing() {
  error.value = ''
  errorCode.value = ''
  startProcessing()
}

function handlePrev() {
  emit('prev')
}

function handleNext() {
  if (hasSubtitles.value) {
    store.nextStep()
    emit('next')
  }
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
</script>

<style lang="scss" scoped>
.step-process {
  max-width: 900px;
  margin: 0 auto;
}

.step-header {
  text-align: center;
  margin-bottom: $spacing-xl;

  &__title {
    font-size: 24px;
    font-weight: 600;
    color: $primary;
    margin-bottom: $spacing-sm;
  }

  &__desc {
    color: $text-secondary;
    font-size: 14px;
  }
}

.settings-panel {
  display: flex;
  align-items: flex-end;
  gap: $spacing-lg;
  flex-wrap: wrap;

  &__item {
    flex: 1;
    min-width: 200px;
  }

  &__label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: $text-secondary;
    margin-bottom: $spacing-xs;
  }

  &__actions {
    display: flex;
    gap: $spacing-sm;
  }
}

.progress-panel {
  margin-top: $spacing-lg;

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-sm;
    font-size: 14px;
    font-weight: 500;
  }

  &__percent {
    color: $accent;
    font-weight: 600;
  }

  &__stage {
    margin-top: $spacing-sm;
    font-size: 13px;
    color: $text-secondary;
    text-align: center;
  }
}

.progress-bar {
  height: 8px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  overflow: hidden;

  &__fill {
    height: 100%;
    background: linear-gradient(90deg, $accent, lighten($accent, 15%));
    transition: width 0.3s ease;

    &--error {
      background: $error;
    }
  }
}

.subtitle-preview {
  margin-top: $spacing-lg;

  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-md;
    padding-bottom: $spacing-sm;
    border-bottom: 1px solid rgba(0, 0, 0, 0.08);

    h3 {
      font-size: 16px;
      font-weight: 600;
      color: $primary;
    }
  }

  &__count {
    font-size: 12px;
    color: $text-secondary;
    background: rgba(0, 0, 0, 0.05);
    padding: 2px 8px;
    border-radius: 10px;
  }

  &__list {
    max-height: 300px;
    overflow-y: auto;
  }
}

.subtitle-item {
  padding: $spacing-sm $spacing-md;
  border-radius: $radius-md;
  cursor: pointer;
  transition: $transition;

  &:hover {
    background: rgba(0, 0, 0, 0.03);
  }

  &--active {
    background: rgba($accent, 0.1);
    border-left: 3px solid $accent;
  }

  &__time {
    font-size: 12px;
    color: $text-secondary;
    font-family: 'Consolas', monospace;
    margin-bottom: 4px;
  }

  &__text {
    font-size: 14px;
    color: $text-primary;
    line-height: 1.5;
  }

  &__actions {
    display: flex;
    gap: $spacing-xs;
    margin-top: $spacing-xs;
    opacity: 0;
    transition: $transition;
  }

  &:hover &__actions {
    opacity: 1;
  }
}

.btn--small {
  padding: 4px 8px;
  font-size: 11px;
}

.error-panel {
  margin-top: $spacing-lg;
  display: flex;
  align-items: flex-start;
  gap: $spacing-md;
  background: rgba($error, 0.05);
  border: 1px solid rgba($error, 0.2);

  &__icon {
    font-size: 24px;
  }

  &__content {
    flex: 1;
  }

  &__code {
    font-size: 12px;
    font-weight: 600;
    color: $error;
    margin-bottom: 4px;
  }

  &__message {
    font-size: 14px;
    color: $text-primary;
  }

  &__actions {
    display: flex;
    gap: $spacing-sm;
  }
}

.step-actions {
  display: flex;
  justify-content: space-between;
  margin-top: $spacing-xl;
}

.spinner-small {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
