"""pytest 共享配置：把仓库根目录加入 sys.path，便于测试导入 windows.app 等包。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
