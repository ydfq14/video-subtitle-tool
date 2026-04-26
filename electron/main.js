const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron')
const path = require('path')
const { spawn, execSync } = require('child_process')
const fs = require('fs')
const log = require('electron-log')

// 配置日志
log.transports.file.level = 'info'
log.transports.file.maxSize = 10 * 1024 * 1024

// 全局异常处理
process.on('uncaughtException', (error) => {
  log.error('Uncaught Exception:', error)
})

process.on('unhandledRejection', (reason, promise) => {
  log.error('Unhandled Rejection at:', promise, 'reason:', reason)
})

let mainWindow = null
let pythonProcess = null

// Python 服务路径
function getPythonScriptPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'python', 'whisper_service.py')
  }
  return path.join(__dirname, '..', 'python', 'whisper_service.py')
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  // 开发模式加载本地文件
  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    log.info('Application window ready')
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(() => {
  createWindow()
  log.info('App started successfully')

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// ============ IPC 处理器 ============

// 打开文件对话框
ipcMain.handle('dialog:openFile', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: '视频文件', extensions: ['mp4', 'mov', 'avi', 'mkv', 'webm'] }
    ],
    ...options
  })
  return result
})

// 保存文件对话框
ipcMain.handle('dialog:saveFile', async (event, options) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    filters: [
      { name: '视频文件', extensions: ['mp4'] },
      { name: '字幕文件', extensions: ['srt'] }
    ],
    ...options
  })
  return result
})

// 获取视频信息
ipcMain.handle('video:getInfo', async (event, filePath) => {
  log.info('Getting video info for:', filePath)

  try {
    const output = execSync(`ffprobe -v quiet -print_format json -show_format -show_streams "${filePath}"`, {
      encoding: 'utf-8'
    })
    const info = JSON.parse(output)
    const videoStream = info.streams.find(s => s.codec_type === 'video')
    const audioStream = info.streams.find(s => s.codec_type === 'audio')
    const format = info.format

    return {
      duration: parseFloat(format.duration) || 0,
      width: videoStream ? videoStream.width : 0,
      height: videoStream ? videoStream.height : 0,
      size: parseInt(format.size) || 0,
      format: format.format_name || '',
      hasAudio: !!audioStream,
      bitrate: parseInt(format.bit_rate) || 0
    }
  } catch (error) {
    log.error('ffprobe failed:', error)
    throw new Error('E101: 无法读取视频信息')
  }
})

// 语音识别（调用 Python Whisper）
ipcMain.handle('whisper:transcribe', async (event, { videoPath, language }) => {
  log.info('Starting Whisper transcription for:', videoPath)

  return new Promise((resolve, reject) => {
    const pythonScript = getPythonScriptPath()

    // 检查 Python 是否可用
    try {
      execSync('python --version', { encoding: 'utf-8' })
    } catch (e) {
      reject(new Error('E004: Python 未安装，请先安装 Python 3.8+'))
      return
    }

    // 检查 Whisper 是否安装
    try {
      execSync('python -c "import whisper"', { encoding: 'utf-8' })
    } catch (e) {
      log.warn('Whisper not installed, trying to install...')
      try {
        execSync('pip install openai-whisper -q', { encoding: 'utf-8' })
      } catch (installError) {
        reject(new Error('E004: Whisper 安装失败，请运行: pip install openai-whisper'))
        return
      }
    }

    const args = [
      pythonScript,
      videoPath,
      language || 'ja',
      '--json'
    ]

    const proc = spawn('python', args, {
      windowsHide: true
    })

    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (data) => {
      stdout += data.toString()
      // 发送进度更新
      try {
        const lines = stdout.trim().split('\n')
        const lastLine = lines[lines.length - 1]
        if (lastLine.startsWith('PROGRESS:')) {
          const progress = JSON.parse(lastLine.replace('PROGRESS:', ''))
          mainWindow?.webContents.send('process:progress', progress)
        }
      } catch (e) {
        // 忽略解析错误
      }
    })

    proc.stderr.on('data', (data) => {
      stderr += data.toString()
      log.info('[Whisper]', data.toString().trim())
    })

    proc.on('close', (code) => {
      if (code === 0) {
        try {
          // 解析最后一行 JSON
          const lines = stdout.trim().split('\n')
          const resultLine = lines[lines.length - 1]
          const result = JSON.parse(resultLine)
          log.info('Transcription completed, segments:', result.segments?.length || 0)
          resolve(result)
        } catch (e) {
          log.error('Failed to parse result:', e, stdout)
          reject(new Error('E002: 语音识别结果解析失败'))
        }
      } else {
        log.error('Whisper failed:', stderr)
        reject(new Error('E002: 语音识别失败 - ' + (stderr || '未知错误').split('\n')[0]))
      }
    })

    proc.on('error', (error) => {
      log.error('Python process error:', error)
      reject(new Error('E004: 无法启动 Python 服务'))
    })
  })
})

// 生成字幕文件
ipcMain.handle('subtitle:generate', async (event, { segments, outputPath, format }) => {
  log.info('Generating subtitle file:', outputPath)

  try {
    if (format === 'srt') {
      const content = generateSRT(segments)
      fs.writeFileSync(outputPath, '\ufeff' + content, 'utf-8')
    } else if (format === 'ass') {
      const content = generateASS(segments)
      fs.writeFileSync(outputPath, content, 'utf-8')
    }
    log.info('Subtitle file generated successfully')
    return outputPath
  } catch (error) {
    log.error('Failed to generate subtitle:', error)
    throw new Error('E003: 字幕文件生成失败')
  }
})

// 烧录字幕到视频
ipcMain.handle('video:burnSubtitles', async (event, { videoPath, subtitlePath, outputPath, options }) => {
  log.info('Burning subtitles into video')

  return new Promise((resolve, reject) => {
    const fontSize = options?.fontSize || 24
    const position = options?.position || 'bottom'

    // 构建 FFmpeg 命令
    const args = [
      '-i', videoPath,
      '-vf', `subtitles='${subtitlePath.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}':force_style='FontSize=${fontSize},PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'`,
      '-c:a', 'copy',
      '-preset', 'fast',
      '-y',
      outputPath
    ]

    const proc = spawn('ffmpeg', args, {
      windowsHide: true
    })

    let stderr = ''

    proc.stderr.on('data', (data) => {
      stderr += data.toString()

      // 解析进度
      const str = data.toString()
      const timeMatch = str.match(/time=(\d+):(\d+):(\d+)/)
      if (timeMatch) {
        const hours = parseInt(timeMatch[1])
        const minutes = parseInt(timeMatch[2])
        const seconds = parseInt(timeMatch[3])
        const currentSeconds = hours * 3600 + minutes * 60 + seconds
        mainWindow?.webContents.send('process:progress', {
          status: 'processing',
          progress: currentSeconds,
          message: `合成中... ${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
        })
      }
    })

    proc.on('close', (code) => {
      if (code === 0) {
        log.info('Video with burned subtitles created')
        resolve(outputPath)
      } else {
        log.error('ffmpeg failed:', stderr)
        reject(new Error('E006: 视频合成失败'))
      }
    })

    proc.on('error', (error) => {
      log.error('ffmpeg process error:', error)
      reject(new Error('E005: FFmpeg 不可用，请安装 FFmpeg'))
    })
  })
})

// 打开文件夹
ipcMain.handle('shell:openPath', async (event, filePath) => {
  shell.showItemInFolder(filePath)
})

// 打开 URL
ipcMain.handle('shell:openExternal', async (event, url) => {
  shell.openExternal(url)
})

// ============ 辅助函数 ============

function generateSRT(segments) {
  return segments.map((seg, i) => {
    const start = formatSRTTime(seg.start)
    const end = formatSRTTime(seg.end)
    const text = seg.translated || seg.text
    return `${i + 1}\n${start} --> ${end}\n${text}\n`
  }).join('\n')
}

function generateASS(segments) {
  const lines = [
    '[Script Info]',
    'Title: Smart Subtitle Tool',
    'ScriptType: v4.00+',
    '',
    '[V4+ Styles]',
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
    'Style: Default,Microsoft YaHei,24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,134',
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
