<template>
  <div class="step-upload">
    <div class="step-header">
      <h2 class="step-header__title">📤 上传视频</h2>
      <p class="step-header__desc">选择本地视频文件，支持 MP4、MOV、AVI、MKV、WebM 格式</p>
    </div>

    <div
      class="upload-zone"
      :class="{ 'upload-zone--dragover': isDragOver, 'upload-zone--has-file': hasFile }"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDrop"
      @click="handleClick"
    >
      <input
        ref="fileInput"
        type="file"
        accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm"
        @change="handleFileSelect"
        hidden
      />

      <template v-if="!hasFile">
        <div class="upload-zone__icon">🎬</div>
        <div class="upload-zone__text">
          <p class="upload-zone__main">点击选择视频文件</p>
          <p class="upload-zone__sub">或拖拽视频文件到这里</p>
        </div>
        <div class="upload-zone__formats">
          支持格式：MP4、MOV、AVI、MKV、WebM（最大 2GB）
        </div>
      </template>

      <template v-else>
        <div class="video-preview" v-if="videoUrl">
          <video
            ref="videoElement"
            :src="videoUrl"
            class="video-preview__player"
            @loadedmetadata="handleVideoLoaded"
            @error="handleVideoError"
          ></video>
        </div>
        <div class="file-info" v-if="fileInfo">
          <div class="file-info__icon">📄</div>
          <div class="file-info__details">
            <p class="file-info__name">{{ fileInfo.name }}</p>
            <p class="file-info__meta">
              {{ formatSize(fileInfo.size) }} |
              {{ videoInfo ? `${videoInfo.width}×${videoInfo.height}` : '加载中...' }} |
              {{ videoInfo ? formatDuration(videoInfo.duration) : '加载中...' }}
            </p>
          </div>
          <button class="btn btn--ghost file-info__remove" @click.stop="handleRemove">
            🗑️
          </button>
        </div>
      </template>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-message">
      <span class="error-message__icon">⚠️</span>
      <span class="error-message__text">{{ error }}</span>
    </div>

    <!-- 操作按钮 -->
    <div class="step-actions" v-if="hasFile && !error">
      <button
        class="btn btn--primary btn--large"
        :disabled="!videoInfo || store.isProcessing"
        @click="handleNext"
      >
        <span>下一步</span>
        <span>→</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useProjectStore } from '../stores/project'

const emit = defineEmits(['next'])

const store = useProjectStore()

const fileInput = ref(null)
const videoElement = ref(null)
const isDragOver = ref(false)
const selectedFile = ref(null)
const videoUrl = ref('')
const error = ref('')

const hasFile = computed(() => !!selectedFile.value)
const videoInfo = computed(() => store.videoInfo)

const fileInfo = computed(() => {
  if (!selectedFile.value) return null
  return {
    name: selectedFile.value.name,
    size: selectedFile.value.size
  }
})

const maxSize = 2 * 1024 * 1024 * 1024 // 2GB

async function handleClick() {
  if (!hasFile.value) {
    try {
      const result = await window.electronAPI.openFileDialog()
      if (!result.canceled && result.filePaths.length > 0) {
        const filePath = result.filePaths[0]
        await loadVideoFromPath(filePath)
      }
    } catch (e) {
      // 如果 Electron API 不可用（开发模式），使用原生文件选择
      fileInput.value?.click()
    }
  }
}

function handleDragOver(e) {
  isDragOver.value = true
}

function handleDragLeave(e) {
  isDragOver.value = false
}

function handleDrop(e) {
  isDragOver.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    handleFile(files[0])
  }
}

function handleFileSelect(e) {
  const files = e.target.files
  if (files && files.length > 0) {
    handleFile(files[0])
  }
}

async function loadVideoFromPath(filePath) {
  error.value = ''

  // 验证文件类型
  const ext = filePath.split('.').pop().toLowerCase()
  const allowedExts = ['mp4', 'mov', 'avi', 'mkv', 'webm']
  if (!allowedExts.includes(ext)) {
    error.value = '不支持的视频格式，请上传 MP4、MOV、AVI、MKV 或 WebM 文件'
    return
  }

  try {
    // 使用 Electron 获取视频信息
    const info = await window.electronAPI.getVideoInfo(filePath)

    selectedFile.value = {
      name: filePath.split(/[\\/]/).pop(),
      size: info.size,
      path: filePath
    }

    // 使用 file:// 协议播放本地视频
    videoUrl.value = 'file:///' + filePath.replace(/\\/g, '/')

    store.setVideo(videoUrl.value, {
      duration: info.duration,
      width: info.width,
      height: info.height,
      size: info.size
    })

    store.addLog('info', `已选择视频: ${selectedFile.value.name} (${formatSize(info.size)})`)
    store.addLog('success', `视频信息: ${info.width}×${info.height}, 时长 ${formatDuration(info.duration)}`)

  } catch (e) {
    error.value = '视频文件读取失败: ' + e.message
    store.addLog('error', error.value)
  }
}

async function handleFile(file) {
  error.value = ''

  // 验证文件类型
  const ext = file.name.split('.').pop().toLowerCase()
  const allowedExts = ['mp4', 'mov', 'avi', 'mkv', 'webm']
  if (!allowedExts.includes(ext)) {
    error.value = '不支持的视频格式，请上传 MP4、MOV、AVI、MKV 或 WebM 文件'
    return
  }

  // 验证文件大小
  if (file.size > maxSize) {
    error.value = '文件大小超过 2GB 限制'
    return
  }

  selectedFile.value = file

  // 创建 blob URL 供预览
  videoUrl.value = URL.createObjectURL(file)
  store.addLog('info', `已选择视频: ${file.name} (${formatSize(file.size)})`)

  // 获取视频信息
  try {
    await nextTick()
    await loadVideoInfo()
  } catch (e) {
    error.value = '视频文件读取失败，请尝试重新上传'
    store.addLog('error', error.value)
  }
}

async function loadVideoInfo() {
  await nextTick()

  return new Promise((resolve, reject) => {
    const video = videoElement.value
    if (!video) {
      setTimeout(() => loadVideoInfo().then(resolve).catch(reject), 100)
      return
    }

    const handleMeta = () => {
      const info = {
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
        size: selectedFile.value.size
      }
      store.setVideo(videoUrl.value, info)
      store.addLog('success', `视频信息读取完成: ${info.width}×${info.height}, 时长 ${formatDuration(info.duration)}`)
      resolve(info)
    }

    const handleError = () => {
      reject(new Error('视频加载失败'))
    }

    if (video.readyState >= 1) {
      handleMeta()
    } else {
      video.onloadedmetadata = handleMeta
      video.onerror = handleError
      setTimeout(() => {
        if (video.readyState < 1) {
          reject(new Error('视频加载超时'))
        }
      }, 10000)
    }
  })
}

function handleVideoError() {
  error.value = '视频文件读取失败，请尝试重新上传'
  store.addLog('error', error.value)
}

function handleRemove() {
  if (videoUrl.value && videoUrl.value.startsWith('blob:')) {
    URL.revokeObjectURL(videoUrl.value)
  }
  selectedFile.value = null
  videoUrl.value = ''
  error.value = ''
  if (fileInput.value) {
    fileInput.value.value = ''
  }
  store.reset()
  store.addLog('info', '已移除视频文件')
}

function handleNext() {
  if (hasFile.value && videoInfo.value) {
    store.nextStep()
    emit('next')
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
}

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}
</script>

<style lang="scss" scoped>
.step-upload {
  max-width: 800px;
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

.upload-zone {
  position: relative;
  min-height: 300px;
  border: 2px dashed rgba(0, 0, 0, 0.15);
  border-radius: $radius-lg;
  background: $bg-card;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: $transition;
  overflow: hidden;

  &:hover {
    border-color: $accent;
    background: rgba($accent, 0.02);
  }

  &--dragover {
    border-color: $accent;
    border-style: solid;
    background: rgba($accent, 0.05);
  }

  &--has-file {
    min-height: auto;
    padding: $spacing-lg;
  }

  &__icon {
    font-size: 64px;
    margin-bottom: $spacing-md;
    opacity: 0.8;
  }

  &__text {
    text-align: center;
  }

  &__main {
    font-size: 18px;
    font-weight: 500;
    color: $text-primary;
    margin-bottom: $spacing-xs;
  }

  &__sub {
    font-size: 14px;
    color: $text-secondary;
  }

  &__formats {
    margin-top: $spacing-lg;
    font-size: 12px;
    color: $text-secondary;
    padding: $spacing-xs $spacing-md;
    background: rgba(0, 0, 0, 0.03);
    border-radius: $radius-sm;
  }
}

.video-preview {
  width: 100%;
  max-width: 600px;
  margin-bottom: $spacing-md;

  &__player {
    width: 100%;
    border-radius: $radius-md;
    background: #000;
  }
}

.file-info {
  display: flex;
  align-items: center;
  gap: $spacing-md;
  width: 100%;
  max-width: 600px;
  padding: $spacing-md;
  background: rgba(0, 0, 0, 0.03);
  border-radius: $radius-md;

  &__icon {
    font-size: 32px;
  }

  &__details {
    flex: 1;
    min-width: 0;
  }

  &__name {
    font-weight: 500;
    color: $text-primary;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__meta {
    font-size: 12px;
    color: $text-secondary;
    margin-top: 2px;
  }

  &__remove {
    padding: $spacing-xs;
    font-size: 18px;
  }
}

.error-message {
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  margin-top: $spacing-md;
  padding: $spacing-md;
  background: rgba($error, 0.1);
  border-radius: $radius-md;
  color: $error;
  font-size: 14px;

  &__icon {
    font-size: 18px;
  }
}

.step-actions {
  display: flex;
  justify-content: center;
  margin-top: $spacing-xl;
}

.btn--large {
  padding: 14px 40px;
  font-size: 16px;
}
</style>
