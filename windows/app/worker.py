"""后台刷新：QThreadPool + QRunnable，结果经信号回到主线程。"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .plugins import run_plugin


class _Signals(QObject):
    finished = Signal(str, dict)  # card_id, result


class RefreshJob(QRunnable):
    def __init__(self, plugin_id: str, params: dict[str, str], language: str,
                 on_finished: Callable[[str, dict], None],
                 card_id: str | None = None):
        super().__init__()
        self._plugin_id = plugin_id      # 执行哪个插件（类型）
        self._card_id = card_id or plugin_id  # 结果路由到哪张卡片（实例）
        self._params = params
        self._language = language
        self._signals = _Signals()
        self._signals.finished.connect(on_finished)

    def run(self) -> None:
        try:
            result = run_plugin(self._plugin_id, self._params, self._language)
        except Exception as exc:  # run_plugin 理论上不会抛，兜底防止卡片永远停在加载中
            result = {"error": f"插件执行失败: {self._plugin_id}: {type(exc).__name__}: {exc}"}
        self._signals.finished.emit(self._card_id, result)


class WorkerPool:
    def __init__(self, on_result: Callable[[str, dict], None]):
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(4)
        self._on_result = on_result
        self._jobs: list[RefreshJob] = []  # 保持引用，避免 GC

    def refresh(self, plugin_id: str, params: dict[str, str], language: str,
                card_id: str | None = None) -> None:
        job = RefreshJob(plugin_id, params, language, self._on_result,
                         card_id=card_id)
        self._jobs.append(job)
        job._signals.finished.connect(lambda *_: self._discard(job))
        self._pool.start(job)

    def _discard(self, job: RefreshJob) -> None:
        try:
            self._jobs.remove(job)
        except ValueError:
            pass

    def wait_for_done(self, msecs: int = 10000) -> bool:
        return self._pool.waitForDone(msecs)
