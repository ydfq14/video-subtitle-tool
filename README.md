# 🎬 智能字幕工坊 (Smart Subtitle Tool)

一个基于 PyQt5 + Whisper 的本地视频字幕生成工具，支持日语、英语、中文视频的自动语音识别、翻译和字幕合成。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-GUI-green.svg)
![Whisper](https://img.shields.io/badge/Whisper-Medium-orange.svg)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Video-red.svg)
![MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ 功能特性

### 核心功能
- 🎯 **高精度语音识别** - 使用 OpenAI Whisper Medium 模型，本地运行，保护隐私
- 🌐 **多语言支持** - 支持日语、英语、中文自动检测和识别
- 🔄 **智能翻译** - 支持将字幕翻译为简体中文（腾讯云机器翻译 API）
- 🎬 **一键合成** - 自动将字幕烧录到视频，导出带字幕的 MP4 文件
- 📥 **自动导出** - 每完成一个任务自动保存 SRT 字幕和合成视频到输出目录
- ⏹️ **任务取消** - 支持取消当前任务，自动清理半成品文件
- 📁 **输出目录** - 可自定义输出目录，默认输出到项目 output 文件夹

### 翻译优化
- 📝 **上下文翻译** - 保留前一条字幕作为参考，提升翻译连贯性
- ⏱️ **智能限流** - 500ms 间隔请求，避免 API 限流

### 处理模式
- ⚡ **GPU 加速** - 支持 NVIDIA GPU (CUDA) 加速
- 💻 **CPU 模式** - 无 GPU 时可使用 CPU 运行
- 📋 **队列处理** - 最大队列 10 个视频，排队依次处理

## 🚀 快速开始

### 环境要求

- Windows 10/11
- Python 3.8+
- FFmpeg
- NVIDIA GPU + CUDA (可选，用于 GPU 加速)

### 1. 安装 FFmpeg

**使用 winget (推荐):**
```powershell
winget install Gyan.FFmpeg
```

**或手动安装:**
1. 访问 https://ffmpeg.org/download.html
2. 下载 Windows 版本
3. 将 `ffmpeg.exe` 添加到系统 PATH

### 2. 安装依赖

```bash
cd python
pip install -r requirements.txt
```

### 3. 配置翻译 API (可选)

如果需要翻译功能，需要设置腾讯云环境变量:

```bash
# Windows
set SecretId=你的SecretId
set SecretKey=你的SecretKey

# 或在代码中直接修改 translate_text_to_chinese 函数
```

### 4. 运行

```bash
cd python
python gui.py
```

或双击运行 `启动智能字幕工坊.bat`

## 📖 使用方法

### 1. 添加视频
点击"添加视频文件"按钮，选择要处理的视频文件（支持 MP4、MOV、AVI、MKV、WebM 格式）。最多可添加 10 个文件排队处理。

### 2. 设置参数
- **源语言**: 选择"自动识别"、"日语"、"英语"或"中文"
- **加速方式**: 选择"GPU (CUDA)"（推荐）或"CPU"
- **翻译功能**: 选择"不翻译"或"翻译为简体中文"
- **输出目录**: 点击"选择目录"设置输出位置

### 3. 开始处理
点击"开始处理"按钮，Whisper 将自动识别视频中的语音并生成字幕。如果选择了翻译，会自动调用翻译 API。

### 4. 查看进度
进度条会实时显示处理进度:
- 0-20%: 加载模型
- 20-60%: 语音转写
- 60-70%: 翻译字幕（如启用）
- 75%: 保存字幕文件
- 80-100%: 合成视频

### 5. 完成导出
任务完成后会自动输出:
- `{文件名}_subtitle.srt` - SRT 字幕文件
- `{文件名}_subtitled.mp4` - 带字幕的视频文件

## 🔧 GPU 加速设置

### 安装 CUDA 版 PyTorch

```bash
pip uninstall torch -y
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 验证 GPU

```python
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

## 📁 项目结构

```
video-subtitle-tool/
├── python/
│   ├── gui.py                 # 主程序
│   ├── requirements.txt        # Python 依赖
│   └── 启动智能字幕工坊.bat   # Windows 启动脚本
├── whisper/                   # Whisper 模型目录
│   └── medium.pt             # Medium 模型（首次运行自动下载）
├── output/                    # 输出目录
├── resources/                 # 应用资源
├── scripts/                   # 构建脚本
├── src/                       # 前端源码 (Electron)
├── public/                    # 静态资源
├── index.html
├── package.json
├── vite.config.js
├── SPEC.md                    # 项目规格说明
└── README.md
```

## ⚙️ 技术栈

- **GUI**: PyQt5
- **语音识别**: OpenAI Whisper (Medium 模型)
- **翻译 API**: 腾讯云机器翻译 TMT
- **视频处理**: FFmpeg
- **加速**: CUDA (可选)

## 📝 使用提示

1. **首次运行**: 程序会自动下载 Whisper Medium 模型（约 1.5GB）
2. **翻译功能**: 需要配置腾讯云 SecretId 和 SecretKey
3. **批量处理**: 添加多个文件后自动排队处理，无需手动操作
4. **取消任务**: 点击"取消任务"按钮可终止当前任务，清理半成品

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 语音识别模型
- [FFmpeg](https://ffmpeg.org/) - 视频处理工具
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架
- [腾讯云](https://cloud.tencent.com/) - 机器翻译 API
