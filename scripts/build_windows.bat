@echo off
rem UsageBoard Windows 打包脚本（在 Windows 上运行）
rem 产物：dist\UsageBoard.exe（单文件，无需安装 Python）
setlocal
chcp 65001 >nul

cd /d "%~dp0\.."

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3.10+ 并加入 PATH
    exit /b 1
)

echo [1/3] 安装依赖...
python -m pip install -r windows\requirements.txt
if errorlevel 1 exit /b 1

echo [2/3] 清理旧构建...
rem 若旧版正在运行，先结束进程，否则 dist\UsageBoard.exe 会被占用
taskkill /f /im UsageBoard.exe >nul 2>nul
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/3] PyInstaller 打包...
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name UsageBoard ^
    --icon windows\icon.ico ^
    --add-data "Resources\BundledPlugins;plugins" ^
    --add-data "Resources\icon.png;." ^
    windows\launcher.py

if errorlevel 1 (
    echo [错误] 打包失败
    exit /b 1
)

echo.
echo [完成] 产物位于 dist\UsageBoard.exe
endlocal
