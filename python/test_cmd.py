#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import tempfile
import os
import sys

# 重新配置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 生成 ASS 字幕
def generate_ass():
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
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
        'Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello World',
        'Dialogue: 0,0:00:05.00,0:00:08.00,Default,,0,0,0,,Test subtitle'
    ]
    return '\n'.join(lines)

# 创建临时字幕文件
temp_dir = tempfile.gettempdir()
temp_sub = os.path.join(temp_dir, 'test_subtitle.ass')
with open(temp_sub, 'w', encoding='utf-8-sig') as f:
    f.write(generate_ass())

print(f"字幕文件: {temp_sub}")
print(f"字幕文件存在: {os.path.exists(temp_sub)}")

# 读取并显示字幕内容
with open(temp_sub, 'r', encoding='utf-8-sig') as f:
    content = f.read()
print(f"\n字幕内容:\n{content}")

# 测试视频文件 - 你需要修改为实际存在的视频文件路径
# video_path = r"你的视频文件路径"
# output_path = os.path.join(temp_dir, 'output.mp4')

# 测试 FFmpeg 命令
print("\n" + "="*50)
print("测试 FFmpeg 命令格式")
print("="*50)

# 使用英文提示
print("\n请修改脚本中的 video_path 为你的实际视频文件路径")
print("然后运行以下命令测试:\n")

example_video = r"D:\test\video.mp4"
example_output = os.path.join(temp_dir, 'output.mp4')
temp_sub_ffmpeg = temp_sub.replace('\\', '/')

cmd = [
    'ffmpeg', '-y',
    '-i', example_video,
    '-vf', f'subtitles={temp_sub_ffmpeg}',
    '-c:a', 'copy',
    example_output
]

print("示例命令:")
print(' '.join(cmd))

# 如果有测试视频，取消注释下面这行运行测试
# result = subprocess.run(cmd, capture_output=True, text=True)
# print(f"\n返回码: {result.returncode}")
# if result.returncode != 0:
#     print(f"错误:\n{result.stderr}")
