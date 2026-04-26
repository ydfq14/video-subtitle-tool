#!/usr/bin/env python3
"""
智能字幕工坊 - Whisper 语音识别服务
使用方法: python whisper_service.py <视频文件路径> <语言代码> [--json]
"""

import sys
import os
import json
import tempfile
import warnings

# 忽略警告
warnings.filterwarnings('ignore')

def log_progress(message, progress=None):
    """发送进度到父进程"""
    if progress is not None:
        print(f"PROGRESS:{{\"status\": \"processing\", \"progress\": {progress}, \"message\": \"{message}\"}}", flush=True)
    else:
        print(f"PROGRESS:{{\"status\": \"info\", \"message\": \"{message}\"}}", flush=True)

def extract_audio(video_path, output_path):
    """从视频提取音频"""
    import subprocess

    log_progress("正在提取音频...", 10)

    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',
        output_path
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    log_progress("音频提取完成", 20)

def transcribe_with_whisper(audio_path, language):
    """使用 Whisper 进行语音识别"""
    import whisper
    import math

    log_progress("正在加载 Whisper 模型...", 25)

    # 加载模型（首次会自动下载）
    model = whisper.load_model("base")

    log_progress("模型加载完成，开始识别...", 35)

    # 执行识别
    result = model.transcribe(
        audio_path,
        language=language,
        verbose=False,
        task='transcribe'
    )

    log_progress("语音识别完成，正在处理结果...", 90)

    # 转换为字幕段
    segments = []
    for seg in result.get('segments', []):
        segments.append({
            'id': len(segments) + 1,
            'start': round(seg['start'], 2),
            'end': round(seg['end'], 2),
            'text': seg['text'].strip(),
            'translated': ''
        })

    return {
        'segments': segments,
        'text': result.get('text', ''),
        'language': result.get('language', language)
    }

def main():
    if len(sys.argv) < 3:
        print("用法: python whisper_service.py <视频文件路径> <语言代码> [--json]")
        sys.exit(1)

    video_path = sys.argv[1]
    language = sys.argv[2]
    output_json = '--json' in sys.argv[3:]

    if not os.path.exists(video_path):
        error = {'error': f'文件不存在: {video_path}'}
        print(json.dumps(error))
        sys.exit(1)

    # 语言代码映射
    lang_map = {
        'ja': 'japanese',
        'en': 'english',
        'zh': 'chinese'
    }
    whisper_lang = lang_map.get(language, 'japanese')

    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = os.path.join(temp_dir, 'audio.wav')

            # 提取音频
            extract_audio(video_path, audio_path)

            # 语音识别
            result = transcribe_with_whisper(audio_path, whisper_lang)

            # 输出结果
            if output_json:
                print(json.dumps(result))
            else:
                for seg in result['segments']:
                    print(f"{seg['start']:.2f} --> {seg['end']:.2f}: {seg['text']}")

    except Exception as e:
        error = {'error': str(e)}
        print(json.dumps(error))
        sys.exit(1)

if __name__ == '__main__':
    main()
