#!/usr/bin/env python3
"""
智能字幕工坊 - 桌面应用
使用 PyQt5 + Whisper + FFmpeg
"""


import hashlib
import hmac
import urllib.request
import time
import sys
import os
import json
import tempfile
import subprocess
import threading
import queue
from datetime import datetime, timezone

# 翻译 API 限流：每秒最多 2 次请求（增加间隔减少限流）
_last_translate_time = 0
_translate_min_interval = 0.5  # 每秒最多 2 次

# 翻译上下文：保留前一条字幕用于优化翻译
_translation_context = ""
_context_max_length = 100  # 上下文最大长度

# 最大队列长度
MAX_QUEUE_SIZE = 10

# -*- coding: utf-8 -*-
import io

# 修复 Windows 控制台编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 尝试导入 PyQt5
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QFileDialog, QProgressBar, QTextEdit,
        QComboBox, QMessageBox, QGroupBox, QListWidget
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QObject
    from PyQt5.QtGui import QFont
    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False
    os.system('pip install PyQt5 -q')
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QFileDialog, QProgressBar, QTextEdit,
        QComboBox, QMessageBox, QGroupBox, QListWidget
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QObject
    from PyQt5.QtGui import QFont

def check_dependencies():
    print("[OK] PyQt5 is installed")
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("[OK] FFmpeg is installed")
    except:
        print("[WARNING] FFmpeg not found")

def translate_text_to_chinese(text, from_lang='ja', context=''):
    """使用腾讯云机器翻译 API 将文本翻译为简体中文
    环境变量 SecretId 和 SecretKey 需要提前设置

    改进翻译准确率：
    1. 添加上下文参考（前一两句）
    2. 优化提示词风格
    3. 增加文本长度限制到 1000 字符
    """
    if not text or not text.strip():
        return text

    SECRET_ID = os.environ.get('SecretId', '')
    SECRET_KEY = os.environ.get('SecretKey', '')

    if not SECRET_ID or not SECRET_KEY:
        print("[翻译] 未配置环境变量 SecretId/SecretKey，使用原文")
        return text

    # 腾讯云 TMT API 参数
    service = "tmt"
    host = "tmt.tencentcloudapi.com"
    endpoint = f"https://{host}"
    action = "TextTranslate"
    version = "2018-03-21"
    region = "ap-guangzhou"  # 翻译接口不区分地域，可固定

    # 源语言和目标语言（转换为 API 需要的代码）
    # 支持 Whisper 返回的 ISO 639-1 代码 (ja, en, zh) 和完整名称 (japanese, english, chinese)
    lang_code_map = {
        'japanese': 'ja', 'ja': 'ja',
        'english': 'en', 'en': 'en',
        'chinese': 'zh', 'zh': 'zh'
    }
    from_lang_code = lang_code_map.get(from_lang, 'en')
    target_lang = 'zh'  # 简体中文（不是 zh-CHS）

    print(f"[翻译] from_lang={from_lang}, from_lang_code={from_lang_code}")  # 调试日志

    # 限制文本长度（单次请求最大 2000 字符，这里取 1000 确保安全）
    source_text = text[:1000]

    # 如果有上下文，在文本前加上参考（帮助翻译器理解语境）
    if context:
        # 只取最后一小段上下文
        context_hint = f"[参考上文：{context[-_context_max_length:]}] "
        source_text = context_hint + source_text

    # 请求参数
    payload = json.dumps({
        "SourceText": source_text,
        "Source": from_lang_code,
        "Target": target_lang,
        "ProjectId": 0
    })

    # 签名所需时间戳（UTC 秒级）
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")

    # ---------- 步骤 1：拼接待签名字符串 ----------
    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{host}\n"
    signed_headers = "content-type;host"
    hashed_request_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        f"{http_request_method}\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{hashed_request_payload}"
    )

    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{service}/tc3_request"
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = (
        f"{algorithm}\n"
        f"{timestamp}\n"
        f"{credential_scope}\n"
        f"{hashed_canonical_request}"
    )

    # ---------- 步骤 2：计算签名 ----------
    def _sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _sign(("TC3" + SECRET_KEY).encode("utf-8"), date)
    secret_service = _sign(secret_date, service)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    # ---------- 步骤 3：拼接 Authorization ----------
    authorization = (
        f"{algorithm} Credential={SECRET_ID}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    # ---------- 步骤 4：发送请求 ----------
    headers = {
        "Authorization": authorization,
        "Content-Type": ct,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
        "X-TC-Region": region,
    }

    # 限流：确保每秒最多 5 次请求
    global _last_translate_time
    elapsed = time.time() - _last_translate_time
    if elapsed < _translate_min_interval:
        time.sleep(_translate_min_interval - elapsed)
    _last_translate_time = time.time()

    try:
        req = urllib.request.Request(endpoint, data=payload.encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if "Response" in result and "TargetText" in result["Response"]:
                return result["Response"]["TargetText"]
            else:
                print(f"[翻译] API 返回异常: {result}")
                return text
    except Exception as e:
        print(f"[翻译] 请求失败: {e}")
        return text

class Worker(QObject):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, video_path, language, device='cuda', translate=False, output_dir=None, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.language = language
        self.device = device
        self.translate = translate
        self.output_dir = output_dir
        self._cancel_requested = False  # 取消标志

    def request_cancel(self):
        """请求取消当前任务"""
        self._cancel_requested = True

    def run(self):
        global _translation_context
        try:
            import whisper

            self.progress.emit({'status': 'loading', 'message': '正在加载 Whisper 模型...', 'percent': 5})

            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'whisper', 'medium.pt'
            )

            if os.path.exists(model_path):
                self.progress.emit({'status': 'loading', 'message': f'正在加载本地模型 ({self.device})...', 'percent': 20})
                model = whisper.load_model(model_path, device=self.device)
            else:
                self.progress.emit({'status': 'loading', 'message': f'正在下载 medium 模型 ({self.device})...', 'percent': 20})
                model = whisper.load_model("medium", device=self.device)

            self.progress.emit({'status': 'transcribing', 'message': '正在识别语音...', 'percent': 30})

            # 开始转写（不带进度回调，避免复杂化）
            result = model.transcribe(
                self.video_path,
                language=self.language,
                task='transcribe'
            )

            # 检查是否被取消
            if self._cancel_requested:
                self.cancelled.emit()
                return

            # 转写完成，获取检测到的语言
            detected_lang = result.get('language', 'en')  # Whisper 检测到的语言
            print(f"[DEBUG] 自动检测到语言: {detected_lang}")  # 调试日志
            seg_list = result.get('segments', [])
            total_segs = len(seg_list)

            if self.translate and detected_lang != 'zh':
                self.progress.emit({'status': 'translating', 'message': f'准备翻译 {total_segs} 个片段（检测到语言: {detected_lang}）...', 'percent': 60})
            else:
                self.progress.emit({'status': 'processing', 'message': '正在处理结果...', 'percent': 70})

            # 重置翻译上下文
            _translation_context = ""

            # 处理片段（翻译）
            segments = []
            for i, seg in enumerate(seg_list):
                # 检查是否被取消
                if self._cancel_requested:
                    self.cancelled.emit()
                    return

                original_text = seg['text'].strip()
                translated_text = original_text

                # 如果选择翻译且源语言不是中文，则翻译为简体中文
                if self.translate and detected_lang != 'zh':
                    # 翻译阶段进度: 60% - 95%
                    trans_percent = 60 + int((i + 1) / total_segs * 35) if total_segs > 0 else 90
                    self.progress.emit({'status': 'translating', 'message': f'正在翻译 [{i+1}/{total_segs}]: {original_text[:15]}...', 'percent': trans_percent})
                    # 传入上下文用于优化翻译，使用检测到的语言
                    translated_text = translate_text_to_chinese(original_text, detected_lang, _translation_context)

                    # 更新上下文（保留最近的几条字幕）
                    if _translation_context:
                        _translation_context += " " + original_text
                    else:
                        _translation_context = original_text
                    # 限制上下文长度
                    if len(_translation_context) > 300:
                        _translation_context = _translation_context[-200:]

                segments.append({
                    'id': len(segments) + 1,
                    'start': round(seg['start'], 2),
                    'end': round(seg['end'], 2),
                    'text': original_text,
                    'translated': translated_text if self.translate else ''
                })

            # 所有处理完成，转写+翻译阶段结束（进度70%）
            self.progress.emit({'status': 'complete', 'message': '识别翻译完成!', 'percent': 70})

            self.finished.emit({
                'segments': segments,
                'text': result.get('text', ''),
                'language': detected_lang
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class BurnWorker(QObject):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, video_path, subtitle_content, output_path, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.subtitle_content = subtitle_content
        self.output_path = output_path
        self._cancel_requested = False
        self._process = None

    def request_cancel(self):
        """请求取消当前任务"""
        self._cancel_requested = True
        if self._process:
            try:
                self._process.terminate()
            except:
                pass

    def run(self):
        try:
            temp_dir = tempfile.gettempdir()
            temp_sub = os.path.join(temp_dir, 'subtitle_temp.ass')

            with open(temp_sub, 'w', encoding='utf-8-sig') as f:
                f.write(self.subtitle_content)

            self.progress.emit({'percent': 20, 'message': '字幕文件已生成'})

            sub_filename = 'subtitle_temp.ass'
            video_abs = os.path.abspath(self.video_path).replace('\\', '/')
            output_abs = os.path.abspath(self.output_path).replace('\\', '/')

            cmd = [
                'ffmpeg', '-y',
                '-i', video_abs,
                '-vf', f'subtitles={sub_filename}',
                '-c:a', 'copy',
                '-preset', 'ultrafast',
                output_abs
            ]

            self.progress.emit({'percent': 30, 'message': '开始合成视频...'})

            self._process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                cwd=temp_dir
            )

            stderr_output = []
            while True:
                # 检查是否被取消
                if self._cancel_requested:
                    try:
                        os.unlink(temp_sub)
                    except:
                        pass
                    try:
                        os.unlink(output_abs)
                    except:
                        pass
                    self.cancelled.emit()
                    return

                line = self._process.stderr.readline()
                if not line and self._process.poll() is not None:
                    break
                stderr_output.append(line)
                if 'time=' in line:
                    self.progress.emit({'percent': 50, 'message': '合成中...'})

            stderr_text = ''.join(stderr_output)

            try:
                os.unlink(temp_sub)
            except:
                pass

            # 检查是否被取消
            if self._cancel_requested:
                try:
                    os.unlink(output_abs)
                except:
                    pass
                self.cancelled.emit()
                return

            if self._process.returncode == 0:
                self.progress.emit({'percent': 100, 'message': '合成完成!'})
                self.finished.emit(self.output_path)
            else:
                # 如果合成失败，删除半成品文件
                try:
                    os.unlink(output_abs)
                except:
                    pass
                self.error.emit(f'FFmpeg 失败 (返回码: {self._process.returncode})\n命令:\n{" ".join(cmd)}\n错误:\n{stderr_text[-1000:]}')

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.video_path = None
        self.video_info = None
        self.segments = []

        # 输出目录设置（必须在 init_ui 之前）
        self.output_dir = self._get_default_output_dir()

        self.init_ui()

        # 多文件处理相关
        self.video_files = []  # 待处理的文件列表
        self.active_workers = {}  # {video_path: {'worker': Worker, 'thread': Thread, 'segments': []}}
        self.task_queue = queue.Queue()
        self.completed_results = {}  # {video_path: {'segments': [], 'text': '', 'language': ''}}
        # 当前正在运行的任务（保持引用防止 GC）
        self.current_worker = None
        self.current_thread = None
        self.current_video_path = None  # 当前处理中的视频路径
        self.current_burn_worker = None  # 当前合成任务
        self.current_burn_thread = None

    def _get_default_output_dir(self):
        """获取默认输出目录"""
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(script_dir, 'output')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        return output_dir

    def init_ui(self):
        self.setWindowTitle('智能字幕工坊')
        self.setGeometry(100, 100, 950, 750)

        # 设置整体样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dcdde1;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2c3e50;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
            QPushButton#process_btn {
                background-color: #27ae60;
                font-size: 14px;
                padding: 10px 20px;
            }
            QPushButton#process_btn:hover {
                background-color: #229954;
            }
            QPushButton#process_btn:disabled {
                background-color: #95a5a6;
            }
            QPushButton#export_btn {
                background-color: #9b59b6;
            }
            QPushButton#export_btn:hover {
                background-color: #8e44ad;
            }
            QComboBox {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 5px 10px;
                background-color: white;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
            }
            QTextEdit {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                background-color: #fafafa;
            }
            QListWidget {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                background-color: white;
            }
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: #ecf0f1;
                text-align: center;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background-color: #3498db;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题区域
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 10)

        title = QLabel('🎬 智能字幕工坊')
        title.setFont(QFont('Microsoft YaHei', 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('color: #2c3e50;')
        title_layout.addWidget(title)

        subtitle = QLabel('视频语音转字幕 · 支持日/英/中 · 智能翻译')
        subtitle.setFont(QFont('Microsoft YaHei', 10))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet('color: #7f8c8d;')
        title_layout.addWidget(subtitle)

        layout.addWidget(title_container)

        # Step 1: 选择视频
        step1_group = QGroupBox('📁 步骤一：选择视频（支持批量，最多10个排队）')
        step1_layout = QVBoxLayout()
        step1_layout.setSpacing(10)

        # 文件选择按钮
        video_btn_layout = QHBoxLayout()
        video_btn = QPushButton('📂 添加视频文件')
        video_btn.clicked.connect(self.select_video)
        video_btn_layout.addWidget(video_btn)

        clear_btn = QPushButton('🗑️ 清空列表')
        clear_btn.clicked.connect(self.clear_video_list)
        video_btn_layout.addWidget(clear_btn)
        self.clear_btn = clear_btn

        self.file_count_label = QLabel('已选择 0 个文件')
        self.file_count_label.setStyleSheet('color: #7f8c8d;')
        self.file_count_label.setFont(QFont('Microsoft YaHei', 9))
        video_btn_layout.addWidget(self.file_count_label)
        video_btn_layout.addStretch()
        step1_layout.addLayout(video_btn_layout)

        # 文件列表
        self.video_list_widget = QListWidget()
        self.video_list_widget.setMaximumHeight(100)
        step1_layout.addWidget(self.video_list_widget)

        step1_group.setLayout(step1_layout)
        layout.addWidget(step1_group)

        # Step 2: 设置
        step2_group = QGroupBox('⚙️ 步骤二：设置参数')
        step2_layout = QHBoxLayout()
        step2_layout.setSpacing(20)

        # 源语言
        lang_widget = QWidget()
        lang_layout = QVBoxLayout(lang_widget)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        lang_label = QLabel('源语言')
        lang_label.setFont(QFont('Microsoft YaHei', 9, QFont.Bold))
        lang_layout.addWidget(lang_label)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(['自动识别', '日语', '英语', '中文'])
        self.lang_combo.setCurrentIndex(0)
        self.lang_combo.setMinimumWidth(120)
        lang_layout.addWidget(self.lang_combo)
        step2_layout.addWidget(lang_widget)

        # 加速方式
        device_widget = QWidget()
        device_layout = QVBoxLayout(device_widget)
        device_layout.setContentsMargins(0, 0, 0, 0)
        device_label = QLabel('加速方式')
        device_label.setFont(QFont('Microsoft YaHei', 9, QFont.Bold))
        device_layout.addWidget(device_label)
        self.device_combo = QComboBox()
        self.device_combo.addItems(['GPU (CUDA)', 'CPU'])
        self.device_combo.setCurrentIndex(0)
        self.device_combo.setMinimumWidth(120)
        device_layout.addWidget(self.device_combo)
        step2_layout.addWidget(device_widget)

        # 翻译选项
        trans_widget = QWidget()
        trans_layout = QVBoxLayout(trans_widget)
        trans_layout.setContentsMargins(0, 0, 0, 0)
        trans_label = QLabel('翻译功能')
        trans_label.setFont(QFont('Microsoft YaHei', 9, QFont.Bold))
        trans_layout.addWidget(trans_label)
        self.translate_combo = QComboBox()
        self.translate_combo.addItems(['不翻译', '翻译为简体中文'])
        self.translate_combo.setCurrentIndex(0)
        self.translate_combo.setMinimumWidth(150)
        trans_layout.addWidget(self.translate_combo)
        step2_layout.addWidget(trans_widget)

        # 输出目录
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_label = QLabel('输出目录')
        output_label.setFont(QFont('Microsoft YaHei', 9, QFont.Bold))
        output_layout.addWidget(output_label)

        output_btn_layout = QHBoxLayout()
        self.output_dir_btn = QPushButton('📁 选择目录')
        self.output_dir_btn.setMinimumWidth(100)
        self.output_dir_btn.clicked.connect(self.select_output_dir)
        output_btn_layout.addWidget(self.output_dir_btn)

        self.output_dir_label = QLabel('默认')
        self.output_dir_label.setStyleSheet('color: #7f8c8d; font-size: 9px;')
        self.output_dir_label.setToolTip(self.output_dir)
        output_btn_layout.addWidget(self.output_dir_label)
        output_layout.addLayout(output_btn_layout)
        step2_layout.addWidget(output_widget)

        # 取消按钮（处理中可见）
        self.cancel_btn = QPushButton('⏹️ 取消任务')
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_current_task)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setMinimumWidth(100)
        step2_layout.addWidget(self.cancel_btn)

        # 开始按钮
        step2_layout.addStretch()
        self.process_btn = QPushButton('🚀 开始处理')
        self.process_btn.setObjectName('process_btn')
        self.process_btn.clicked.connect(self.process_video)
        self.process_btn.setEnabled(False)
        self.process_btn.setMinimumWidth(140)
        step2_layout.addWidget(self.process_btn)

        step2_group.setLayout(step2_layout)
        layout.addWidget(step2_group)

        # Step 3: 结果
        step3_group = QGroupBox('📋 步骤三：结果与导出')
        step3_layout = QVBoxLayout()
        step3_layout.setSpacing(10)

        # 字幕列表
        self.subtitle_list = QListWidget()
        step3_layout.addWidget(self.subtitle_list, 1)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(20)
        step3_layout.addWidget(self.progress_bar)

        # 当前处理文件标签
        self.current_file_label = QLabel('')
        self.current_file_label.setFont(QFont('Microsoft YaHei', 9))
        self.current_file_label.setStyleSheet('color: #3498db;')
        self.current_file_label.setVisible(False)
        step3_layout.addWidget(self.current_file_label)

        # 日志区域
        log_label = QLabel('📝 处理日志')
        log_label.setFont(QFont('Microsoft YaHei', 9, QFont.Bold))
        step3_layout.addWidget(log_label)


        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        step3_layout.addWidget(self.log_text)

        step3_group.setLayout(step3_layout)
        layout.addWidget(step3_group)

    def select_output_dir(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            '选择输出目录',
            self.output_dir
        )
        if dir_path:
            self.output_dir = dir_path
            # 显示简短路径
            short_path = dir_path if len(dir_path) <= 20 else '...' + dir_path[-17:]
            self.output_dir_label.setText(short_path)
            self.output_dir_label.setToolTip(dir_path)
            self.log(f'📁 输出目录已设置为: {dir_path}')

    def cancel_current_task(self):
        """取消当前正在运行的任务"""
        reply = QMessageBox.question(
            self,
            '确认取消',
            '确定要取消当前任务吗？\n未完成的文件将被删除。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.log('⏹️ 正在取消任务...')

        # 取消转写任务
        if self.current_worker:
            self.current_worker.request_cancel()

        # 取消合成任务
        if self.current_burn_worker:
            self.current_burn_worker.request_cancel()

    def select_video(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            '选择视频文件（可多选）',
            '',
            '视频文件 (*.mp4 *.mov *.avi *.mkv *.webm);;所有文件 (*)'
        )

        if not paths:
            return

        # 检查数量限制
        remaining_slots = MAX_QUEUE_SIZE - len(self.video_files)
        if remaining_slots <= 0:
            self.log(f'⚠️ 队列已满（最多{MAX_QUEUE_SIZE}个），请先清空列表')
            QMessageBox.warning(self, '提示', f'队列最多 {MAX_QUEUE_SIZE} 个文件，请先清空列表再添加新文件')
            return

        # 只添加还能添加的文件
        paths_to_add = paths[:remaining_slots]
        if len(paths) > remaining_slots:
            self.log(f'⚠️ 只添加前 {remaining_slots} 个文件（队列最大{MAX_QUEUE_SIZE}个）')

        for path in paths_to_add:
            if path in self.video_files:
                continue  # 跳过已存在的文件

            try:
                info = self.get_video_info(path)
                self.video_files.append(path)

                # 添加到列表显示
                filename = os.path.basename(path)
                duration = self.format_duration(info['duration'])
                size = self.format_size(info['size'])
                item_text = f'📄 {filename}  [{duration}] [{size}]'
                self.video_list_widget.addItem(item_text)

            except Exception as e:
                self.log(f'获取视频信息失败: {e}')

        # 更新文件计数
        self.file_count_label.setText(f'已选择 {len(self.video_files)} 个文件')

        # 启用处理按钮
        self.process_btn.setEnabled(len(self.video_files) > 0)

        self.log(f'已添加 {len(paths_to_add)} 个视频文件，当前队列: {len(self.video_files)}/{MAX_QUEUE_SIZE}')

    def clear_video_list(self):
        """清空视频列表"""
        # 检查是否有正在运行的任务
        running = [p for p, data in self.active_workers.items() if data.get('running')]
        if running:
            self.log('⚠️ 有任务正在运行，无法清空列表')
            QMessageBox.warning(self, '提示', '有任务正在运行，请等待完成后再清空')
            return

        self.video_files = []
        self.video_list_widget.clear()
        self.file_count_label.setText('已选择 0 个文件')
        self.process_btn.setEnabled(False)
        self.log('已清空视频列表')

    def get_video_info(self, path):
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        info = json.loads(result.stdout)

        video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
        format_info = info['format']

        return {
            'width': video_stream['width'],
            'height': video_stream['height'],
            'duration': float(format_info['duration']),
            'size': int(format_info['size'])
        }

    def format_duration(self, seconds):
        m, s = divmod(int(seconds), 60)
        if seconds >= 3600:
            h, m = divmod(m, 60)
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def process_video(self):
        if not self.video_files:
            return

        self.log(f'🚀 开始处理队列（{len(self.video_files)} 个视频，最大队列 {MAX_QUEUE_SIZE}）...')
        self.process_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

        # 禁用设置控件
        self.lang_combo.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.translate_combo.setEnabled(False)

        # 获取当前设置
        lang_map = {0: None, 1: 'japanese', 2: 'english', 3: 'chinese'}
        language = lang_map[self.lang_combo.currentIndex()]
        device_map = {0: 'cuda', 1: 'cpu'}
        device = device_map[self.device_combo.currentIndex()]
        translate = (self.translate_combo.currentIndex() == 1)

        # 初始化任务状态
        self.active_workers = {}
        for path in self.video_files:
            self.active_workers[path] = {
                'completed': False,
                'segments': [],
            }

        # 只启动第一个任务，其余加入队列
        self._start_worker(self.video_files[0], language, device, translate)

        # 如果有更多任务，加入队列
        remaining = self.video_files[1:]
        for path in remaining:
            self.task_queue.put(path)

    def _start_worker(self, path, language, device, translate):
        """启动单个任务的 Worker"""
        self.log(f'▶️ 开始处理: {os.path.basename(path)}')

        # 保存当前任务引用，防止 GC
        self.current_video_path = path
        self.current_worker = Worker(path, language, device, translate, self.output_dir)
        self.current_worker.progress.connect(lambda data, p=path: self._on_task_progress(p, data))
        self.current_worker.finished.connect(lambda data, p=path: self._on_task_finished(p, data))
        self.current_worker.error.connect(lambda msg, p=path: self._on_task_error(p, msg))
        self.current_worker.cancelled.connect(self._on_task_cancelled)

        self.current_thread = threading.Thread(target=self.current_worker.run)
        self.current_thread.start()

        # 显示进度条和当前文件
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.current_file_label.setVisible(True)
        self.current_file_label.setText(f'📄 {os.path.basename(path)}')
        self.current_file_label.setStyleSheet('color: #3498db;')

        # 显示取消按钮
        self.cancel_btn.setVisible(True)

    def _on_task_progress(self, path, data):
        """单个任务进度更新"""
        status = data.get('status', '')
        percent = data.get('percent', 0)
        message = data.get('message', '')

        if status == 'transcribing':
            self.progress_bar.setRange(0, 0)  # 不确定进度，显示忙碌状态
        else:
            if self.progress_bar.minimum() == 0 and self.progress_bar.maximum() == 0:
                self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)

        self.current_file_label.setText(f'📄 {os.path.basename(path)} - {message}')

    def _on_task_finished(self, path, result):
        """单个任务完成"""
        try:
            self.log(f'✅ 完成: {os.path.basename(path)} - {len(result["segments"])} 条字幕')

            self.active_workers[path]['completed'] = True
            self.active_workers[path]['segments'] = result['segments']
            self.completed_results[path] = result

            # 清除当前任务引用
            self.current_worker = None
            self.current_thread = None
            self.current_video_path = None

            # 自动保存字幕文件到输出目录
            self.progress_bar.setValue(75)
            self.current_file_label.setText(f'📄 {os.path.basename(path)} - 保存字幕...')
            self._auto_save_srt(path)

            # 自动合成带字幕视频
            self.current_file_label.setText(f'📄 {os.path.basename(path)} - 合成视频...')
            self._auto_burn_subtitles(path, result['segments'])
        except Exception as e:
            import traceback
            print(f"[ERROR] _on_task_finished 出错: {e}")
            traceback.print_exc()
            self.log(f'❌ 处理出错: {e}')

    def _on_auto_burn_finished(self, output_path):
        """自动合成完成"""
        try:
            self.progress_bar.setValue(100)
            burn_path = getattr(self, '_current_burn_path', None) or output_path
            self.current_file_label.setText(f'✅ {os.path.basename(burn_path)} - 已完成')
            self.current_file_label.setStyleSheet('color: #27ae60; font-weight: bold;')

            # 安全清理线程和worker
            self._cleanup_burn_worker()

            # 隐藏取消按钮
            self.cancel_btn.setVisible(False)

            # 检查是否所有任务都完成
            self._check_all_tasks_completed()

            # 从队列启动下一个任务
            self._start_next_in_queue()
        except Exception as e:
            import traceback
            print(f"[ERROR] _on_auto_burn_finished 出错: {e}")
            traceback.print_exc()
            self.log(f'❌ 视频合成后处理出错: {e}')

    def _cleanup_burn_worker(self):
        """安全清理burn worker和线程"""
        if self.current_burn_thread is not None:
            # 等待线程结束
            self.current_burn_thread.quit()
            self.current_burn_thread.wait(1000)  # 最多等待1秒
            self.current_burn_thread = None
        self.current_burn_worker = None
        if hasattr(self, '_current_burn_path'):
            self._current_burn_path = None

    def _on_auto_burn_error(self, error_msg):
        """自动合成出错"""
        try:
            self.progress_bar.setValue(100)
            burn_path = getattr(self, '_current_burn_path', None) or '未知文件'
            self.current_file_label.setText(f'⚠️ {os.path.basename(burn_path)} - 合成失败')
            self.current_file_label.setStyleSheet('color: #e74c3c; font-weight: bold;')

            # 安全清理线程和worker
            self._cleanup_burn_worker()

            # 隐藏取消按钮
            self.cancel_btn.setVisible(False)

            # 检查是否所有任务都完成
            self._check_all_tasks_completed()

            # 从队列启动下一个任务
            self._start_next_in_queue()
        except Exception as e:
            import traceback
            print(f"[ERROR] _on_auto_burn_error 出错: {e}")
            traceback.print_exc()
            self.log(f'❌ 错误处理出错: {e}')

    def _auto_save_srt(self, video_path):
        """自动保存 SRT 字幕文件到输出目录"""
        result = self.completed_results.get(video_path)
        if not result or not result.get('segments'):
            return

        filename = os.path.splitext(os.path.basename(video_path))[0]
        save_path = os.path.join(self.output_dir, f'{filename}_subtitle.srt')

        segments = result['segments']
        lines = []
        for i, seg in enumerate(segments, 1):
            start = self.format_srt_time(seg['start'])
            end = self.format_srt_time(seg['end'])
            text = seg.get('translated') or seg.get('text', '')
            lines.extend([str(i), f"{start} --> {end}", text, ''])

        content = '\n'.join(lines)
        try:
            with open(save_path, 'w', encoding='utf-8-sig') as f:
                f.write(content)
            self.log(f'📄 自动保存字幕: {save_path}')
        except Exception as e:
            self.log(f'⚠️ 自动保存字幕失败: {e}')

    def _auto_burn_subtitles(self, video_path, segments):
        """自动合成带字幕视频"""
        filename = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(self.output_dir, f'{filename}_subtitled.mp4')

        # 生成 ASS 字幕内容
        ass_content = self._generate_ass_content(segments)

        self.log(f'🎬 开始自动合成: {os.path.basename(video_path)}')
        self._current_burn_path = video_path  # 保存当前合成路径

        # 使用 BurnWorker 进行异步合成，支持进度报告
        self.current_burn_worker = BurnWorker(video_path, ass_content, output_path)
        self.current_burn_worker.progress.connect(self._on_auto_burn_progress)
        self.current_burn_worker.finished.connect(self._on_auto_burn_finished)
        self.current_burn_worker.error.connect(self._on_auto_burn_error)
        self.current_burn_worker.cancelled.connect(self._on_auto_burn_cancelled)

        from PyQt5.QtCore import QThread
        self.current_burn_thread = QThread()
        self.current_burn_worker.moveToThread(self.current_burn_thread)
        self.current_burn_thread.started.connect(self.current_burn_worker.run)
        # 连接线程完成信号，用于正确清理
        self.current_burn_thread.finished.connect(self._on_burn_thread_finished)
        self.current_burn_thread.start()

    def _on_burn_thread_finished(self):
        """线程真正结束时调用，确保线程正确清理"""
        # 不需要做任何事，只是确保线程被正确等待
        pass

    def _on_auto_burn_progress(self, data):
        """自动合成进度更新"""
        # 将 BurnWorker 的进度 (0-100) 映射到我们的进度 (80-100)
        burn_percent = data.get('percent', 0)
        my_percent = 80 + int(burn_percent * 0.2)  # 80-100
        self.progress_bar.setValue(my_percent)
        self.log(data.get('message', '合成中...'))

    def _on_auto_burn_cancelled(self):
        """自动合成被取消"""
        try:
            self.progress_bar.setValue(100)
            self.current_file_label.setText(f'⏹️ 合成已取消')
            self.current_file_label.setStyleSheet('color: #e67e22; font-weight: bold;')

            # 安全清理线程和worker
            self._cleanup_burn_worker()

            # 隐藏取消按钮
            self.cancel_btn.setVisible(False)

            # 检查是否所有任务都完成
            self._check_all_tasks_completed()

            # 从队列启动下一个任务
            self._start_next_in_queue()
        except Exception as e:
            import traceback
            print(f"[ERROR] _on_auto_burn_cancelled 出错: {e}")
            traceback.print_exc()
            self.log(f'❌ 取消处理出错: {e}')

    def _generate_ass_content(self, segments):
        """生成 ASS 字幕内容"""
        lines = [
            '[Script Info]',
            'Title: Smart Subtitle Tool',
            'ScriptType: v4.00+',
            '',
            '[V4+ Styles]',
            'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
            'Style: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,134',
            '',
            '[Events]',
            'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text'
        ]

        for seg in segments:
            start = self._format_ass_time(seg['start'])
            end = self._format_ass_time(seg['end'])
            text = (seg.get('translated') or seg.get('text', '')).replace('\n', '\\N').replace('\r', '')
            lines.append(f'Dialogue: 0,{start},{end},Default,,0,0,0,,{text}')

        return '\n'.join(lines)

    def _format_ass_time(self, seconds):
        """格式化 ASS 时间码"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds - int(seconds)) * 100)
        return f'{h}:{m:02d}:{s:02d}.{cs:02d}'

    def _on_task_error(self, path, error_msg):
        """单个任务出错"""
        self.log(f'❌ 任务失败: {os.path.basename(path)} - {error_msg}')

        self.active_workers[path]['completed'] = True

        self.current_file_label.setText(f'❌ {os.path.basename(path)} - 失败')
        self.current_file_label.setStyleSheet('color: #e74c3c; font-weight: bold;')

        # 清除当前任务引用
        self.current_worker = None
        self.current_thread = None
        self.current_video_path = None

        # 隐藏取消按钮
        self.cancel_btn.setVisible(False)

        # 检查是否所有任务都完成
        self._check_all_tasks_completed()

        # 从队列启动下一个任务
        self._start_next_in_queue()

    def _on_task_cancelled(self):
        """任务被取消"""
        self.log('⚠️ 任务已取消')

        # 标记当前任务为完成
        if self.current_video_path and self.current_video_path in self.active_workers:
            self.active_workers[self.current_video_path]['completed'] = True

        # 清除当前任务引用
        self.current_worker = None
        self.current_thread = None

        # 隐藏取消按钮
        self.cancel_btn.setVisible(False)

        self.progress_bar.setVisible(False)
        self.current_file_label.setText('⏹️ 任务已取消')
        self.current_file_label.setStyleSheet('color: #e67e22; font-weight: bold;')

        # 清空队列
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break

        # 检查是否所有任务都完成（此时可能没有全部完成，但队列已清空）
        self._check_all_tasks_completed()

        # 重新启用控件
        self.process_btn.setEnabled(len(self.video_files) > 0)
        self.clear_btn.setEnabled(True)
        self.lang_combo.setEnabled(True)
        self.device_combo.setEnabled(True)
        self.translate_combo.setEnabled(True)

    def _start_next_in_queue(self):
        """从队列启动下一个任务"""
        try:
            next_path = self.task_queue.get_nowait()
            lang_map = {0: None, 1: 'japanese', 2: 'english', 3: 'chinese'}
            language = lang_map[self.lang_combo.currentIndex()]
            device_map = {0: 'cuda', 1: 'cpu'}
            device = device_map[self.device_combo.currentIndex()]
            translate = (self.translate_combo.currentIndex() == 1)
            self._start_worker(next_path, language, device, translate)
        except queue.Empty:
            pass  # 队列为空，不做操作

    def _check_all_tasks_completed(self):
        """检查是否所有任务都完成了"""
        all_done = all(
            data.get('completed', False) for data in self.active_workers.values()
        )

        if all_done:
            self.log('🎉 所有任务处理完成！')

            # 启用控件
            self.process_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            self.lang_combo.setEnabled(True)
            self.device_combo.setEnabled(True)
            self.translate_combo.setEnabled(True)

            # 汇总结果
            self._summarize_results()

    def _summarize_results(self):
        """汇总所有任务结果"""
        self.progress_bar.setVisible(False)
        self.current_file_label.setVisible(False)
        self.subtitle_list.clear()

        # 汇总信息
        total_files = len(self.completed_results)
        total_segments = sum(len(r['segments']) for r in self.completed_results.values())

        success_count = sum(1 for r in self.completed_results.values() if r['segments'])
        fail_count = total_files - success_count

        self.log(f'📊 处理汇总: {success_count} 个成功, {fail_count} 个失败, 共 {total_segments} 条字幕')

        # 显示结果列表
        for path, result in self.completed_results.items():
            filename = os.path.basename(path)
            seg_count = len(result['segments'])
            self.subtitle_list.addItem(f'📄 {filename}: {seg_count} 条字幕')

        # 保存当前选中的文件路径用于导出
        if self.completed_results:
            self.video_path = list(self.completed_results.keys())[0]
            self.segments = self.completed_results[self.video_path]['segments']

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{m:02d}:{s:02d},{ms:03d}"

    def format_ass_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds - int(seconds)) * 100)
        return f'{h}:{m:02d}:{s:02d}.{cs:02d}'

    def generate_srt(self):
        lines = []
        for i, seg in enumerate(self.segments, 1):
            start = self.format_srt_time(seg['start'])
            end = self.format_srt_time(seg['end'])
            text = seg['translated'] or seg['text']
            lines.extend([str(i), f"{start} --> {end}", text, ''])
        return '\n'.join(lines)

    def format_srt_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f'[{timestamp}] {message}')


def main():
    print("检查依赖...")
    check_dependencies()

    app = QApplication(sys.argv)
    app.setFont(QFont('Microsoft YaHei', 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

