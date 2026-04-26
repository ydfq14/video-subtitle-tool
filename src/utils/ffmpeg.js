/**
 * FFmpeg 工具 - 简化版
 *
 * 使用 CSS/HTML 叠加方式实现字幕预览，
 * 视频合成使用备选方案。
 */

// FFmpeg 加载状态
let ffmpeg = null
let loading = false
let loaded = false

/**
 * 加载 FFmpeg
 */
export async function loadFFmpeg(onProgress = () => {}) {
  if (loaded && ffmpeg) {
    return ffmpeg
  }

  if (loading) {
    // 等待加载完成
    while (loading) {
      await new Promise(r => setTimeout(r, 200))
    }
    return ffmpeg
  }

  loading = true

  try {
    onProgress({ status: 'loading', message: '正在加载视频处理引擎...' })

    const { FFmpeg } = await import('@ffmpeg/ffmpeg')
    const { fetchFile, toBlobURL } = await import('@ffmpeg/util')

    ffmpeg = new FFmpeg()

    ffmpeg.on('log', ({ message }) => {
      console.log('[FFmpeg]', message)
    })

    ffmpeg.on('progress', ({ progress }) => {
      onProgress({
        status: 'processing',
        progress: Math.round((progress || 0) * 100),
        message: `处理中... ${Math.round((progress || 0) * 100)}%`
      })
    })

    const baseURL = 'https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm'

    await ffmpeg.load({
      coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
      wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm')
    })

    loaded = true
    loading = false
    onProgress({ status: 'ready', message: '视频处理引擎加载完成' })

    return ffmpeg

  } catch (error) {
    loading = false
    console.error('FFmpeg 加载失败:', error)
    throw new Error('视频处理引擎加载失败')
  }
}

/**
 * 生成 SRT 字幕文件内容
 */
export function generateSRTContent(segments) {
  return segments.map((seg, i) => {
    const start = formatSRTTime(seg.start)
    const end = formatSRTTime(seg.end)
    const text = seg.translated || seg.text
    return `${i + 1}\n${start} --> ${end}\n${text}\n`
  }).join('\n')
}

/**
 * 生成 ASS 字幕文件内容
 */
export function generateASSContent(segments, options = {}) {
  const {
    fontSize = 24,
    fontName = 'Microsoft YaHei',
    primaryColor = '&H00FFFFFF',
    outlineColor = '&H00000000',
    position = 'bottom'
  } = options

  const alignment = position === 'bottom' ? 2 : 8

  const lines = [
    '[Script Info]',
    'Title: Smart Subtitle Tool',
    'ScriptType: v4.00+',
    '',
    '[V4+ Styles]',
    `Style: Default,${fontName},${fontSize},${primaryColor},&H000000FF,${outlineColor},&H00000000,0,0,0,0,100,100,0,0,1,2,2,${alignment},10,10,10,134`,
    '',
    '[Events]',
    'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'
  ]

  segments.forEach(seg => {
    const start = formatASSTime(seg.start)
    const end = formatASSTime(seg.end)
    const text = (seg.translated || seg.text).replace(/\n/g, '\\N').replace(/'/g, "'")
    lines.push(`Dialogue: 0,${start},${end},Default,,0,0,0,,${text}`)
  })

  return lines.join('\n')
}

/**
 * 将字幕烧录到视频中
 */
export async function burnSubtitles(videoFile, segments, options = {}, onProgress = () => {}) {
  try {
    const ff = await loadFFmpeg(onProgress)

    onProgress({ status: 'processing', message: '正在准备文件...', progress: 10 })

    // 生成 SRT 字幕
    const srtContent = generateSRTContent(segments)
    const srtBlob = new Blob([srtContent], { type: 'text/plain' })

    // 写入文件
    await ff.writeFile('subtitle.srt', await fetchFile(srtBlob))

    const videoExt = videoFile.name.split('.').pop()
    const inputName = `input.${videoExt}`
    await ff.writeFile(inputName, await fetchFile(videoFile))

    onProgress({ status: 'processing', message: '正在合成视频...', progress: 30 })

    // 执行合成
    await ff.exec([
      '-i', inputName,
      '-vf', `subtitles=subtitle.srt:force_style='FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000'`,
      '-c:a', 'copy',
      '-preset', 'fast',
      'output.mp4'
    ])

    onProgress({ status: 'processing', message: '正在读取输出文件...', progress: 90 })

    // 读取输出
    const data = await ff.readFile('output.mp4')

    // 清理
    await ff.deleteFile('subtitle.srt')
    await ff.deleteFile(inputName)
    await ff.deleteFile('output.mp4')

    onProgress({ status: 'complete', message: '视频合成完成', progress: 100 })

    return new Blob([data.buffer], { type: 'video/mp4' })

  } catch (error) {
    console.error('视频合成失败:', error)

    // 返回 null 表示合成失败，但不抛出异常
    // 上层会处理降级方案
    return null
  }
}

// 辅助函数
function formatSRTTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`
}

function formatASSTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const cs = Math.round((seconds % 1) * 100)
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(cs).padStart(2, '0')}`
}
