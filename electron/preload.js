const { contextBridge, ipcRenderer } = require('electron')

// 暴露安全 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 文件对话框
  openFileDialog: (options) => ipcRenderer.invoke('dialog:openFile', options),
  saveFileDialog: (options) => ipcRenderer.invoke('dialog:saveFile', options),

  // 视频处理
  getVideoInfo: (filePath) => ipcRenderer.invoke('video:getInfo', filePath),
  burnSubtitles: (params) => ipcRenderer.invoke('video:burnSubtitles', params),

  // 语音识别
  transcribe: (params) => ipcRenderer.invoke('whisper:transcribe', params),

  // 字幕生成
  generateSubtitle: (params) => ipcRenderer.invoke('subtitle:generate', params),

  // 系统
  openPath: (filePath) => ipcRenderer.invoke('shell:openPath', filePath),
  openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),

  // 进度监听
  onProgress: (callback) => {
    ipcRenderer.on('process:progress', (event, data) => callback(data))
  },

  // 移除进度监听
  removeProgressListener: () => {
    ipcRenderer.removeAllListeners('process:progress')
  }
})

// 版本信息
contextBridge.exposeInMainWorld('appInfo', {
  version: '1.0.0',
  name: '智能字幕工坊'
})
