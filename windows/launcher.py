"""PyInstaller 打包入口：以包方式导入 windows.app.main，避免相对导入失败。

直接运行：python windows/launcher.py
开发模式建议：python -m windows.app.main
"""
import sys
from pathlib import Path

# 允许从任意目录直接运行本脚本
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from windows.app.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
