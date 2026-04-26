# 🎬 智能字幕工坊 (Smart Subtitle Tool)

一个功能强大的本地视频字幕生成工具，支持日语、英语、中文视频的自动语音识别和字幕生成。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-GUI-green.svg)
![Whisper](https://img.shields.io/badge/Whisper-AI-orange.svg)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Video-red.svg)

## ✨ 功能特性

- 🎯 **高精度语音识别** - 使用 OpenAI Whisper 模型，本地运行，保护隐私
- 🌐 **多语言支持** - 支持日语、英语、中文视频
- ⚡ **灵活加速** - 支持 GPU (CUDA) 和 CPU 两种模式
- 🎬 **一键合成** - 将字幕烧录到视频，导出带字幕的 MP4 文件
- 📥 **多格式导出** - 支持导出 SRT、ASS 字幕文件
- 📝 **实时预览** - 边看视频边检查字幕效果
- 🔧 **字幕编辑** - 可视化编辑字幕时间轴和文字

## 🚀 快速开始

### 环境要求

- Windows 10/11
- Python 3.8+
- FFmpeg
- (可选) NVIDIA GPU + CUDA 用于 GPU 加速

### 安装 FFmpeg

**Windows (使用 winget):**
```powershell
winget install Gyan.FFmpeg
```

**或手动安装:**
1. 访问 https://ffmpeg.org/download.html
2. 下载 Windows 版本
3. 将 `ffmpeg.exe` 添加到系统 PATH

### 安装依赖

```bash
cd python
pip install -r requirements.txt
```

### 运行

```bash
python gui.py
```

或双击运行 `启动智能字幕工坊.bat`

## 📖 使用方法

### 1. 选择视频
点击"选择视频文件"按钮，选择要处理的视频文件（支持 MP4、MOV、AVI、MKV、WebM 格式）

### 2. 设置参数
- **源语言**: 选择视频中的语言（日语/英语/中文）
- **加速模式**: 选择 GPU（推荐）或 CPU

### 3. 开始处理
点击"开始处理"按钮，Whisper 将自动识别视频中的语音并生成字幕

### 4. 编辑字幕（如需要）
在字幕列表中可以查看和编辑每条字幕的时间和文字

### 5. 导出结果
- 点击"下载 SRT 字幕"导出字幕文件
- 点击"合成带字幕视频"导出带字幕的 MP4 文件

## ⚙️ GPU 加速设置

### CUDA 版本安装

如果使用 NVIDIA GPU，需要安装支持 CUDA 的 PyTorch:

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
│   ├── whisper_service.py      # Whisper 服务
│   └── 启动智能字幕工坊.bat   # 启动脚本
├── whisper/                   # Whisper 模型目录
│   └── medium.pt             # Medium 模型（可选）
└── README.md
```

## 🔧 模型设置

默认使用 `base` 模型。如需使用其他模型:

1. 下载模型: https://github.com/openai/whisper#available-models-and-languages
2. 将模型文件放入 `whisper/` 目录
3. 修改 `gui.py` 中的模型名称:
   ```python
   model = whisper.load_model("medium")  # tiny/base/small/medium/large
   ```

## 📝 技术栈

- **GUI**: PyQt5
- **语音识别**: OpenAI Whisper
- **视频处理**: FFmpeg
- **加速**: CUDA/cuDNN (可选)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 语音识别模型
- [FFmpeg](https://ffmpeg.org/) - 视频处理工具
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架
