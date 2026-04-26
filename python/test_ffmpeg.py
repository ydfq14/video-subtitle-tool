# 测试 FFmpeg 字幕烧录
import subprocess
import tempfile
import os

# 创建测试字幕
srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello World 你好

2
00:00:05,000 --> 00:00:08,000
This is a test 这是测试
"""

# 创建临时字幕文件
temp_dir = tempfile.gettempdir()
temp_sub = os.path.join(temp_dir, 'test_subtitle.srt')
with open(temp_sub, 'w', encoding='utf-8-sig') as f:
    f.write(srt_content)

print(f"字幕文件: {temp_sub}")
print(f"字幕文件存在: {os.path.exists(temp_sub)}")

# 读取字幕内容
with open(temp_sub, 'r', encoding='utf-8-sig') as f:
    content = f.read()
    print(f"字幕内容预览:\n{content[:200]}")

# 构建 FFmpeg 命令
video_path = r"D:\Project\Visual Studio Code\video-subtitle-tool\test.mp4"
output_path = os.path.join(temp_dir, 'output_test.mp4')

# 使用正确的路径格式
temp_sub_escaped = temp_sub.replace('\\', '/')

cmd = [
    'ffmpeg', '-y',
    '-i', video_path,
    '-vf', f'subtitles={temp_sub_escaped}',
    '-c:a', 'copy',
    output_path
]

print(f"\n执行命令:")
print(' '.join(cmd))

# 执行
result = subprocess.run(cmd, capture_output=True, text=True)

print(f"\n返回码: {result.returncode}")
if result.returncode != 0:
    print(f"错误输出:\n{result.stderr[-1000:]}")
else:
    print("成功!")
