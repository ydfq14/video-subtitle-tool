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

# 最大队列长度
MAX_QUEUE_SIZE = 10

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')

def load_settings():
    """从配置文件加载设置"""
    default_settings = {
        'secret_id': '',
        'secret_key': '',
        'output_dir': '',
        'model_path': '',
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                default_settings.update(saved)
        except Exception as e:
            print(f"[设置] 加载配置失败: {e}")
    return default_settings

def save_settings(settings):
    """保存设置到配置文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[设置] 保存配置失败: {e}")

# 全局设置
_app_settings = load_settings()

# -*- coding: utf-8 -*-
import io

# 修复 Windows 控制台编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# 尝试导入 PyQt5（仅导入，不自动安装）
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QFileDialog, QProgressBar, QTextEdit,
        QComboBox, QMessageBox, QGroupBox, QListWidget,
        QLineEdit, QDialog, QFormLayout, QDialogButtonBox
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QObject, QSize
    from PyQt5.QtGui import QFont, QIcon, QPixmap
    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False

def check_dependencies():
    """检查并自动安装缺失的环境依赖，返回 True 表示全部就绪"""
    results = []  # [(名称, 状态, 详情)]
    all_ok = True

    # 1. 检查 Python 包依赖
    required_packages = [
        ('PyQt5', 'PyQt5>=5.15.0'),
        ('whisper', 'openai-whisper'),
        ('numpy', 'numpy'),
    ]

    for module_name, pip_name in required_packages:
        try:
            __import__(module_name)
            results.append((module_name, 'ok', '已安装'))
        except ImportError:
            results.append((module_name, 'installing', f'正在安装 {pip_name}...'))
            all_ok = False

    # 2. 检查 FFmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        results.append(('FFmpeg', 'ok', '已安装'))
    except Exception:
        results.append(('FFmpeg', 'warning', '未安装，字幕合成功能将不可用'))

    # 如果全部 OK，不需要展示检测界面
    if all_ok:
        for name, status, detail in results:
            print(f"[环境] {name}: {detail}")
        return True

    # 有缺失依赖，展示 GUI 安装界面
    return _show_env_check_ui(results, required_packages)


def _show_env_check_ui(results, required_packages):
    """展示环境检测 GUI 并自动安装缺失依赖"""
    if not PYQT5_AVAILABLE:
        # PyQt5 缺失，先用命令行安装
        print("[环境] PyQt5 未安装，正在自动安装...")
        _pip_install('PyQt5>=5.15.0')
        print("[环境] PyQt5 安装完成，请重新运行程序。")
        try:
            input("按回车键退出...")
        except:
            pass
        return False

    # 创建临时 QApplication（可能还没有）
    app = None
    if QApplication.instance() is None:
        app = QApplication(sys.argv)

    # 构建检测界面
    dialog = QDialog()
    dialog.setWindowTitle('智能字幕工坊 - 环境检测')
    dialog.setMinimumWidth(480)
    dialog.setMinimumHeight(360)
    dialog.setModal(True)
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowCloseButtonHint)

    dialog.setStyleSheet("""
        QDialog {
            background-color: #f0f2f5;
        }
        QLabel#title {
            font-size: 20px;
            font-weight: bold;
            color: #2c3e50;
        }
        QLabel#subtitle {
            font-size: 12px;
            color: #95a5a6;
        }
        QFrame#card {
            background-color: white;
            border-radius: 10px;
            border: none;
        }
        QLabel#item_name {
            font-size: 13px;
            font-weight: bold;
            color: #2c3e50;
        }
        QLabel#item_status {
            font-size: 12px;
        }
        QPushButton#close_btn {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 40px;
            font-size: 14px;
            font-weight: bold;
        }
        QPushButton#close_btn:hover {
            background-color: #2e86c1;
        }
    """)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(14)

    # 标题
    title = QLabel('🔍 环境检测')
    title.setObjectName('title')
    layout.addWidget(title)

    subtitle = QLabel('正在检查运行环境，自动安装缺失的依赖...')
    subtitle.setObjectName('subtitle')
    layout.addWidget(subtitle)

    layout.addSpacing(6)

    # 状态卡片
    card = QFrame()
    card.setObjectName('card')
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(20, 16, 20, 16)
    card_layout.setSpacing(10)

    status_labels = {}
    for name, status, detail in results:
        row = QHBoxLayout()
        name_label = QLabel(f'  {name}')
        name_label.setObjectName('item_name')
        name_label.setMinimumWidth(100)
        row.addWidget(name_label)

        status_label = QLabel(detail)
        status_label.setObjectName('item_status')
        if status == 'ok':
            status_label.setStyleSheet('color: #27ae60; font-weight: bold;')
            status_label.setText('✅ 已安装')
        elif status == 'installing':
            status_label.setStyleSheet('color: #f39c12; font-weight: bold;')
            status_label.setText('⏳ 准备安装...')
        elif status == 'warning':
            status_label.setStyleSheet('color: #e74c3c; font-weight: bold;')
            status_label.setText('⚠️ ' + detail)
        row.addWidget(status_label)
        row.addStretch()
        card_layout.addLayout(row)
        status_labels[name] = status_label

    layout.addWidget(card)

    # 进度条
    progress = QProgressBar()
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.setTextVisible(False)
    progress.setFixedHeight(4)
    progress.setStyleSheet("""
        QProgressBar {
            background-color: #e0e0e0;
            border-radius: 2px;
            border: none;
        }
        QProgressBar::chunk {
            background-color: #3498db;
            border-radius: 2px;
        }
    """)
    layout.addWidget(progress)

    layout.addSpacing(6)

    # 日志区域
    log_text = QTextEdit()
    log_text.setReadOnly(True)
    log_text.setMaximumHeight(80)
    log_text.setStyleSheet("""
        QTextEdit {
            background-color: #2c3e50;
            color: #ecf0f1;
            border-radius: 8px;
            border: none;
            font-family: Consolas, 'Microsoft YaHei';
            font-size: 11px;
            padding: 8px;
        }
    """)
    layout.addWidget(log_text)

    # 关闭按钮（默认隐藏）
    close_btn = QPushButton('启动程序')
    close_btn.setObjectName('close_btn')
    close_btn.setCursor(Qt.PointingHandCursor)
    close_btn.setVisible(False)
    close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_btn, alignment=Qt.AlignCenter)

    dialog.show()

    # 执行安装
    def do_install():
        total = len(results)
        done = 0

        for name, status, detail in results:
            if status != 'installing':
                done += 1
                progress.setValue(int(done / total * 100))
                continue

            # 找到对应的 pip 包名
            pip_name = ''
            for module_name, pname in required_packages:
                if module_name == name:
                    pip_name = pname
                    break

            status_labels[name].setText('⏳ 正在安装...')
            log_text.append(f'[安装] {pip_name} ...')
            QApplication.processEvents()

            success = _pip_install(pip_name)
            if success:
                status_labels[name].setText('✅ 安装成功')
                status_labels[name].setStyleSheet('color: #27ae60; font-weight: bold;')
                log_text.append(f'[完成] {pip_name} 安装成功')
            else:
                status_labels[name].setText('❌ 安装失败')
                status_labels[name].setStyleSheet('color: #e74c3c; font-weight: bold;')
                log_text.append(f'[错误] {pip_name} 安装失败，请手动执行: pip install {pip_name}')

            done += 1
            progress.setValue(int(done / total * 100))
            QApplication.processEvents()

        subtitle.setText('环境检测完成')
        close_btn.setVisible(True)

    # 延迟执行安装（让界面先显示）
    from PyQt5.QtCore import QTimer
    QTimer.singleShot(500, do_install)

    dialog.exec_()

    if app is not None:
        app.quit()

    return True  # 即使有安装失败也继续运行，让主界面提示


def _pip_install(package_name):
    """执行 pip install，返回是否成功"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package_name, '-q'],
            capture_output=True, text=True, timeout=300
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[安装错误] {e}")
        return False

def translate_text_to_chinese(text, from_lang='ja'):
    """使用腾讯云机器翻译 API 将文本翻译为简体中文
    环境变量 SecretId 和 SecretKey 需要提前设置
    """
    if not text or not text.strip():
        return text

    SECRET_ID = _app_settings.get('secret_id', '') or os.environ.get('SecretId', '')
    SECRET_KEY = _app_settings.get('secret_key', '') or os.environ.get('SecretKey', '')

    if not SECRET_ID or not SECRET_KEY:
        print("[翻译] 未配置 SecretId/SecretKey，使用原文")
        return text

    # 腾讯云 TMT API 参数
    service = "tmt"
    host = "tmt.tencentcloudapi.com"
    endpoint = f"https://{host}"
    action = "TextTranslate"
    version = "2018-03-21"
    region = "ap-guangzhou"

    # 源语言和目标语言
    lang_code_map = {
        'japanese': 'ja', 'ja': 'ja',
        'english': 'en', 'en': 'en',
        'chinese': 'zh', 'zh': 'zh'
    }
    from_lang_code = lang_code_map.get(from_lang, 'en')
    target_lang = 'zh'

    # 清理文本：去除前后空白和多余空格
    source_text = text.strip()[:1000]

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
                translated = result["Response"]["TargetText"]
                # 清理翻译结果中的可能残留内容
                import re
                # 去除 [参考上文：...] 或类似括号标记
                translated = re.sub(r'\[参考[^]]*\]', '', translated).strip()
                # 去除多余空格
                translated = re.sub(r'\s{2,}', ' ', translated).strip()
                return translated
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
        try:
            import whisper

            self.progress.emit({'status': 'loading', 'message': '正在加载 Whisper 模型...', 'percent': 5})

            # 确定模型路径：优先使用用户设置的自定义路径
            custom_model_path = _app_settings.get('model_path', '').strip()
            if custom_model_path and os.path.exists(custom_model_path):
                # 用户指定了自定义模型路径且文件存在
                self.progress.emit({'status': 'loading', 'message': f'正在加载自定义模型 ({self.device})...', 'percent': 15})
                model = whisper.load_model(custom_model_path, device=self.device)
            else:
                # 检查项目目录下的默认模型
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
                    translated_text = translate_text_to_chinese(original_text, detected_lang)

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


class SettingsDialog(QDialog):
    """设置对话框 - 现代卡片式设计"""
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('设置')
        self.setMinimumWidth(600)
        self.setMinimumHeight(540)
        self.setModal(True)
        self._init_ui()
        self._load_current_settings()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f2f5;
            }
            /* 头部 */
            QLabel#header_icon {
                font-size: 32px;
            }
            QLabel#header_title {
                font-size: 22px;
                font-weight: bold;
                color: #2c3e50;
            }
            QLabel#header_subtitle {
                font-size: 13px;
                color: #95a5a6;
            }
            /* 卡片 */
            QFrame#card {
                background-color: white;
                border-radius: 12px;
                border: none;
            }
            /* 卡片标题 */
            QLabel#card_title {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
                padding: 0px;
            }
            QLabel#card_desc {
                font-size: 13px;
                color: #95a5a6;
                padding: 0px;
            }
            /* 表单标签 */
            QLabel#field_label {
                font-size: 13px;
                font-weight: bold;
                color: #5d6d7e;
            }
            /* 输入框 */
            QLineEdit {
                border: 1.5px solid #dce1e8;
                border-radius: 8px;
                padding: 9px 12px;
                font-size: 14px;
                background-color: #fafbfc;
                color: #2c3e50;
                selection-background-color: #3498db;
            }
            QLineEdit:focus {
                border-color: #3498db;
                background-color: white;
            }
            QLineEdit::placeholder {
                color: #b0b8c4;
            }
            /* 浏览按钮 */
            QPushButton#browse_btn {
                background-color: #eaf2f8;
                color: #2e86c1;
                border: 1.5px solid #aed6f1;
                border-radius: 8px;
                padding: 7px 14px;
                font-size: 13px;
                font-weight: bold;
                min-width: 70px;
            }
            QPushButton#browse_btn:hover {
                background-color: #d4e6f1;
                border-color: #3498db;
            }
            QPushButton#browse_btn:pressed {
                background-color: #a9cce3;
            }
            /* 底部按钮 */
            QPushButton#save_btn {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 30px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton#save_btn:hover {
                background-color: #2e86c1;
            }
            QPushButton#save_btn:pressed {
                background-color: #2471a3;
            }
            QPushButton#cancel_btn {
                background-color: white;
                color: #7f8c8d;
                border: 1.5px solid #dce1e8;
                border-radius: 8px;
                padding: 10px 30px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton#cancel_btn:hover {
                background-color: #f5f6fa;
                border-color: #bdc3c7;
                color: #2c3e50;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ========== 头部 ==========
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel('⚙️')
        icon_label.setObjectName('header_icon')
        header_layout.addWidget(icon_label)

        header_text = QWidget()
        header_text_layout = QVBoxLayout(header_text)
        header_text_layout.setContentsMargins(10, 0, 0, 0)
        header_text_layout.setSpacing(2)

        title_label = QLabel('应用设置')
        title_label.setObjectName('header_title')
        header_text_layout.addWidget(title_label)

        sub_label = QLabel('配置翻译 API、输出路径和模型选项')
        sub_label.setObjectName('header_subtitle')
        header_text_layout.addWidget(sub_label)

        header_layout.addWidget(header_text, 1)
        main_layout.addWidget(header)

        # ========== 卡片 1: 翻译 API ==========
        api_card = self._create_card()

        card1_header = QHBoxLayout()
        card1_title = QLabel('🔑  翻译 API 配置')
        card1_title.setObjectName('card_title')
        card1_header.addWidget(card1_title)
        card1_header.addStretch()

        self.credential_status = QLabel('●  未配置')
        self.credential_status.setObjectName('credential_status')
        self.credential_status.setStyleSheet('font-size: 12px; color: #e74c3c; font-weight: bold;')
        card1_header.addWidget(self.credential_status)

        card1_desc = QLabel('腾讯云机器翻译服务，用于将日/英语字幕翻译为简体中文')
        card1_desc.setObjectName('card_desc')
        card1_desc.setWordWrap(True)

        api_card_layout = QVBoxLayout()
        api_card_layout.setContentsMargins(20, 16, 20, 20)
        api_card_layout.setSpacing(10)
        api_card_layout.addLayout(card1_header)
        api_card_layout.addWidget(card1_desc)

        # SecretId
        sid_label = QLabel('Secret ID')
        sid_label.setObjectName('field_label')
        api_card_layout.addWidget(sid_label)
        self.secret_id_edit = QLineEdit()
        self.secret_id_edit.setPlaceholderText('请输入腾讯云 SecretId')
        self.secret_id_edit.setEchoMode(QLineEdit.Password)
        self.secret_id_edit.textChanged.connect(self._update_credential_status)
        api_card_layout.addWidget(self.secret_id_edit)

        # SecretKey
        skey_label = QLabel('Secret Key')
        skey_label.setObjectName('field_label')
        api_card_layout.addWidget(skey_label)
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setPlaceholderText('请输入腾讯云 SecretKey')
        self.secret_key_edit.setEchoMode(QLineEdit.Password)
        self.secret_key_edit.textChanged.connect(self._update_credential_status)
        api_card_layout.addWidget(self.secret_key_edit)

        api_card.setLayout(api_card_layout)
        main_layout.addWidget(api_card)

        # ========== 卡片 2: 输出目录 ==========
        output_card = self._create_card()

        output_card_layout = QVBoxLayout()
        output_card_layout.setContentsMargins(20, 16, 20, 20)
        output_card_layout.setSpacing(10)

        out_header = QHBoxLayout()
        out_title = QLabel('📂  输出目录')
        out_title.setObjectName('card_title')
        out_header.addWidget(out_title)
        out_header.addStretch()

        out_desc = QLabel('字幕文件和合成视频的保存位置，留空则使用项目目录下的 output 文件夹')
        out_desc.setObjectName('card_desc')
        out_desc.setWordWrap(True)
        out_header.addWidget(out_desc)
        out_header.addStretch()

        output_card_layout.addLayout(out_header)

        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText('默认：项目目录 / output')
        out_row.addWidget(self.output_dir_edit, 1)

        output_browse_btn = QPushButton('浏览...')
        output_browse_btn.setObjectName('browse_btn')
        output_browse_btn.clicked.connect(self._browse_output_dir)
        out_row.addWidget(output_browse_btn)

        output_card_layout.addLayout(out_row)
        output_card.setLayout(output_card_layout)
        main_layout.addWidget(output_card)

        # ========== 卡片 3: 模型路径 ==========
        model_card = self._create_card()

        model_card_layout = QVBoxLayout()
        model_card_layout.setContentsMargins(20, 16, 20, 20)
        model_card_layout.setSpacing(10)

        mdl_header = QHBoxLayout()
        mdl_title = QLabel('🧠  Whisper 模型路径')
        mdl_title.setObjectName('card_title')
        mdl_header.addWidget(mdl_title)
        mdl_header.addStretch()

        mdl_desc = QLabel('留空使用默认位置自动下载；指定路径则从该位置加载 .pt 模型文件')
        mdl_desc.setObjectName('card_desc')
        mdl_desc.setWordWrap(True)
        mdl_header.addWidget(mdl_desc)
        mdl_header.addStretch()

        model_card_layout.addLayout(mdl_header)

        mdl_row = QHBoxLayout()
        mdl_row.setSpacing(8)
        self.model_path_edit = QLineEdit()
        self.model_path_edit.setPlaceholderText('默认：Whisper 自动下载目录')
        mdl_row.addWidget(self.model_path_edit, 1)

        model_browse_btn = QPushButton('浏览...')
        model_browse_btn.setObjectName('browse_btn')
        model_browse_btn.clicked.connect(self._browse_model_path)
        mdl_row.addWidget(model_browse_btn)

        model_card_layout.addLayout(mdl_row)
        model_card.setLayout(model_card_layout)
        main_layout.addWidget(model_card)

        # ========== 底部按钮 ==========
        main_layout.addSpacing(4)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton('取消')
        cancel_btn.setObjectName('cancel_btn')
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton('保存设置')
        save_btn.setObjectName('save_btn')
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

    def _create_card(self):
        """创建白色圆角卡片"""
        from PyQt5.QtWidgets import QFrame
        frame = QFrame()
        frame.setObjectName('card')
        return frame

    def _update_credential_status(self):
        """实时更新凭证状态指示"""
        sid = self.secret_id_edit.text().strip()
        skey = self.secret_key_edit.text().strip()
        has_env_id = bool(os.environ.get('SecretId', ''))
        has_env_key = bool(os.environ.get('SecretKey', ''))

        if (sid and skey):
            self.credential_status.setText('●  已配置')
            self.credential_status.setStyleSheet('font-size: 12px; color: #27ae60; font-weight: bold;')
        elif (not sid and not skey) and (has_env_id and has_env_key):
            self.credential_status.setText('●  使用环境变量')
            self.credential_status.setStyleSheet('font-size: 12px; color: #f39c12; font-weight: bold;')
        elif sid or skey:
            self.credential_status.setText('●  不完整')
            self.credential_status.setStyleSheet('font-size: 12px; color: #e67e22; font-weight: bold;')
        else:
            self.credential_status.setText('●  未配置')
            self.credential_status.setStyleSheet('font-size: 12px; color: #e74c3c; font-weight: bold;')

    def _load_current_settings(self):
        """加载当前设置到界面"""
        settings = load_settings()
        self.secret_id_edit.setText(settings.get('secret_id', ''))
        self.secret_key_edit.setText(settings.get('secret_key', ''))
        self.output_dir_edit.setText(settings.get('output_dir', ''))
        self.model_path_edit.setText(settings.get('model_path', ''))
        self._update_credential_status()

    def _browse_output_dir(self):
        """浏览选择输出目录"""
        current = self.output_dir_edit.text() or ''
        dir_path = QFileDialog.getExistingDirectory(self, '选择输出目录', current)
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def _browse_model_path(self):
        """浏览选择模型文件"""
        current = self.model_path_edit.text() or ''
        start_dir = os.path.dirname(current) if os.path.isfile(current) else current
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择 Whisper 模型文件', start_dir,
            '模型文件 (*.pt);;所有文件 (*)'
        )
        if file_path:
            self.model_path_edit.setText(file_path)

    def _on_save(self):
        """保存设置"""
        global _app_settings
        new_settings = {
            'secret_id': self.secret_id_edit.text().strip(),
            'secret_key': self.secret_key_edit.text().strip(),
            'output_dir': self.output_dir_edit.text().strip(),
            'model_path': self.model_path_edit.text().strip(),
        }
        save_settings(new_settings)
        _app_settings.update(new_settings)
        self.settings_changed.emit(new_settings)
        self.accept()


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
        self.model_custom_path = _app_settings.get('model_path', '').strip()
        custom_output = _app_settings.get('output_dir', '').strip()
        if custom_output and os.path.isdir(custom_output):
            self.output_dir = custom_output
        else:
            self.output_dir = self._get_default_output_dir()

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

        self.init_ui()

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
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 10)

        # 左侧标题
        title_left = QWidget()
        title_left_layout = QVBoxLayout(title_left)
        title_left_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel('智能字幕工坊')
        title.setFont(QFont('Microsoft YaHei', 22, QFont.Bold))
        title.setStyleSheet('color: #2c3e50;')

        subtitle = QLabel('视频语音转字幕 · 支持日/英/中 · 智能翻译')
        subtitle.setFont(QFont('Microsoft YaHei', 10))
        subtitle.setStyleSheet('color: #7f8c8d;')

        title_left_layout.addWidget(title)
        title_left_layout.addWidget(subtitle)
        title_layout.addWidget(title_left, 1)

        # 右侧设置按钮 — SVG 齿轮图标
        self.settings_btn = QPushButton()
        self.settings_btn.setFixedSize(42, 42)
        self.settings_btn.setToolTip('打开设置')
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        # 绘制 SVG 齿轮图标
        gear_svg = (
            '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M12 15a3 3 0 100-6 3 3 0 000 6z" stroke="#5d6d7e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            '<path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" stroke="#5d6d7e" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
            '</svg>'
        )
        pix = QPixmap()
        pix.loadFromData(gear_svg.encode('utf-8'))
        self.settings_btn.setIcon(QIcon(pix))
        self.settings_btn.setIconSize(QSize(24, 24))
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #eef1f5;
                border: 1px solid #dce1e8;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #e3e8f0;
                border-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #d5dce6;
            }
        """)
        self.settings_btn.clicked.connect(self.open_settings)
        title_layout.addWidget(self.settings_btn)

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
        trans_layout.setSpacing(4)
        trans_label = QLabel('翻译功能')
        trans_label.setFont(QFont('Microsoft YaHei', 9, QFont.Bold))
        trans_layout.addWidget(trans_label)
        self.translate_combo = QComboBox()
        self.translate_combo.addItems(['不翻译', '翻译为简体中文'])
        self.translate_combo.setCurrentIndex(0)
        self.translate_combo.setMinimumWidth(150)
        self.translate_combo.currentIndexChanged.connect(self._on_translate_option_changed)
        trans_layout.addWidget(self.translate_combo)

        # 合并字幕到视频选项
        from PyQt5.QtWidgets import QCheckBox
        self.merge_checkbox = QCheckBox('合并字幕到视频')
        self.merge_checkbox.setChecked(True)
        self.merge_checkbox.setToolTip('取消勾选则只输出字幕文件，不合成带字幕的视频')
        self.merge_checkbox.setStyleSheet('font-size: 10px; color: #7f8c8d;')
        trans_layout.addWidget(self.merge_checkbox)

        step2_layout.addWidget(trans_widget)

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

    def _on_translate_option_changed(self, index):
        """翻译选项变更时，检查 SecretId/SecretKey 是否已配置"""
        if index != 1:
            # 不是"翻译为简体中文"，无需检查
            return

        # 检查凭证是否已配置（设置或环境变量）
        has_secret_id = bool(_app_settings.get('secret_id', '').strip()) or bool(os.environ.get('SecretId', ''))
        has_secret_key = bool(_app_settings.get('secret_key', '').strip()) or bool(os.environ.get('SecretKey', ''))

        if has_secret_id and has_secret_key:
            return  # 已配置，放行

        # 未配置，弹出提示
        reply = QMessageBox.warning(
            self,
            '需要配置翻译 API',
            '使用翻译功能需要配置腾讯云翻译 API 的 SecretId 和 SecretKey。\n\n'
            '是否现在前往设置进行配置？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            # 打开设置对话框
            dialog = SettingsDialog(self)
            dialog.settings_changed.connect(self._on_settings_changed)
            result = dialog.exec_()

            if result == QDialog.Accepted:
                # 用户保存了设置，再次检查凭证
                sid = _app_settings.get('secret_id', '').strip() or os.environ.get('SecretId', '')
                skey = _app_settings.get('secret_key', '').strip() or os.environ.get('SecretKey', '')
                if sid and skey:
                    return  # 配置成功，保持"翻译为简体中文"
                # 用户保存了但凭证仍为空
                QMessageBox.information(self, '提示', 'SecretId 和 SecretKey 未填写完整，无法使用翻译功能。')
            # 用户取消了设置对话框，回退到"不翻译"
            self.translate_combo.blockSignals(True)
            self.translate_combo.setCurrentIndex(0)
            self.translate_combo.blockSignals(False)
        else:
            # 用户选择不配置，回退到"不翻译"
            self.translate_combo.blockSignals(True)
            self.translate_combo.setCurrentIndex(0)
            self.translate_combo.blockSignals(False)

    def open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec_()

    def _on_settings_changed(self, settings):
        """设置变更后的回调"""
        # 更新输出目录
        output_dir = settings.get('output_dir', '')
        if output_dir and os.path.isdir(output_dir):
            self.output_dir = output_dir
            self.log(f'📁 输出目录已更新: {output_dir}')
        elif not output_dir:
            # 恢复默认
            self.output_dir = self._get_default_output_dir()
            self.log('📁 输出目录已恢复为默认')

        # 提示其他设置需要重新启动生效
        self.log('✅ 设置已保存（SecretId/SecretKey 和模型路径即时生效）')

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

            # 根据用户设置决定是否合成带字幕视频
            if self.merge_checkbox.isChecked():
                self.current_file_label.setText(f'📄 {os.path.basename(path)} - 合成视频...')
                self._auto_burn_subtitles(path, result['segments'])
            else:
                # 不合成，直接标记完成
                self.progress_bar.setValue(100)
                self.current_file_label.setText(f'✅ {os.path.basename(path)} - 已完成（仅字幕）')
                self.current_file_label.setStyleSheet('color: #27ae60; font-weight: bold;')
                self.cancel_btn.setVisible(False)
                self._check_all_tasks_completed()
                self._start_next_in_queue()
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

    def _wrap_text(self, text, max_chars=30):
        """智能换行文本，仅在内容过长时才断行"""
        if not text:
            return text
        # 清理原文本中的换行符，统一用空格替代
        text = text.replace('\n', ' ').replace('\r', '').strip()
        if len(text) <= max_chars:
            return text

        result_lines = []
        remaining = text

        while len(remaining) > max_chars:
            # 优先在标点处断行
            punctuation = '。！？；，、）】》』」〕'
            best_break = -1
            for pi in range(max_chars - 1, max(0, max_chars - 10) - 1, -1):
                if pi < len(remaining) and remaining[pi] in punctuation:
                    best_break = pi + 1
                    break

            if best_break <= 0:
                # 没有标点，找最后一个空格
                for pi in range(max_chars - 1, max(0, max_chars - 10) - 1, -1):
                    if pi < len(remaining) and remaining[pi] == ' ':
                        best_break = pi + 1
                        break

            if best_break <= 0:
                # 硬切
                best_break = max_chars

            result_lines.append(remaining[:best_break].strip())
            remaining = remaining[best_break:].strip()

        if remaining:
            result_lines.append(remaining)

        # 用 \N 连接多行（ASS 字幕换行符）
        return '\\N'.join(result_lines)

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
            raw_text = seg.get('translated') or seg.get('text', '')
            text = self._wrap_text(raw_text, max_chars=30)
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
    print("智能字幕工坊 - 启动中...")
    print("=" * 40)

    # 环境检测和自动安装
    env_ok = check_dependencies()

    if not PYQT5_AVAILABLE:
        print("[错误] PyQt5 安装失败，程序无法启动。")
        print("[提示] 请手动执行: pip install PyQt5>=5.15.0")
        try:
            input("按回车键退出...")
        except:
            pass
        return

    print("=" * 40)
    print("启动主界面...")

    app = QApplication(sys.argv)
    app.setFont(QFont('Microsoft YaHei', 10))

    window = MainWindow()

    # 如果环境检测有警告（如 FFmpeg 缺失），在日志中提示
    if not env_ok:
        window.log('⚠️ 部分环境依赖未就绪，请检查设置或查看启动日志')

    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

