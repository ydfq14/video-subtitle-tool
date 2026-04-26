<template>
  <div class="step-export">
    <div class="step-header">
      <h2 class="step-header__title">🎬 预览与合并</h2>
      <p class="step-header__desc">预览字幕效果，导出带字幕的视频</p>
    </div>

    <div class="export-layout">
      <!-- 视频预览区 -->
      <div class="preview-section">
        <div class="video-container" ref="videoContainer">
          <video
            ref="videoPlayer"
            :src="videoUrl"
            class="video-player"
            @timeupdate="handleTimeUpdate"
            @loadedmetadata="handleVideoLoaded"
            @play="isPlaying = true"
            @pause="isPlaying = false"
          ></video>

          <!-- 字幕叠加层 -->
          <div
            class="subtitle-overlay"
            :class="`subtitle-overlay--${subtitlePosition}`"
            v-if="currentSubtitle"
          >
            <span class="subtitle-overlay__text" :style="{ fontSize: fontSize + 'px' }">
              {{ currentSubtitle }}
            </span>
          </div>

          <!-- 控制栏 -->
          <div class="video-controls">
            <button class="video-controls__btn" @click="togglePlay">
              {{ isPlaying ? '⏸️' : '▶️' }}
            </button>
            <div class="video-controls__progress" @click="seekVideo">
              <div
                class="video-controls__progress-fill"
                :style="{ width: `${progressPercent}%` }"
              ></div>
            </div>
            <span class="video-controls__time">
              {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
            </span>
            <button class="video-controls__btn" @click="toggleMute">
              {{ isMuted ? '🔇' : '🔊' }}
            </button>
          </div>
        </div>

        <!-- 字幕轨道 -->
        <div class="subtitle-track">
          <div
            v-for="(seg, index) in segments"
            :key="index"
            class="subtitle-track__item"
            :class="{ 'subtitle-track__item--active': isActiveSegment(seg) }"
            :style="getSegmentStyle(seg)"
            @click="seekToSegment(seg)"
          ></div>
        </div>
      </div>

      <!-- 字幕编辑区 -->
      <div class="subtitle-section">
        <div class="subtitle-editor card">
          <div class="subtitle-editor__header">
            <h3>字幕编辑</h3>
            <span class="subtitle-count">{{ segments.length }} 条</span>
          </div>

          <div class="subtitle-list">
            <div
              v-for="(seg, index) in segments"
              :key="index"
              class="subtitle-entry"
              :class="{ 'subtitle-entry--active': activeIndex === index }"
              @click="selectSegment(index)"
            >
              <div class="subtitle-entry__time">
                <input
                  type="text"
                  :value="formatSRTTime(seg.start)"
                  @change="(e) => updateTime(index, 'start', e.target.value)"
                  class="time-input"
                />
                <span class="time-separator">→</span>
                <input
                  type="text"
                  :value="formatSRTTime(seg.end)"
                  @change="(e) => updateTime(index, 'end', e.target.value)"
                  class="time-input"
                />
              </div>
              <textarea
                :value="seg.translated || seg.text"
                @change="(e) => updateText(index, e.target.value)"
                class="text-input"
                rows="2"
              ></textarea>
              <div class="subtitle-entry__actions">
                <button class="btn btn--ghost btn--tiny" @click.stop="adjustTime(index, -1)">-1s</button>
                <button class="btn btn--ghost btn--tiny" @click.stop="adjustTime(index, 1)">+1s</button>
                <button class="btn btn--ghost btn--tiny" @click.stop="deleteSegment(index)">🗑️</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 导出设置 -->
        <div class="export-settings card">
          <h3>导出设置</h3>

          <div class="setting-row">
            <label>字幕位置</label>
            <select v-model="subtitlePosition" class="select">
              <option value="bottom">底部居中</option>
              <option value="top">顶部居中</option>
            </select>
          </div>

          <div class="setting-row">
            <label>字体大小</label>
            <select v-model="fontSize" class="select">
              <option value="18">小 (18px)</option>
              <option value="24">中 (24px)</option>
              <option value="32">大 (32px)</option>
              <option value="40">特大 (40px)</option>
            </select>
          </div>

          <div class="export-info" v-if="isExporting">
            <div class="export-info__progress">
              <span>{{ exportStage }}</span>
              <span>{{ exportProgress }}%</span>
            </div>
            <div class="progress-bar">
              <div class="progress-bar__fill" :style="{ width: `${exportProgress}%` }"></div>
            </div>
          </div>

          <div class="export-actions">
            <button class="btn btn--secondary" @click="downloadSRT" :disabled="isExporting">
              📥 下载 SRT 字幕
            </button>
            <button class="btn btn--primary" @click="burnSubtitles" :disabled="isExporting">
              <span v-if="isExporting" class="spinner-small"></span>
              <span v-else>🎬</span>
              {{ isExporting ? '合成中...' : '合成视频' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 完成提示 -->
    <div v-if="exportComplete" class="success-modal">
      <div class="success-card card">
        <div class="success-card__icon">✅</div>
        <h3>导出成功！</h3>
        <p>带字幕视频已准备好</p>
        <div class="success-card__preview" v-if="outputVideoUrl">
          <video :src="outputVideoUrl" controls class="success-card__video"></video>
        </div>
        <div class="success-card__actions">
          <button class="btn btn--secondary" @click="openOutputFolder">
            📂 打开文件夹
          </button>
          <button class="btn btn--secondary" @click="downloadVideo">
            📥 下载视频
          </button>
          <button class="btn btn--primary" @click="handleDone">
            完成
          </button>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="step-actions">
      <button class="btn btn--secondary" @click="handlePrev">
        <span>←</span> 上一步
      </button>
      <button class="btn btn--ghost" @click="handleReset">
        🔄 重置项目
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useProjectStore } from '../stores/project'

const emit = defineEmits(['prev'])

const store = useProjectStore()

const videoPlayer = ref(null)
const videoUrl = ref('')
const outputVideoUrl = ref('')
const outputFilePath = ref('')
const isPlaying = ref(false)
const isMuted = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const activeIndex = ref(-1)
const currentSubtitle = ref('')

const subtitlePosition = ref('bottom')
const fontSize = ref('24')
const isExporting = ref(false)
const exportProgress = ref(0)
const exportStage = ref('')
const exportComplete = ref(false)

const segments = computed(() => store.segments)

onMounted(() => {
  if (store.videoPath) {
    videoUrl.value = store.videoPath
  }
})

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatSRTTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`
}

const progressPercent = computed(() => {
  if (duration.value === 0) return 0
  return (currentTime.value / duration.value) * 100
})

function handleVideoLoaded() {
  if (videoPlayer.value) {
    duration.value = videoPlayer.value.duration
  }
}

function handleTimeUpdate() {
  if (videoPlayer.value) {
    currentTime.value = videoPlayer.value.currentTime
    updateCurrentSubtitle()
  }
}

function updateCurrentSubtitle() {
  const time = currentTime.value
  const seg = segments.value.find(s => time >= s.start && time <= s.end)
  currentSubtitle.value = seg ? (seg.translated || seg.text) : ''
}

function isActiveSegment(seg) {
  return currentTime.value >= seg.start && currentTime.value <= seg.end
}

function getSegmentStyle(seg) {
  if (duration.value === 0) return {}
  const left = (seg.start / duration.value) * 100
  const width = ((seg.end - seg.start) / duration.value) * 100
  return {
    left: `${left}%`,
    width: `${Math.max(width, 0.5)}%`
  }
}

function seekToSegment(seg) {
  if (videoPlayer.value) {
    videoPlayer.value.currentTime = seg.start
  }
}

function togglePlay() {
  if (videoPlayer.value) {
    if (isPlaying.value) {
      videoPlayer.value.pause()
    } else {
      videoPlayer.value.play()
    }
    isPlaying.value = !isPlaying.value
  }
}

function toggleMute() {
  if (videoPlayer.value) {
    videoPlayer.value.muted = !videoPlayer.value.muted
    isMuted.value = !isMuted.value
  }
}

function seekVideo(e) {
  if (videoPlayer.value) {
    const rect = e.currentTarget.getBoundingClientRect()
    const percent = (e.clientX - rect.left) / rect.width
    videoPlayer.value.currentTime = percent * duration.value
  }
}

function selectSegment(index) {
  activeIndex.value = index
  if (videoPlayer.value && segments.value[index]) {
    videoPlayer.value.currentTime = segments.value[index].start
  }
}

function updateTime(index, field, value) {
  const time = parseSRTTime(value)
  if (time !== null) {
    store.updateSegment(index, { [field]: time })
  }
}

function parseSRTTime(str) {
  const match = str.match(/(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/)
  if (!match) return null
  const [, h, m, s, ms] = match
  return parseInt(h) * 3600 + parseInt(m) * 60 + parseInt(s) + parseInt(ms) / 1000
}

function updateText(index, value) {
  store.updateSegment(index, { translated: value })
}

function adjustTime(index, delta) {
  const seg = segments.value[index]
  if (seg) {
    const newStart = Math.max(0, seg.start + delta)
    const newEnd = Math.max(newStart + 0.1, seg.end + delta)
    store.updateSegment(index, { start: newStart, end: newEnd })
  }
}

function deleteSegment(index) {
  const newSegments = [...segments.value]
  newSegments.splice(index, 1)
  store.setSegments(newSegments)
}

function generateSRTContent() {
  return segments.value.map((seg, i) => {
    const start = formatSRTTime(seg.start)
    const end = formatSRTTime(seg.end)
    const text = seg.translated || seg.text
    return `${i + 1}\n${start} --> ${end}\n${text}\n`
  }).join('\n')
}

async function downloadSRT() {
  try {
    const result = await window.electronAPI.saveFileDialog({
      defaultPath: 'subtitle.srt'
    })

    if (result.canceled) return

    await window.electronAPI.generateSubtitle({
      segments: segments.value,
      outputPath: result.filePath,
      format: 'srt'
    })

    store.addLog('success', 'SRT字幕已保存: ' + result.filePath)
    alert('SRT字幕已保存成功！')

  } catch (e) {
    store.addLog('error', 'SRT下载失败: ' + e.message)
    alert('SRT下载失败: ' + e.message)
  }
}

async function burnSubtitles() {
  isExporting.value = true
  exportProgress.value = 0
  exportStage.value = '准备中...'
  exportComplete.value = false

  try {
    // 让用户选择保存位置
    const saveResult = await window.electronAPI.saveFileDialog({
      defaultPath: 'output_with_subtitle.mp4'
    })

    if (saveResult.canceled) {
      isExporting.value = false
      return
    }

    const outputPath = saveResult.filePath
    const videoPath = store.videoPath

    // 先生成临时字幕文件
    const tempSubtitlePath = outputPath.replace('.mp4', '.srt')
    await window.electronAPI.generateSubtitle({
      segments: segments.value,
      outputPath: tempSubtitlePath,
      format: 'srt'
    })

    exportProgress.value = 30
    exportStage.value = '正在合成视频...'

    // 调用 FFmpeg 烧录字幕
    const result = await window.electronAPI.burnSubtitles({
      videoPath: videoPath,
      subtitlePath: tempSubtitlePath,
      outputPath: outputPath,
      options: {
        fontSize: parseInt(fontSize.value),
        position: subtitlePosition.value
      }
    })

    exportProgress.value = 100
    exportStage.value = '完成！'

    outputFilePath.value = result
    outputVideoUrl.value = 'file://' + result.replace(/\\/g, '/')

    exportComplete.value = true
    store.addLog('success', '视频合成完成: ' + result)

    // 删除临时字幕文件
    try {
      const fs = require('fs')
      fs.unlinkSync(tempSubtitlePath)
    } catch (e) {}

  } catch (e) {
    store.addLog('error', '视频合成失败: ' + e.message)
    alert('视频合成失败: ' + e.message)
  } finally {
    isExporting.value = false
  }
}

function openOutputFolder() {
  if (outputFilePath.value) {
    window.electronAPI.openPath(outputFilePath.value)
  }
}

function downloadVideo() {
  if (!outputFilePath.value) return

  // 使用 shell 打开文件所在文件夹
  window.electronAPI.openPath(outputFilePath.value)
}

function handlePrev() {
  emit('prev')
}

function handleReset() {
  if (confirm('确定要重置项目吗？所有未保存的数据将丢失。')) {
    if (outputVideoUrl.value && outputVideoUrl.value.startsWith('blob:')) {
      URL.revokeObjectURL(outputVideoUrl.value)
    }
    store.reset()
  }
}
</script>

<style lang="scss" scoped>
.step-export {
  max-width: 1200px;
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

.export-layout {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: $spacing-xl;

  @media (max-width: 1000px) {
    grid-template-columns: 1fr;
  }
}

.preview-section {
  .video-container {
    position: relative;
    background: #000;
    border-radius: $radius-lg;
    overflow: hidden;
  }
}

.video-player {
  width: 100%;
  display: block;
  max-height: 500px;
}

.subtitle-overlay {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  max-width: 80%;
  text-align: center;
  pointer-events: none;

  &--bottom {
    bottom: 60px;
  }

  &--top {
    top: 20px;
  }

  &__text {
    display: inline-block;
    padding: 8px 16px;
    background: rgba(0, 0, 0, 0.75);
    color: white;
    line-height: 1.4;
    border-radius: 4px;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);
  }
}

.video-controls {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: $spacing-sm;
  padding: $spacing-sm $spacing-md;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.8));

  &__btn {
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    padding: 4px;
    transition: transform 0.2s;

    &:hover {
      transform: scale(1.1);
    }
  }

  &__progress {
    flex: 1;
    height: 4px;
    background: rgba(255, 255, 255, 0.3);
    border-radius: 2px;
    cursor: pointer;

    &-fill {
      height: 100%;
      background: $accent;
      border-radius: 2px;
      transition: width 0.1s;
    }
  }

  &__time {
    font-size: 12px;
    color: white;
    font-family: 'Consolas', monospace;
    min-width: 100px;
  }
}

.subtitle-track {
  position: relative;
  height: 20px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 0 0 $radius-md $radius-md;

  &__item {
    position: absolute;
    top: 2px;
    height: 16px;
    background: rgba($primary, 0.4);
    border-radius: 2px;
    cursor: pointer;
    transition: background 0.2s;

    &:hover {
      background: rgba($primary, 0.6);
    }

    &--active {
      background: rgba($accent, 0.7);
    }
  }
}

.subtitle-section {
  display: flex;
  flex-direction: column;
  gap: $spacing-lg;
}

.subtitle-editor {
  &__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: $spacing-md;

    h3 {
      font-size: 16px;
      font-weight: 600;
      color: $primary;
    }
  }
}

.subtitle-count {
  font-size: 12px;
  color: $text-secondary;
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 8px;
  border-radius: 10px;
}

.subtitle-list {
  max-height: 300px;
  overflow-y: auto;
}

.subtitle-entry {
  padding: $spacing-sm;
  border-radius: $radius-md;
  margin-bottom: $spacing-sm;
  background: rgba(0, 0, 0, 0.03);
  cursor: pointer;
  transition: $transition;

  &:hover {
    background: rgba(0, 0, 0, 0.06);
  }

  &--active {
    background: rgba($accent, 0.1);
    border-left: 3px solid $accent;
  }

  &__time {
    display: flex;
    align-items: center;
    gap: $spacing-xs;
    margin-bottom: $spacing-xs;
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

.time-input {
  width: 100px;
  padding: 4px 8px;
  font-size: 12px;
  font-family: 'Consolas', monospace;
  border: 1px solid rgba(0, 0, 0, 0.15);
  border-radius: $radius-sm;
  outline: none;

  &:focus {
    border-color: $accent;
  }
}

.time-separator {
  color: $text-secondary;
  font-size: 12px;
}

.text-input {
  width: 100%;
  padding: $spacing-xs;
  font-size: 13px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: $radius-sm;
  resize: vertical;
  outline: none;
  font-family: inherit;

  &:focus {
    border-color: $accent;
  }
}

.btn--tiny {
  padding: 2px 6px;
  font-size: 10px;
}

.export-settings {
  h3 {
    font-size: 16px;
    font-weight: 600;
    color: $primary;
    margin-bottom: $spacing-md;
  }
}

.setting-row {
  margin-bottom: $spacing-md;

  label {
    display: block;
    font-size: 13px;
    color: $text-secondary;
    margin-bottom: $spacing-xs;
  }
}

.export-info {
  margin-top: $spacing-md;
  padding: $spacing-sm;
  background: rgba($primary, 0.05);
  border-radius: $radius-md;

  &__progress {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: $text-secondary;
    margin-bottom: $spacing-xs;
  }
}

.progress-bar {
  height: 4px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
  overflow: hidden;

  &__fill {
    height: 100%;
    background: $accent;
    transition: width 0.3s ease;
  }
}

.export-actions {
  display: flex;
  gap: $spacing-sm;
  margin-top: $spacing-lg;

  .btn {
    flex: 1;
  }
}

.success-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.success-card {
  text-align: center;
  min-width: 400px;
  max-width: 90vw;

  &__icon {
    font-size: 48px;
    margin-bottom: $spacing-md;
  }

  h3 {
    font-size: 20px;
    color: $primary;
    margin-bottom: $spacing-sm;
  }

  p {
    color: $text-secondary;
    margin-bottom: $spacing-md;
  }

  &__preview {
    margin: $spacing-md 0;
  }

  &__video {
    width: 100%;
    max-height: 300px;
    border-radius: $radius-md;
  }

  &__actions {
    display: flex;
    gap: $spacing-md;
    justify-content: center;
    margin-top: $spacing-lg;
  }
}

.step-actions {
  display: flex;
  justify-content: flex-start;
  margin-top: $spacing-xl;
  gap: $spacing-md;
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
