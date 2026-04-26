#!/usr/bin/env python3
"""
智能字幕工坊 - 桌面应用
使用 PyQt5 + Whisper + FFmpeg
"""

import sys
import os
import json
import tempfile
import subprocess
import threading
from datetime import datetime

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

class Worker(QObject):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, video_path, language, device='cuda', parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.language = language
        self.device = device

    def run(self):
        try:
            import whisper

            self.progress.emit({'status': 'loading', 'message': '加载 Whisper 模型...', 'percent': 10})

            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'whisper', 'medium.pt'
            )

            if os.path.exists(model_path):
                self.progress.emit({'status': 'loading', 'message': f'使用本地模型 ({self.device})', 'percent': 15})
                model = whisper.load_model(model_path, device=self.device)
            else:
                self.progress.emit({'status': 'loading', 'message': f'使用 medium ({self.device})', 'percent': 15})
                model = whisper.load_model("medium", device=self.device)

            self.progress.emit({'status': 'transcribing', 'message': '开始语音识别...', 'percent': 30})

            result = model.transcribe(
                self.video_path,
                language=self.language,
                task='transcribe'
            )

            self.progress.emit({'status': 'processing', 'message': '处理结果...', 'percent': 90})

            segments = []
            for seg in result.get('segments', []):
                segments.append({
                    'id': len(segments) + 1,
                    'start': round(seg['start'], 2),
                    'end': round(seg['end'], 2),
                    'text': seg['text'].strip(),
                    'translated': ''
                })

            self.progress.emit({'status': 'complete', 'message': '识别完成!', 'percent': 100})

            self.finished.emit({
                'segments': segments,
                'text': result.get('text', ''),
                'language': result.get('language', self.language)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


class BurnWorker(QObject):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, video_path, subtitle_content, output_path, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.subtitle_content = subtitle_content
        self.output_path = output_path

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

            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                cwd=temp_dir
            )

            stderr_output = []
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                stderr_output.append(line)
                if 'time=' in line:
                    self.progress.emit({'percent': 50, 'message': '合成中...'})

            stderr_text = ''.join(stderr_output)

            try:
                os.unlink(temp_sub)
            except:
                pass

            if process.returncode == 0:
                self.progress.emit({'percent': 100, 'message': '合成完成!'})
                self.finished.emit(self.output_path)
            else:
                self.error.emit(f'FFmpeg 失败 (返回码: {process.returncode})\n命令:\n{" ".join(cmd)}\n错误:\n{stderr_text[-1000:]}')

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
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('智能字幕工坊')
        self.setGeometry(100, 100, 900, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        title = QLabel('🎬 智能字幕工坊')
        title.setFont(QFont('Microsoft YaHei', 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Step 1: Video Selection
        step1_group = QGroupBox('步骤1: 选择视频')
        step1_layout = QVBoxLayout()

        video_layout = QHBoxLayout()
        self.video_path_label = QLabel('未选择视频')
        video_btn = QPushButton('选择视频文件')
        video_btn.clicked.connect(self.select_video)
        video_layout.addWidget(self.video_path_label, 1)
        video_layout.addWidget(video_btn)
        step1_layout.addLayout(video_layout)

        self.video_info_label = QLabel('')
        step1_layout.addWidget(self.video_info_label)
        step1_group.setLayout(step1_layout)
        layout.addWidget(step1_group)

        # Step 2: Settings
        step2_group = QGroupBox('步骤2: 设置')
        step2_layout = QHBoxLayout()

        step2_layout.addWidget(QLabel('Source Language:'))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(['Japanese', 'English', 'Chinese'])
        self.lang_combo.setCurrentIndex(0)
        step2_layout.addWidget(self.lang_combo)

        step2_layout.addWidget(QLabel('Acceleration:'))
        self.device_combo = QComboBox()
        self.device_combo.addItems(['GPU (CUDA)', 'CPU'])
        self.device_combo.setCurrentIndex(0)
        step2_layout.addWidget(self.device_combo)

        self.process_btn = QPushButton('🎯 开始处理')
        self.process_btn.clicked.connect(self.process_video)
        self.process_btn.setEnabled(False)
        step2_layout.addWidget(self.process_btn)

        step2_group.setLayout(step2_layout)
        layout.addWidget(step2_group)

        # Step 3: Results
        step3_group = QGroupBox('步骤3: 结果')
        step3_layout = QVBoxLayout()

        self.subtitle_list = QListWidget()
        step3_layout.addWidget(self.subtitle_list)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        step3_layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        step3_layout.addWidget(QLabel('日志:'))
        step3_layout.addWidget(self.log_text)

        export_layout = QHBoxLayout()
        self.export_srt_btn = QPushButton('📥 下载 SRT 字幕')
        self.export_srt_btn.clicked.connect(self.export_srt)
        self.export_srt_btn.setEnabled(False)

        self.export_video_btn = QPushButton('🎬 合成带字幕视频')
        self.export_video_btn.clicked.connect(self.burn_subtitles)
        self.export_video_btn.setEnabled(False)

        export_layout.addWidget(self.export_srt_btn)
        export_layout.addWidget(self.export_video_btn)
        step3_layout.addLayout(export_layout)

        step3_group.setLayout(step3_layout)
        layout.addWidget(step3_group)

    def select_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            '选择视频文件',
            '',
            '视频文件 (*.mp4 *.mov *.avi *.mkv *.webm);;所有文件 (*)'
        )

        if path:
            self.video_path = path
            self.video_path_label.setText(os.path.basename(path))
            self.log(f'已选择视频: {path}')

            try:
                info = self.get_video_info(path)
                self.video_info = info
                self.video_info_label.setText(
                    f'分辨率: {info["width"]}×{info["height"]} | '
                    f'时长: {self.format_duration(info["duration"])} | '
                    f'大小: {self.format_size(info["size"])}'
                )
                self.process_btn.setEnabled(True)
            except Exception as e:
                self.log(f'获取视频信息失败: {e}')

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
        if not self.video_path:
            return

        self.log('开始语音识别...')
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.process_btn.setEnabled(False)

        lang_map = {0: 'japanese', 1: 'english', 2: 'chinese'}
        language = lang_map[self.lang_combo.currentIndex()]
        device_map = {0: 'cuda', 1: 'cpu'}
        device = device_map[self.device_combo.currentIndex()]

        self.worker = Worker(self.video_path, language, device)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)

        self.thread = threading.Thread(target=self.worker.run)
        self.thread.start()

    def on_progress(self, data):
        self.progress_bar.setValue(data['percent'])
        self.log(data['message'])

    def on_finished(self, result):
        self.segments = result['segments']
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)

        self.log(f'识别完成! 共 {len(self.segments)} 条字幕')

        self.subtitle_list.clear()
        for seg in self.segments:
            item_text = f"[{self.format_time(seg['start'])} --> {self.format_time(seg['end'])}] {seg['text']}"
            self.subtitle_list.addItem(item_text)

        self.export_srt_btn.setEnabled(True)
        self.export_video_btn.setEnabled(True)

    def on_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        self.log(f'错误: {error_msg}')
        QMessageBox.critical(self, '错误', f'处理失败: {error_msg}')

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{m:02d}:{s:02d},{ms:03d}"

    def export_srt(self):
        if not self.segments:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            '保存 SRT 字幕',
            f'{os.path.splitext(os.path.basename(self.video_path))[0]}_subtitle.srt',
            'SRT 字幕 (*.srt)'
        )

        if path:
            content = self.generate_srt()
            with open(path, 'w', encoding='utf-8-sig') as f:
                f.write(content)
            self.log(f'SRT 字幕已保存: {path}')

    def generate_ass(self):
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

        for seg in self.segments:
            start = self.format_ass_time(seg['start'])
            end = self.format_ass_time(seg['end'])
            text = (seg['translated'] or seg['text']).replace('\n', '\\N').replace('\r', '')
            lines.append(f'Dialogue: 0,{start},{end},Default,,0,0,0,,{text}')

        return '\n'.join(lines)

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

    def burn_subtitles(self):
        if not self.segments:
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            '保存带字幕视频',
            f'{os.path.splitext(os.path.basename(self.video_path))[0]}_subtitled.mp4',
            'MP4 视频 (*.mp4)'
        )

        if not output_path:
            return

        self.log('开始合成视频...')
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.export_video_btn.setEnabled(False)

        subtitle_content = self.generate_ass()
        self.burn_worker = BurnWorker(self.video_path, subtitle_content, output_path)
        self.burn_worker.progress.connect(self.on_burn_progress)
        self.burn_worker.finished.connect(self.on_burn_finished)
        self.burn_worker.error.connect(self.on_burn_error)

        from PyQt5.QtCore import QThread
        self.burn_thread = QThread()
        self.burn_worker.moveToThread(self.burn_thread)
        self.burn_thread.started.connect(self.burn_worker.run)
        self.burn_thread.start()

    def on_burn_progress(self, data):
        self.progress_bar.setValue(data['percent'])
        self.log(data['message'])

    def on_burn_finished(self, output_path):
        self.progress_bar.setVisible(False)
        self.export_video_btn.setEnabled(True)
        self.log(f'视频已保存: {output_path}')
        QMessageBox.information(self, '成功', f'带字幕视频已保存到:\n{output_path}')

    def on_burn_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.export_video_btn.setEnabled(True)
        self.log(f'合成失败: {error_msg}')
        QMessageBox.critical(self, '错误', f'视频合成失败:\n{error_msg}')

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
