"""外壳 UI 文案（zh-Hans / en）。"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "app_title":        {"zh-Hans": "UsageBoard", "en": "UsageBoard"},
    "show_panel":       {"zh-Hans": "显示面板", "en": "Show Panel"},
    "hide_panel":       {"zh-Hans": "隐藏面板", "en": "Hide Panel"},
    "refresh_now":      {"zh-Hans": "立即刷新", "en": "Refresh Now"},
    "settings":         {"zh-Hans": "设置", "en": "Settings"},
    "settings_general": {"zh-Hans": "通用", "en": "General"},
    "quit":             {"zh-Hans": "退出", "en": "Quit"},
    "refreshing":       {"zh-Hans": "刷新中…", "en": "Refreshing…"},
    "updated_at":       {"zh-Hans": "更新于 {time}", "en": "Updated at {time}"},
    "never_updated":    {"zh-Hans": "尚未更新", "en": "Not updated yet"},
    "open_settings":    {"zh-Hans": "打开设置", "en": "Open Settings"},
    "language":         {"zh-Hans": "语言", "en": "Language"},
    "language_auto":    {"zh-Hans": "跟随系统", "en": "System Default"},
    "refresh_interval": {"zh-Hans": "刷新间隔（秒）", "en": "Refresh Interval (sec)"},
    "enabled":          {"zh-Hans": "启用", "en": "Enabled"},
    "save":             {"zh-Hans": "保存", "en": "Save"},
    "cancel":           {"zh-Hans": "取消", "en": "Cancel"},
    "reset_at":         {"zh-Hans": "重置时间 {time}", "en": "Resets at {time}"},
    "reset_today":      {"zh-Hans": "今天 {time}", "en": "Today {time}"},
    "reset_tomorrow":   {"zh-Hans": "明天 {time}", "en": "Tomorrow {time}"},
    "error_badge":      {"zh-Hans": "错误", "en": "Error"},
    "no_limit":         {"zh-Hans": "已用 {used}", "en": "Used {used}"},
    "usage_of":         {"zh-Hans": "{used} / {limit}", "en": "{used} / {limit}"},
    "loading":          {"zh-Hans": "加载中…", "en": "Loading…"},
    "collapse_panel":   {"zh-Hans": "收起面板", "en": "Collapse Panel"},
    "add_account":      {"zh-Hans": "添加账号", "en": "Add Account"},
    "account_name":     {"zh-Hans": "备注名称", "en": "Label"},
    "account_default":  {"zh-Hans": "账号 {n}", "en": "Account {n}"},
    "remove_account":   {"zh-Hans": "删除", "en": "Remove"},
}

_current = "zh-Hans"


def set_language(language: str) -> None:
    global _current
    _current = language if language in ("zh-Hans", "en") else "zh-Hans"


def language() -> str:
    return _current


def tr(key: str, **kwargs) -> str:
    text = STRINGS.get(key, {}).get(_current) or STRINGS.get(key, {}).get("zh-Hans") or key
    return text.format(**kwargs) if kwargs else text


def system_language() -> str:
    """根据系统区域推断语言（中文环境 → zh-Hans，其余 → en）。"""
    try:
        from PySide6.QtCore import QLocale
        if QLocale.system().language() == QLocale.Language.Chinese:
            return "zh-Hans"
        return "en"
    except ImportError:
        import locale
        name = (locale.getlocale()[0] or "").lower()
        return "zh-Hans" if name.startswith("zh") else "en"
