# Intel Mac 兼容移植 — 设计文档

> 日期：2026-08-06
> 子项目：跨平台移植 1/3（Intel Mac → iOS → Windows）
> 状态：已与用户确认方案 A，待实现

---

## 1. 背景与目标

UsageBoard 目前只能在 Apple Silicon（M 系列）Mac 上构建和运行。用户的开发机是 Intel 架构 Mac（macOS 15，Swift 6.2.4），无法构建也无法运行本项目。

本子项目目标：

- 项目可在 Intel Mac 上完整编译、测试、运行。
- 发布物（zip 分发包）同时支持 arm64 与 x86_64，任一架构的机器下载后都能运行。
- 不引入与目标无关的重构，为后续 iOS / Windows 子项目保留现状即可。

非目标（YAGNI）：

- 不为 iOS / Windows 提前抽象核心层（`UsageBoardCore` 已是纯 Foundation、无 AppKit 依赖，届时直接复用）。
- 不改动更新检查协议与 `version.json` 结构。
- 不改动任何 Python 插件（架构中性，无需处理）。

## 2. 问题根因

1. **本机无法编译**：`Package.swift` 第 1 行声明 `swift-tools-version: 6.3`，本机工具链为 Swift 6.2.4，SPM 拒绝解析。代码本身为纯标准 Swift 6 写法，无 arm64 专属代码。
2. **发布物为单架构**：`scripts/build.sh` 与 `scripts/release.sh` 使用裸 `swift build -c release`，只产出构建机架构的二进制。在 M 系列机器上发布的 zip 不含 x86_64 切片，Intel 用户下载后无法运行。`version.json` 仅含单一 `downloadURL`，`UpdateChecker` 不区分架构。

其余部分均为架构中性：Python 插件、ad-hoc 签名、`LSMinimumSystemVersion 13.0`。

## 3. 方案选型

| 方案 | 内容 | 结论 |
| --- | --- | --- |
| A（选用） | tools-version 降为 6.2；构建加 `--arch arm64 --arch x86_64` 产出 universal 二进制 | 本机立即可编译；单一发布物；`version.json` / `UpdateChecker` 零改动；体积翻倍但本 app 仅数 MB，无感 |
| B | 保留 6.3，升级本机工具链 | 只解决本机编译，不解决发布物缺 x86_64 切片；Intel 版 6.3 工具链可用性不可控。否决 |
| C | 按架构分别分发（双 zip + `version.json` 加架构字段 + `UpdateChecker` 按架构选包） | 改动面大（发布脚本、服务端、客户端更新逻辑），对本 app 体积无实际收益。否决 |

## 4. 设计详情

### 4.1 Package.swift

- `swift-tools-version: 6.3` → `6.2`。
- 第一步即验证 `swift build` / `swift test` 在 6.2 下全绿；若发现使用了 6.3 专属语法，单独评估改写（预期没有）。
- 其余声明（`platforms: [.macOS(.v13)]`、`swiftLanguageModes: [.v6]`、target 布局）保持不变。

### 4.2 构建与发布脚本

`scripts/build.sh` 与 `scripts/release.sh`：

- 构建命令改为 `swift build -c release --arch arm64 --arch x86_64`。
- 打包后、签名前，用 `lipo -info` 校验 `UsageBoard` 二进制包含 `x86_64 arm64` 两个切片，缺任一则报错中止。
- 签名（ad-hoc `codesign --force --deep --sign -`）、zip 打包、`version.json` 生成、上传流程不变——universal 包维持单一 `downloadURL`。

### 4.3 验证

- `swift build`：通过。
- `swift test`：Core 层 XCTest 全绿。
- `python3 -m pytest Tests/PluginTests/ -v`：插件测试全绿。
- `bash scripts/build.sh` 打包后在本机（Intel）实际启动 app：菜单栏图标可点开 popover、至少启用一个 API-Key 类插件刷新成功。
- `lipo -info dist/UsageBoard.app/Contents/MacOS/UsageBoard` 输出包含 `x86_64 arm64`。

### 4.4 文档

- `README.md` / `README_EN.md`：系统要求处补充"支持 Intel 与 Apple Silicon（universal 二进制）"。
- `docs/architecture.md`：发布一节补充 universal 构建说明。

## 5. 风险与对策

| 风险 | 概率 | 对策 |
| --- | --- | --- |
| 代码含 6.3 专属语法，降 6.2 后编译失败 | 低 | 首个任务即全量编译验证；若有个别语法点，改写为 6.2 兼容写法 |
| Intel 机器上交叉编译 arm64 切片失败 | 低 | Xcode SDK 天然支持双向交叉编译；失败时检查 Xcode 命令行工具完整性 |
| 旧发布物（arm64-only）已被 Intel 用户下载 | 中 | 本次发布后出的第一个版本即为 universal，覆盖即可，无需兼容处理 |

## 6. 后续子项目衔接

- **iOS（iPhone）**：另立 spec。已知约束：Claude / Codex 两个插件依赖 macOS 本地凭证与日志文件，iOS 上不可用；5 个 API-Key 类插件（GLM / MiniMax / DeepSeek / Kimi / Tavily）可直接在 iOS 实现。
- **Windows**：另立 spec。已知约束：插件层为 Python 脚本，Windows 端需解决 Python 运行时依赖或改写插件。
