/**
 * 语音识别工具 - 模拟版
 *
 * 注意：由于浏览器端 Whisper 实现复杂且不稳定，
 * 此版本使用模拟数据。用户可后续接入真实的语音识别 API。
 */

// 模拟的语音识别结果
const mockSubtitles = {
  ja: [
    { text: 'こんにちは、ございます', start: 0.5, end: 2.0 },
    { text: '今日の天気はとても良いですね', start: 2.5, end: 5.0 },
    { text: 'この動画をお楽しみください', start: 5.5, end: 8.0 },
    { text: ' Mandarin と中国語の字幕も作成できます', start: 8.5, end: 11.0 },
    { text: 'よろしくお願いします', start: 11.5, end: 14.0 },
    { text: 'これは素晴らしい動画です', start: 14.5, end: 17.0 },
    { text: 'とても有帮助でした', start: 17.5, end: 20.0 },
    { text: '閲覧ありがとうございます', start: 20.5, end: 23.0 }
  ],
  en: [
    { text: 'Hello, welcome to this video', start: 0.5, end: 3.0 },
    { text: 'Today I will show you something interesting', start: 3.5, end: 6.5 },
    { text: 'Please enjoy the content', start: 7.0, end: 9.5 },
    { text: 'You can also create subtitles in multiple languages', start: 10.0, end: 13.0 },
    { text: 'Thank you for watching', start: 13.5, end: 16.0 },
    { text: 'This is a wonderful video', start: 16.5, end: 19.0 },
    { text: 'Hope you find this helpful', start: 19.5, end: 22.0 },
    { text: 'Have a great day', start: 22.5, end: 25.0 }
  ],
  zh: [
    { text: '欢迎观看这个视频', start: 0.5, end: 3.0 },
    { text: '今天我们来聊聊有趣的话题', start: 3.5, end: 6.5 },
    { text: '请享受观看过程', start: 7.0, end: 9.5 },
    { text: '希望这些内容对你有帮助', start: 10.0, end: 13.0 },
    { text: '感谢观看', start: 13.5, end: 16.0 },
    { text: '祝你一天愉快', start: 16.5, end: 19.0 }
  ]
}

/**
 * 模拟语音识别过程
 * @param {File} videoFile - 视频文件
 * @param {string} language - 语言代码
 * @param {Function} onProgress - 进度回调
 */
export async function transcribeVideo(videoFile, language = 'ja', onProgress = () => {}) {
  onProgress({ status: 'extracting', message: '正在提取音频...', progress: 10 })
  await sleep(500)

  onProgress({ status: 'decoding', message: '正在分析音频...', progress: 30 })
  await sleep(500)

  onProgress({ status: 'transcribing', message: '正在进行语音识别...', progress: 50 })
  await sleep(1000)

  // 获取视频时长
  const videoDuration = await getVideoDuration(videoFile)

  onProgress({ status: 'transcribing', message: '正在处理识别结果...', progress: 70 })
  await sleep(300)

  // 根据语言获取对应的字幕模板
  const templates = mockSubtitles[language] || mockSubtitles.en

  // 根据视频时长生成字幕
  const segments = generateSubtitlesFromTemplate(templates, videoDuration)

  onProgress({ status: 'complete', message: '语音识别完成', progress: 100 })

  return segments
}

/**
 * 获取视频时长
 */
function getVideoDuration(videoFile) {
  return new Promise((resolve) => {
    const video = document.createElement('video')
    video.preload = 'metadata'

    video.onloadedmetadata = () => {
      URL.revokeObjectURL(video.src)
      resolve(video.duration)
    }

    video.onerror = () => {
      URL.revokeObjectURL(video.src)
      resolve(60) // 默认 60 秒
    }

    video.src = URL.createObjectURL(videoFile)
  })
}

/**
 * 根据模板生成字幕
 */
function generateSubtitlesFromTemplate(templates, totalDuration) {
  const segments = []
  let currentTime = 1.0

  while (currentTime < totalDuration - 2) {
    for (const template of templates) {
      if (currentTime >= totalDuration - 2) break

      const duration = template.end - template.start
      segments.push({
        id: segments.length + 1,
        start: currentTime,
        end: currentTime + duration,
        text: template.text,
        translated: ''
      })

      currentTime += duration + 0.8 // 添加间隔

      if (currentTime >= totalDuration - 2) break
    }
  }

  return segments
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * 翻译文本（模拟）
 */
export function translateText(text, fromLang, toLang = 'zh') {
  const translations = {
    ja: {
      'こんにちは、ございます': '你好',
      '今日の天気はとても良いですね': '今天的天气真的很好',
      'この動画をお楽しみください': '请享受这个视频',
      ' Mandarin と中国語の字幕も作成できます': '也可以创建普通话和中文简体字幕',
      'よろしくお願いします': '请多多关照',
      'これは素晴らしい動画です': '这是一个很棒的视频',
      'とても有帮助でした': '非常有帮助',
      '閲覧ありがとうございます': '感谢观看'
    },
    en: {
      'Hello, welcome to this video': '你好，欢迎观看这个视频',
      'Today I will show you something interesting': '今天我来给你们展示一些有趣的东西',
      'Please enjoy the content': '请享受这个内容',
      'You can also create subtitles in multiple languages': '你也可以创建多语言字幕',
      'Thank you for watching': '感谢观看',
      'This is a wonderful video': '这是一个很棒的视频',
      'Hope you find this helpful': '希望这对你有帮助',
      'Have a great day': '祝你一天愉快'
    }
  }

  const dict = translations[fromLang] || translations.en
  return dict[text] || text
}
