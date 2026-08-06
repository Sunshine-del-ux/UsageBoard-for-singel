"""PyInstaller 打包入口：以包方式导入 windows.app.main，避免相对导入失败。

直接运行：python windows/launcher.py
开发模式建议：python -m windows.app.main
"""
import sys
from pathlib import Path

# 允许从任意目录直接运行本脚本
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 插件脚本以数据文件形式随包分发，PyInstaller 无法静态分析其 import。
# 这里显式引入插件用到的标准库，确保它们被打进 exe。
import datetime  # noqa: F401,E402
import hashlib  # noqa: F401,E402
import json  # noqa: F401,E402
import socket  # noqa: F401,E402
import ssl  # noqa: F401,E402
import urllib.error  # noqa: F401,E402
import urllib.parse  # noqa: F401,E402
import urllib.request  # noqa: F401,E402

from windows.app.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
