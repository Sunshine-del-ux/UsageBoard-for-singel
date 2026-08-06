#!/usr/bin/env bash
# 在 macOS/Linux 上以开发模式运行 Windows 外壳（PySide6 跨平台，便于调试 UI）。
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-$HOME/.pyenv/shims/python}"
if ! "$PYTHON" -c "import PySide6" 2>/dev/null; then
    echo "安装依赖中…"
    "$PYTHON" -m pip install -r windows/requirements.txt
fi

# 开发配置与 macOS 版隔离，避免污染真实配置
export USAGEBOARD_CONFIG_DIR="${USAGEBOARD_CONFIG_DIR:-$HOME/.config/UsageBoard}"
exec "$PYTHON" -m windows.app.main "$@"
