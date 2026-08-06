# UsageBoard for Windows

UsageBoard 的 Windows 版本：基于 **Python + PySide6** 的系统托盘应用，复用 macOS 版的插件体系（进程内调用），单面板卡片式展示用量。

## 功能

- 系统托盘常驻，左键单击弹出/收起用量面板（屏幕右下角，无边框卡片式）
- 内置 4 个 API 插件：DeepSeek、Kimi、智谱 GLM、MiniMax
- 托盘右键菜单：显示面板 / 立即刷新 / 设置 / 退出
- 设置对话框由插件清单自动生成（API Key、金额上限、统计周期、订阅计划等）
- 自动刷新（默认 5 分钟，可在设置中调整，最低 30 秒）
- 中英文界面（默认跟随系统语言）
- 配置保存在 `%APPDATA%\UsageBoard\config.json`

## 构建（在 Windows 上）

需要 Windows 10/11 + Python 3.10 或更高版本（安装时勾选 Add to PATH）。

```bat
scripts\build_windows.bat
```

产物为 `dist\UsageBoard.exe`，单文件、免安装，双击即可运行。

## 开发（macOS / Linux / Windows）

PySide6 跨平台，可直接在开发机上运行界面调试：

```bash
scripts/dev_run.sh
```

开发模式下配置写入 `~/.config/UsageBoard/config.json`（可用环境变量
`USAGEBOARD_CONFIG_DIR` 覆盖），不会读写 macOS 版的配置。

## 测试

```bash
pytest -q
```

## 架构说明

```
windows/
  app/
    main.py      入口：QApplication + 托盘 + 面板 + 定时刷新
    tray.py      系统托盘图标与菜单
    panel.py     无边框弹出面板（单面板滚动卡片）
    cards.py     插件卡片与用量条目组件
    settings.py  设置对话框（由插件清单动态生成表单）
    config.py    配置读写（%APPDATA%\UsageBoard\config.json）
    plugins.py   插件发现、清单解析、进程内调用
    worker.py    QThreadPool 后台刷新
    i18n.py      界面文案（zh-Hans / en）
```

插件代码与 macOS 版共用同一来源 `Resources/BundledPlugins/`，构建时经
PyInstaller `--add-data` 打包进 exe，运行时通过每个插件新增的
`run(params) -> dict` 入口进程内调用（CLI 用法不受影响）。

## 与 macOS 版的差异（v1）

- 暂不渲染用量趋势图（GLM 插件的 chart 数据仍会获取，仅不展示）
- 无开机自启动开关
- 无插件市场，仅内置 4 个插件
