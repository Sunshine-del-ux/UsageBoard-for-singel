# Intel Mac 兼容移植 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 UsageBoard 在 Intel Mac（Swift 6.2.4 工具链）上可编译、可测试、可运行，并使发布脚本产出同时含 arm64 + x86_64 切片的 universal app。

**Architecture:** 不改任何 Swift/Python 源码逻辑。仅三处改动：①`Package.swift` tools-version 6.3→6.2；②`scripts/build.sh` 与 `scripts/release.sh` 把裸 `swift build -c release` 换成「按 triple 分别构建 + `lipo -create` 合并 + `lipo -info` 校验」；③README 与架构文档同步。已实测：本机仅装 Command Line Tools（无完整 Xcode），`swift build --arch arm64 --arch x86_64` 因依赖 XCBuild 不可用，必须走 `--triple` + `lipo` 路线；产物路径确定为 `.build/<arch>-apple-macosx/release/UsageBoard`。

**Tech Stack:** SwiftPM（Swift 6.2.4，CLT only）、bash、lipo、XCTest、pytest（pyenv python 3.12）。

## Global Constraints

- `Package.swift` 其余声明保持不变：`platforms: [.macOS(.v13)]`、`swiftLanguageModes: [.v6]`、target 布局不动。
- 部署目标保持 macOS 13.0：triple 只写 `arm64-apple-macosx` / `x86_64-apple-macosx`（不带版本号），部署版本由 manifest 的 `platforms: [.macOS(.v13)]` 驱动。
- `version.json` 结构与 `UpdateChecker` 不动，维持单一 `downloadURL`。
- 不改任何 Python 插件。
- 提交信息遵循仓库惯例：中文 conventional commits（如 `fix(ui): ...`、`docs: ...`）。
- 不运行 `scripts/release.sh` 的上传段（scp/ssh 到生产服务器属于用户决定）；只验证其构建逻辑。
- 每个验证命令的「Expected」必须与实跑结果一致才能进入下一步。
- 【执行期修订 2026-08-06】本机仅 Command Line Tools，无 XCTest 框架（已实测 `swift build --build-tests` 报 `no such module 'XCTest'`），`swift test` 在本机无法运行。本计划不改任何 Swift 源码，`swift build`（含双架构 release）即覆盖全部编译面；故本机验证以 `swift build` + pytest 为准，XCTest 单元测试保留给装有 Xcode 的机器（如 M 系列 Mac / CI）执行。涉及步骤：Task 1 Step 3、Task 5 Step 2。

---

### Task 1: 降级 swift-tools-version 至 6.2 并全量验证

**Files:**
- Modify: `Package.swift:1`

**Interfaces:**
- Consumes: 无
- Produces: 可编译仓库；后续所有任务依赖本任务的构建能力

- [ ] **Step 1: 修改 tools-version**

`Package.swift` 第 1 行：

```swift
// swift-tools-version: 6.3
```

改为：

```swift
// swift-tools-version: 6.2
```

- [ ] **Step 2: 全量编译验证**

Run: `swift build 2>&1 | tail -5`
Expected: 输出 `Build complete!`，无 error。若有 6.3 专属语法报错，逐个改写为 6.2 兼容写法后重跑（预期没有）。

- [ ] **Step 3: 运行 Swift 单元测试（本机环境受限，见 Global Constraints 修订）**

Run: `swift test 2>&1 | tail -5`
Expected: 全部测试 PASS（`Test Suite 'All tests' passed`），0 failure。
本机实测：无 XCTest（CLT only），此步骤在本机不可执行，以 Step 2 的 `swift build` 全量编译替代；XCTest 在有 Xcode 的机器上执行。

- [ ] **Step 4: 安装 pytest 并运行插件测试**

pytest 当前未安装（pyenv python 3.12.12，pip 可用）：

```bash
python3 -m pip install pytest 2>&1 | tail -1
python3 -m pytest Tests/PluginTests/ -v 2>&1 | tail -15
```

Expected: 第一行输出 `Successfully installed pytest-...`（或 already satisfied）；第二行所有用例 PASSED，0 failed。

- [ ] **Step 5: Commit**

```bash
git add Package.swift
git commit -m "build: swift-tools-version 降级至 6.2 以支持 Intel Mac 工具链"
```

---

### Task 2: build.sh 改为 universal 构建

**Files:**
- Modify: `scripts/build.sh:32-39`

**Interfaces:**
- Consumes: Task 1 的可编译仓库
- Produces: `bash scripts/build.sh` 产出的 `dist/UsageBoard.app/Contents/MacOS/UsageBoard` 为 universal 二进制（后续 Task 3/5 用 `lipo -info` 复验）

- [ ] **Step 1: 替换构建与拷贝段**

`scripts/build.sh` 现有第 32-39 行：

```bash
# --- Build ---
echo "构建 release..."
swift build -c release

# --- Copy binary & plugins ---
echo "打包 app..."
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources/Plugins"
cp .build/release/UsageBoard "$APP_BUNDLE/Contents/MacOS/UsageBoard"
```

替换为：

```bash
# --- Build (universal: arm64 + x86_64) ---
echo "构建 release (arm64)..."
swift build -c release --triple arm64-apple-macosx
echo "构建 release (x86_64)..."
swift build -c release --triple x86_64-apple-macosx

UNIVERSAL_BIN=".build/UsageBoard-universal"
lipo -create \
  .build/arm64-apple-macosx/release/UsageBoard \
  .build/x86_64-apple-macosx/release/UsageBoard \
  -output "$UNIVERSAL_BIN"

ARCHS="$(lipo -info "$UNIVERSAL_BIN")"
echo "二进制架构: $ARCHS"
case "$ARCHS" in
  *arm64*x86_64*|*x86_64*arm64*) ;;
  *) echo "错误: 二进制缺少 arm64 或 x86_64 切片" >&2; exit 1 ;;
esac

# --- Copy binary & plugins ---
echo "打包 app..."
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources/Plugins"
cp "$UNIVERSAL_BIN" "$APP_BUNDLE/Contents/MacOS/UsageBoard"
rm -f "$UNIVERSAL_BIN"
```

- [ ] **Step 2: 语法检查**

Run: `bash -n scripts/build.sh`
Expected: 无输出（语法正确）。

- [ ] **Step 3: 实跑 build.sh 并验证架构**

Run: `bash scripts/build.sh 2>&1 | tail -8`
Expected: 依次出现 `构建 release (arm64)...`、`构建 release (x86_64)...`、`二进制架构: ... x86_64 arm64`（顺序可互换）、`打包 app...`、`启动 UsageBoard...`，无 error。

- [ ] **Step 4: 验证包内二进制与进程**

```bash
lipo -info dist/UsageBoard.app/Contents/MacOS/UsageBoard
pgrep -fl "UsageBoard.app"
```

Expected: 第一行输出 `Architectures in the fat file: ... are: x86_64 arm64`；第二行输出一个 PID 和 app 路径（app 已在本机启动，菜单栏出现图标）。

- [ ] **Step 5: Commit**

```bash
git add scripts/build.sh
git commit -m "feat(build): build.sh 产出 arm64+x86_64 universal 二进制"
```

---

### Task 3: release.sh 改为 universal 构建

**Files:**
- Modify: `scripts/release.sh:59-66`

**Interfaces:**
- Consumes: Task 2 已验证的构建命令序列（逐字复用）
- Produces: release zip 内 app 为 universal 二进制

- [ ] **Step 1: 替换构建与拷贝段**

`scripts/release.sh` 现有第 59-66 行：

```bash
# --- Build ---
echo "构建 release..."
swift build -c release

# --- Copy binary & plugins ---
echo "打包 app..."
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources/Plugins"
cp .build/release/UsageBoard "$APP_BUNDLE/Contents/MacOS/UsageBoard"
```

替换为：

```bash
# --- Build (universal: arm64 + x86_64) ---
echo "构建 release (arm64)..."
swift build -c release --triple arm64-apple-macosx
echo "构建 release (x86_64)..."
swift build -c release --triple x86_64-apple-macosx

UNIVERSAL_BIN=".build/UsageBoard-universal"
lipo -create \
  .build/arm64-apple-macosx/release/UsageBoard \
  .build/x86_64-apple-macosx/release/UsageBoard \
  -output "$UNIVERSAL_BIN"

ARCHS="$(lipo -info "$UNIVERSAL_BIN")"
echo "二进制架构: $ARCHS"
case "$ARCHS" in
  *arm64*x86_64*|*x86_64*arm64*) ;;
  *) echo "错误: 二进制缺少 arm64 或 x86_64 切片" >&2; exit 1 ;;
esac

# --- Copy binary & plugins ---
echo "打包 app..."
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources/Plugins"
cp "$UNIVERSAL_BIN" "$APP_BUNDLE/Contents/MacOS/UsageBoard"
rm -f "$UNIVERSAL_BIN"
```

- [ ] **Step 2: 语法检查与逻辑干跑验证（不触发上传）**

```bash
bash -n scripts/release.sh
# 逐字执行脚本中的构建命令，验证产物（不运行完整 release.sh，避免 scp 上传）
swift build -c release --triple arm64-apple-macosx 2>&1 | tail -1
swift build -c release --triple x86_64-apple-macosx 2>&1 | tail -1
lipo -create .build/arm64-apple-macosx/release/UsageBoard .build/x86_64-apple-macosx/release/UsageBoard -output .build/UsageBoard-universal
lipo -info .build/UsageBoard-universal
rm -f .build/UsageBoard-universal
```

Expected: `bash -n` 无输出；两次构建均 `Build complete!`；`lipo -info` 输出含 `x86_64 arm64`。

- [ ] **Step 3: Commit**

```bash
git add scripts/release.sh
git commit -m "feat(build): release.sh 产出 arm64+x86_64 universal 二进制"
```

---

### Task 4: 文档同步（README ×2 + 架构文档）

**Files:**
- Modify: `README.md:327-337`
- Modify: `README_EN.md:320-330`
- Modify: `docs/architecture.md:38-44`

**Interfaces:**
- Consumes: Task 1-3 已落地的行为
- Produces: 文档与实际构建行为一致

- [ ] **Step 1: README.md 系统要求**

`README.md` 第 329-337 行现有内容：

```markdown
运行：

- macOS 13.0 或更高版本
- 系统可用 `python3`，用于执行 Python 插件

开发：

- Xcode
- Swift 6.3 toolchain
```

改为：

```markdown
运行：

- macOS 13.0 或更高版本，支持 Intel 与 Apple Silicon（universal 二进制）
- 系统可用 `python3`，用于执行 Python 插件

开发：

- Xcode 或 Command Line Tools
- Swift 6.2 及以上 toolchain
```

- [ ] **Step 2: README_EN.md 系统要求**

`README_EN.md` 第 322-330 行现有内容：

```markdown
Runtime:

- macOS 13.0 or later
- System `python3` available for executing Python plugins

Development:

- Xcode
- Swift 6.3 toolchain
```

改为：

```markdown
Runtime:

- macOS 13.0 or later, on both Intel and Apple Silicon (universal binary)
- System `python3` available for executing Python plugins

Development:

- Xcode or Command Line Tools
- Swift 6.2+ toolchain
```

- [ ] **Step 3: 架构文档构建命令**

`docs/architecture.md` 第 38-44 行附近「常用验证命令」代码块现有内容：

```markdown
```sh
swift build               # 编译检查
swift test                # Core 单元测试
swift build -c release    # release 构建
bash scripts/build.sh     # 本地 app 构建、签名、启动
python3 -m pytest Tests/PluginTests/ -v   # Python 插件测试
```
```

改为：

````markdown
```sh
swift build               # 编译检查
swift test                # Core 单元测试
swift build -c release --triple arm64-apple-macosx    # release 构建（arm64）
swift build -c release --triple x86_64-apple-macosx   # release 构建（x86_64）
bash scripts/build.sh     # 本地 app 构建（universal：两个 triple 构建后 lipo 合并）、签名、启动
python3 -m pytest Tests/PluginTests/ -v   # Python 插件测试
```
````

- [ ] **Step 4: Commit**

```bash
git add README.md README_EN.md docs/architecture.md
git commit -m "docs: 系统要求补充 Intel/Apple Silicon 支持，构建命令改为 universal"
```

---

### Task 5: 端到端收尾验证

**Files:**
- 无修改，仅验证

**Interfaces:**
- Consumes: Task 1-4 全部产物
- Produces: 移植完成的确认结论

- [ ] **Step 1: 干净环境全量构建**

```bash
rm -rf .build dist
bash scripts/build.sh 2>&1 | tail -6
```

Expected: 双架构构建 + `二进制架构: ... x86_64 arm64` + 打包 + 启动，无 error。

- [ ] **Step 2: 全量测试（本机环境受限，见 Global Constraints 修订）**

```bash
swift build 2>&1 | tail -3
python3 -m pytest Tests/PluginTests/ 2>&1 | tail -3
```

Expected: `Build complete!` + pytest 全部 PASSED，0 failed。`swift test` 本机无 XCTest 不可执行，改由有 Xcode 的机器执行。

- [ ] **Step 3: 包内二进制最终确认**

Run: `lipo -info dist/UsageBoard.app/Contents/MacOS/UsageBoard`
Expected: `Architectures in the fat file: ... are: x86_64 arm64`

- [ ] **Step 4: 用户手动确认**

请用户在菜单栏点击 UsageBoard 图标，确认 popover 正常打开、至少一个插件可刷新成功。这是唯一无法自动化的验证点。

---

## Self-Review 记录

- **Spec 覆盖**：spec §4.1 → Task 1；§4.2 → Task 2 + Task 3；§4.3 → Task 1 Step 2-4 + Task 2 Step 3-4 + Task 5；§4.4 → Task 4。风险表中「6.3 专属语法」对策落在 Task 1 Step 2；「旧发布物覆盖」无需任务（首次 universal 发布自然覆盖）。
- **占位符**：无 TBD/TODO；所有代码与命令为完整内容。
- **类型/命令一致性**：Task 2 与 Task 3 的替换代码逐字一致；`lipo` 产物路径 `.build/<arch>-apple-macosx/release/UsageBoard` 已在本机实测确认；`--arch` 多架构路线已实测不可用（CLT 无 XCBuild），未写入计划。
