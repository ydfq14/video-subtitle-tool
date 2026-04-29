# 智能字幕工坊 (Smart Subtitle Tool)

一个基于 PyQt5 + Whisper 的本地视频字幕生成工具，支持日语、英语、中文视频的自动语音识别、翻译和字幕合成。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-GUI-green.svg)
![Whisper](https://img.shields.io/badge/Whisper-Medium-orange.svg)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Video-red.svg)
![MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## 功能特性

- 语音识别 - 使用 OpenAI Whisper Medium 模型，本地运行，保护隐私
- 多语言支持 - 支持日语、英语、中文自动检测和识别
- 智能翻译 - 支持将日/英语字幕翻译为简体中文（腾讯云机器翻译 API）
- 字幕合成 - 自动将字幕烧录到视频，导出带字幕的 MP4 文件
- 可选导出 - 可选择只输出 SRT 字幕文件，或同时合成带字幕的视频
- 自动导出 - 每完成一个任务自动保存 SRT 字幕到输出目录
- 任务取消 - 支持取消当前任务，自动清理半成品文件
- 队列处理 - 最大队列 10 个视频，排队依次处理
- GPU 加速 - 支持 NVIDIA GPU (CUDA) 加速，也支持 CPU 模式
- 环境检测 - 启动时自动检测依赖，缺失的包自动安装
- 智能换行 - 仅在字幕过长时自动换行，保持字幕可读性
- 现代设置面板 - 卡片式设计，配置翻译 API、输出目录、模型路径

## 快速开始

### 环境要求

- Windows 10/11
- Python 3.8+
- FFmpeg（用于字幕合成，没有则只能输出字幕文件）

### 安装 FFmpeg

**使用 winget (推荐):**
```powershell
winget install Gyan.FFmpeg
```

**或手动安装:**
1. 访问 https://ffmpeg.org/download.html
2. 下载 Windows 版本
3. 将 `ffmpeg.exe` 添加到系统 PATH

### 安装依赖并运行

```bash
cd python
pip install -r requirements.txt
python gui.py
```

或双击运行 `启动智能字幕工坊.bat`

> 程序启动时会自动检测环境，缺失的 Python 包会自动安装。Whisper Medium 模型首次使用会自动下载（约 1.5GB）。

### 配置翻译 API（可选）

如果需要翻译功能，点击主界面右上角的齿轮图标进入设置，填入腾讯云 SecretId 和 SecretKey。也可以通过环境变量配置：

```bash
set SecretId=你的SecretId
set SecretKey=你的SecretKey
```

腾讯云机器翻译服务申请地址：https://cloud.tencent.com/product/tmt

## 使用方法

### 步骤一：添加视频
点击"添加视频文件"按钮，选择要处理的视频文件（支持 MP4、MOV、AVI、MKV、WebM 格式）。最多可添加 10 个文件排队处理。

### 步骤二：设置参数
- **源语言**: 选择"自动识别"、"日语"、"英语"或"中文"
- **加速方式**: 选择"GPU (CUDA)"（推荐）或"CPU"
- **翻译功能**: 选择"不翻译"或"翻译为简体中文"（需要配置 API 密钥）
- **合并字幕到视频**: 勾选则同时输出带字幕视频，取消勾选则只输出字幕文件

### 步骤三：查看结果
进度条实时显示处理进度。任务完成后自动输出到输出目录。

## 设置面板

点击右上角齿轮图标打开设置：

| 设置项 | 说明 |
|--------|------|
| Secret ID / Secret Key | 腾讯云翻译 API 凭证（选择翻译功能时会自动检测是否已配置） |
| 输出目录 | 字幕文件和合成视频的保存位置，留空使用项目 output 文件夹 |
| Whisper 模型路径 | 留空使用默认位置（自动下载），或指定自定义 .pt 模型文件路径 |

设置会保存到项目根目录的 `config.json`（该文件不会被提交到 Git，保护 API 密钥安全）。

## GPU 加速设置

```bash
pip uninstall torch -y
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

验证 GPU：
```python
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

## 项目结构

```
video-subtitle-tool/
├── python/
│   ├── gui.py                 # 主程序（PyQt5 桌面应用）
│   ├── requirements.txt        # Python 依赖
│   └── 启动智能字幕工坊.bat   # Windows 快捷启动
├── whisper/                    # Whisper 模型目录（自动创建）
├── config.example.json         # 配置文件模板
├── output/                     # 输出目录（自动创建）
└── README.md
```

## 技术栈

- **GUI**: PyQt5
- **语音识别**: OpenAI Whisper (Medium 模型)
- **翻译 API**: 腾讯云机器翻译 TMT
- **视频处理**: FFmpeg
- **加速**: CUDA (可选)

## 许可证

MIT License
