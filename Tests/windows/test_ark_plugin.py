"""ark-usage-plugin.py 的单元测试（火山方舟 Coding Plan 用量插件）。"""
from __future__ import annotations

import importlib.util
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

PLUGIN_PATH = (Path(__file__).resolve().parents[2]
               / "Resources" / "BundledPlugins" / "ark-usage-plugin.py")


@pytest.fixture()
def ark():
    spec = importlib.util.spec_from_file_location("ark_usage_plugin", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def usage_payload() -> dict[str, Any]:
    return {
        "ResponseMetadata": {"RequestId": "req-1"},
        "Result": {
            "Status": "ok",
            "UpdateTimestamp": 1780000000,
            "QuotaUsage": [
                {"Level": "session", "Percent": 12.3,
                 "ResetTimestamp": 1780006800},
                {"Level": "weekly", "Percent": 85.0,
                 "ResetTimestamp": 1780500000},
                {"Level": "monthly", "Percent": 5.0, "ResetTimestamp": -1},
            ],
        },
    }


def plan_payload(plan_type: str = "Pro") -> dict[str, Any]:
    return {
        "ResponseMetadata": {},
        "Result": {"PlanType": plan_type, "Status": "Running",
                   "StartTime": "2026-01-01T00:00:00Z",
                   "EndTime": "2027-01-01T00:00:00Z", "AutoRenew": True},
    }


class FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def fake_urlopen(payloads: dict[str, dict[str, Any]]):
    """按请求 URL 中的 Action 返回对应响应体。"""
    def _open(request, timeout=0):
        for action, payload in payloads.items():
            if f"Action={action}" in request.full_url:
                return FakeResponse(payload)
        raise AssertionError(f"未 mock 的请求: {request.full_url}")
    return _open


# ─── 签名 ────────────────────────────────────────────────────────────────────

def test_signed_request_known_answer(ark):
    request = ark.signed_request(
        "GetCodingPlanUsage", "AKLTtest123", "secret-test-456", "{}",
        now=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    assert request.full_url == (
        "https://open.volcengineapi.com/"
        "?Action=GetCodingPlanUsage&Region=cn-beijing&Version=2024-01-01")
    assert request.data == b"{}"
    assert request.headers["X-date"] == "20260102T030405Z"
    # sha256("{}") 的公开已知值
    assert request.headers["X-content-sha256"] == (
        "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a")
    auth = request.headers["Authorization"]
    assert auth.startswith(
        "HMAC-SHA256 Credential=AKLTtest123/20260102/cn-beijing/ark/request, "
        "SignedHeaders=content-type;host;x-content-sha256;x-date, Signature=")
    # 固定输入的回归签名
    assert auth.endswith(
        "05a35ba959b2a1e41dc29883c04e3c4028069f4498d49228a8e7272c462e56b3")


def test_canonical_query_sorted_and_encoded(ark):
    query = ark._canonical_query({"Version": "a b", "Action": "X~y", "Region": "cn-beijing"})
    assert query == "Action=X~y&Region=cn-beijing&Version=a%20b"


# ─── 响应解析 ────────────────────────────────────────────────────────────────

def test_build_items_orders_and_maps(ark):
    items = ark.build_items(usage_payload(), "zh-Hans")
    assert [item["id"] for item in items] == ["ark-session", "ark-weekly", "ark-monthly"]
    session, weekly, monthly = items
    assert session["name"] == "5 小时用量"
    assert session["used"] == 12.3 and session["limit"] == 100
    assert session["displayStyle"] == "percent"
    assert session["resetAt"].endswith("Z")
    assert weekly["color"] == "orange" and weekly["status"] == "warning"
    # ResetTimestamp = -1 表示无重置时间
    assert monthly["resetAt"] is None


def test_build_items_en_names(ark):
    items = ark.build_items(usage_payload(), "en")
    assert [item["name"] for item in items] == [
        "5-hour usage", "Weekly usage", "Monthly usage"]


def test_build_items_handles_missing_levels(ark):
    payload = {"Result": {"QuotaUsage": [
        {"Level": "weekly", "Percent": 42, "ResetTimestamp": 1780000000},
        {"Level": "bogus", "Percent": 1},
    ]}}
    items = ark.build_items(payload, "zh-Hans")
    assert [item["id"] for item in items] == ["ark-weekly"]
    assert ark.build_items({"Result": {}}, "zh-Hans") == []
    assert ark.build_items({}, "zh-Hans") == []


def test_api_error_extraction(ark):
    assert ark.api_error({"Result": {}}) is None
    payload = {"ResponseMetadata": {"Error": {
        "Code": "InvalidAccessKeyId", "Message": "bad ak"}}}
    assert ark.api_error(payload) == "InvalidAccessKeyId: bad ak"


# ─── run() 端到端（mock 网络）──────────────────────────────────────────────

def test_run_missing_keys(ark):
    result = ark.run({})
    assert "ACCESS_KEY" not in result
    assert result["error"] == "请在插件设置中配置 Access Key 和 Secret Key"
    assert ark.run({}, )["error"] != ark.run({"USAGEBOARD_LANGUAGE": "en"})["error"]


def test_run_success_with_badge(ark, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen({
        "GetCodingPlanUsage": usage_payload(),
        "GetPersonalPlan": plan_payload("Pro"),
    }))
    result = ark.run({"ACCESS_KEY": "ak", "SECRET_KEY": "sk",
                      "USAGEBOARD_LANGUAGE": "zh-Hans"})
    assert "error" not in result
    assert result["badge"] == "Pro"
    assert result["badgeColor"] == "orange"
    assert len(result["items"]) == 3
    assert result["schemaVersion"] == 1 and result["updatedAt"]


def test_run_badge_failure_still_succeeds(ark, monkeypatch):
    def _open(request, timeout=0):
        if "Action=GetCodingPlanUsage" in request.full_url:
            return FakeResponse(usage_payload())
        raise TimeoutError("plan endpoint down")
    monkeypatch.setattr("urllib.request.urlopen", _open)
    result = ark.run({"ACCESS_KEY": "ak", "SECRET_KEY": "sk"})
    assert "error" not in result
    assert "badge" not in result


def test_run_api_error_in_200(ark, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen({
        "GetCodingPlanUsage": {"ResponseMetadata": {"Error": {
            "Code": "SignatureDoesNotMatch", "Message": "check your sk"}}},
    }))
    result = ark.run({"ACCESS_KEY": "ak", "SECRET_KEY": "bad"})
    assert result["error"] == "SignatureDoesNotMatch: check your sk"


def test_run_empty_quota(ark, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen({
        "GetCodingPlanUsage": {"Result": {"QuotaUsage": []}},
    }))
    result = ark.run({"ACCESS_KEY": "ak", "SECRET_KEY": "sk"})
    assert result["error"] == "未获取到配额数据"


def test_run_http_error_with_openapi_body(ark, monkeypatch):
    import urllib.error

    def _open(request, timeout=0):
        body = json.dumps({"ResponseMetadata": {"Error": {
            "Code": "InvalidAccessKeyId", "Message": "not exist"}}}).encode()
        raise urllib.error.HTTPError(
            request.full_url, 401, "Unauthorized", None, io.BytesIO(body))
    monkeypatch.setattr("urllib.request.urlopen", _open)
    result = ark.run({"ACCESS_KEY": "bad", "SECRET_KEY": "sk"})
    assert result["error"] == "InvalidAccessKeyId: not exist"
