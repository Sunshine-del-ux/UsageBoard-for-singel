#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"
DIST_DIR="$PROJECT_DIR/dist"
APP_BUNDLE="$DIST_DIR/UsageBoard.app"
PLIST="$APP_BUNDLE/Contents/Info.plist"
UPDATE_CHECK_URL="${UB_UPDATE_CHECK_URL:-https://may.ltd/usageboard/version.json}"

if [ ! -f "$PLIST" ]; then
    mkdir -p "$(dirname "$PLIST")"
    /usr/libexec/PlistBuddy -c "Add :CFBundleDevelopmentRegion string zh_CN" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string UsageBoard" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string UsageBoard" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string ltd.may.UsageBoard" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleInfoDictionaryVersion string 6.0" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleName string UsageBoard" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundlePackageType string APPL" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string 0.1.0" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string 1" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :LSApplicationCategoryType string 'public.app-category.productivity'" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string 13.0" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :LSUIElement string true" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :NSHighResolutionCapable bool true" "$PLIST"
    /usr/libexec/PlistBuddy -c "Add :NSPrincipalClass string NSApplication" "$PLIST"
fi

# --- Kill running instance ---
pkill -f "UsageBoard.app" 2>/dev/null && echo "已关闭运行中的 UsageBoard" || true

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
rm -f "$APP_BUNDLE/Contents/Resources/Plugins/"*.py
cp "$PROJECT_DIR/Resources/UsageBoard.icns" "$APP_BUNDLE/Contents/Resources/UsageBoard.icns"
cp "$PROJECT_DIR/Resources/PluginAuthoringGuide.html" "$APP_BUNDLE/Contents/Resources/PluginAuthoringGuide.html"
cp "$PROJECT_DIR/Resources/BundledPlugins/"*.py "$APP_BUNDLE/Contents/Resources/Plugins/"

# --- Inject update check URL into Info.plist ---
/usr/libexec/PlistBuddy -c "Add :UBUpdateCheckURL string ${UPDATE_CHECK_URL}" "$PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Set :UBUpdateCheckURL ${UPDATE_CHECK_URL}" "$PLIST"

codesign --force --deep --sign - "$APP_BUNDLE"

# --- Launch ---
echo "启动 UsageBoard..."
open "$APP_BUNDLE"
