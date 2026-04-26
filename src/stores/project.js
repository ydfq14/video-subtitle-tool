import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useProjectStore = defineStore('project', () => {
  // 状态
  const currentStep = ref(1)
  const status = ref('idle') // idle, uploading, processing, completed, error
  const progress = ref(0)
  const videoPath = ref('')
  const videoInfo = ref(null)
  const sourceLanguage = ref('ja') // ja: 日语, en: 英语
  const segments = ref([])
  const outputPath = ref('')
  const error = ref(null)

  // 日志
  const logs = ref([])

  function addLog(level, message, code = null) {
    const timestamp = new Date()
    logs.value.push({
      id: Date.now() + Math.random(),
      timestamp,
      level,
      message,
      code
    })
  }

  function clearLogs() {
    logs.value = []
  }

  // 步骤导航
  function goToStep(step) {
    if (step >= 1 && step <= 3) {
      currentStep.value = step
    }
  }

  function nextStep() {
    if (currentStep.value < 3) {
      currentStep.value++
    }
  }

  function prevStep() {
    if (currentStep.value > 1) {
      currentStep.value--
    }
  }

  // 重置
  function reset() {
    currentStep.value = 1
    status.value = 'idle'
    progress.value = 0
    videoPath.value = ''
    videoInfo.value = null
    segments.value = []
    outputPath.value = ''
    error.value = null
    clearLogs()
  }

  // 设置视频
  function setVideo(path, info) {
    videoPath.value = path
    videoInfo.value = info
    status.value = 'idle'
    progress.value = 0
    error.value = null
  }

  // 设置字幕段
  function setSegments(newSegments) {
    segments.value = newSegments
  }

  // 更新字幕段
  function updateSegment(index, updates) {
    if (segments.value[index]) {
      segments.value[index] = { ...segments.value[index], ...updates }
    }
  }

  // 设置处理状态
  function setProcessing(percent = 0) {
    status.value = 'processing'
    progress.value = percent
  }

  // 设置完成
  function setCompleted(output) {
    status.value = 'completed'
    progress.value = 100
    outputPath.value = output
  }

  // 设置错误
  function setError(errorMessage, errorCode = null) {
    status.value = 'error'
    error.value = { message: errorMessage, code: errorCode }
    addLog('error', errorMessage, errorCode)
  }

  // 计算属性
  const hasVideo = computed(() => !!videoPath.value)
  const hasSubtitles = computed(() => segments.value.length > 0)
  const isProcessing = computed(() => status.value === 'processing')
  const isCompleted = computed(() => status.value === 'completed')
  const hasError = computed(() => status.value === 'error')

  return {
    // 状态
    currentStep,
    status,
    progress,
    videoPath,
    videoInfo,
    sourceLanguage,
    segments,
    outputPath,
    error,
    logs,

    // 计算属性
    hasVideo,
    hasSubtitles,
    isProcessing,
    isCompleted,
    hasError,

    // 方法
    addLog,
    clearLogs,
    goToStep,
    nextStep,
    prevStep,
    reset,
    setVideo,
    setSegments,
    updateSegment,
    setProcessing,
    setCompleted,
    setError
  }
})
