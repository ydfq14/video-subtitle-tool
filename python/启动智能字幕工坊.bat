@echo off
chcp 65001 >nul
title 智能字幕工坊

echo ========================================
echo     智能字幕工坊 - 启动中...
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查 FFmpeg
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 FFmpeg，请先安装
    echo 安装方法: winget install Gyan.FFmpeg
    echo 或下载: https://ffmpeg.org/download.html
    pause
    exit /b 1
)

REM 检查依赖
echo [1/3] 检查依赖...
pip show openai-whisper >nul 2>&1
if errorlevel 1 (
    echo [2/3] 正在安装 whisper...
    pip install openai-whisper -q
)

pip show PyQt5 >nul 2>&1
if errorlevel 1 (
    echo [3/3] 正在安装 PyQt5...
    pip install PyQt5 -q
)

echo.
echo [完成] 正在启动应用...
echo.

REM 启动应用
python "%~dp0gui.py"

if errorlevel 1 (
    echo.
    echo [错误] 应用启动失败
    pause
)
