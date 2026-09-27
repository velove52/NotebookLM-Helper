@echo off
chcp 65001 >nul
title NotebookLM Helper
cd /d "%~dp0"

echo ============================================================
echo              Google NotebookLM 助手工具
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有检测到 Python，请先安装: https://www.python.org/downloads/
  echo        安装时务必勾选 "Add Python to PATH"
  echo.
  pause
  exit /b
)

if not exist cookie.txt (
  echo [提示] 当前目录下没有找到 cookie.txt
  echo        请先按 README.txt 里的步骤导出 Cookie 并保存为 cookie.txt
  echo.
  pause
  exit /b
)

echo 正在检查依赖包...
python -m pip install -q requests urllib3 configparser

echo.
echo ------------------------------------------------------------
echo   请选择功能:
echo     [1] 查看 / 批量删除 笔记本数据源
echo     [2] 上传文件 / 网页链接 / 纯文本 到笔记本
echo     [0] 退出
echo ------------------------------------------------------------
echo.
set /p choice=请输入序号后按回车: 

if "%choice%"=="1" python notebooklm_helper.py
if "%choice%"=="2" python notebooklm_uploader.py
if "%choice%"=="0" exit /b
echo.
pause
