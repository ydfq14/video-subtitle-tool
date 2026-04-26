# 测试 FFmpeg 字幕烧录
import subprocess
import tempfile
import os
import sys

# 测试1: 检查 FFmpeg 是否支持 subtitles 滤镜
print("=== 测试 FFmpeg ===")
result = subprocess.run(['ffmpeg', '-filters'], capture_output=True, text=True)
if 'subtitles' in result.stdout:
    print("✓ FFmpeg 支持 subtitles 滤镜")
else:
    print("✗ FFmpeg 不支持 subtitles 滤镜")

# 测试2: 检查 ffmpeg-full 版本
result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
print(f"\nFFmpeg 版本:\n{result.stdout.split()[2]}")

# 测试3: 检查是否有 libass
result = subprocess.run(['ffmpeg', '-filters'], capture_output=True, text=True)
if 'libass' in result.stdout:
    print("✓ 有 libass 支持")
else:
    print("✗ 没有 libass 支持")

# 测试4: 尝试用 ASS 格式代替 SRT
print("\n=== 建议使用 ASS 格式 ===")
print("因为 FFmpeg 的 subtitles 滤镜对 SRT 支持不稳定，")
print("建议将 SRT 转换为 ASS 格式后再烧录。")
