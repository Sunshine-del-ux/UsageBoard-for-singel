#!/usr/bin/env python3
# UsageBoardPlugin:
# {
#   "schemaVersion": 1,
#   "name": "火山方舟",
#   "name@zh-Hans": "火山方舟",
#   "name@en": "Volcengine Ark",
#   "icon": "https://raw.githubusercontent.com/lobehub/lobe-icons/refs/heads/master/packages/static-png/light/volcengine.png",
#   "description": "查询火山方舟 Coding Plan 用量（需火山引擎 AK/SK）",
#   "description@zh-Hans": "查询火山方舟 Coding Plan 用量（需火山引擎 AK/SK）",
#   "description@en": "Query Volcengine Ark Coding Plan usage (requires Volcengine AK/SK)",
#   "parameters": [
#     {
#       "name": "ACCESS_KEY",
#       "label": "Access Key",
#       "label@zh-Hans": "Access Key",
#       "label@en": "Access Key",
#       "type": "secret",
#       "required": true,
#       "placeholder": "火山引擎 Access Key"
#     },
#     {
#       "name": "SECRET_KEY",
#       "label": "Secret Key",
#       "label@zh-Hans": "Secret Key",
#       "label@en": "Secret Key",
#       "type": "secret",
#       "required": true,
#       "placeholder": "火山引擎 Secret Key"
#     }
#   ]
# }
# /UsageBoardPlugin
"""UsageBoard plugin for Volcengine Ark Coding Plan quota usage.

配额数据来自火山引擎 OpenAPI GetCodingPlanUsage（服务 ark，版本 2024-01-01），
返回 5 小时 / 周 / 月三档配额的已用百分比与重置时间；
套餐等级（Lite/Pro）来自 GetPersonalPlan，用作卡片徽标。
两个接口都使用火山引擎 V4 签名（HMAC-SHA256，类 AWS SigV4），
只能用 IAM 的 AK/SK 调用，推理用的 sk- API Key 不支持查询配额。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from _common import (  # noqa: E402
    app_language,
    color_for_pct,
    failure_dict,
    http_error_dict,
    make_translator,
    numeric,
    parse_usageboard_params,
    status_for,
    success_dict,
    url_error_dict,
)

SERVICE = "ark"
REGION = "cn-beijing"
HOST = "open.volcengineapi.com"
API_VERSION = "2024-01-01"
CONTENT_TYPE = "application/json; charset=utf-8"
SIGNED_HEADERS = "content-type;host;x-content-sha256;x-date"

# GetCodingPlanUsage 返回的配额窗口级别（按展示顺序）
LEVEL_NAMES = {
    "session": {"zh-Hans": "5 小时用量", "en": "5-hour usage"},
    "weekly":  {"zh-Hans": "周用量",     "en": "Weekly usage"},
    "monthly": {"zh-Hans": "月用量",     "en": "Monthly usage"},
}

# Coding Plan 套餐等级 → 徽标颜色
PLAN_BADGE_COLOR = {
    "Lite": "gray",
    "Pro": "orange",
}

TRANSLATIONS = {
    "missing_ak_sk": {
        "zh-Hans": "请在插件设置中配置 Access Key 和 Secret Key",
        "en": "Configure Access Key and Secret Key in plugin settings",
    },
    "no_quota_items": {"zh-Hans": "未获取到配额数据", "en": "No quota data found."},
}


# ─── 火山引擎 V4 签名 ────────────────────────────────────────────────────────

def _hmac_sha256(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret_key: str, short_date: str) -> bytes:
    k_date = _hmac_sha256(secret_key.encode("utf-8"), short_date)
    k_region = _hmac_sha256(k_date, REGION)
    k_service = _hmac_sha256(k_region, SERVICE)
    return _hmac_sha256(k_service, "request")


def _canonical_query(params: dict[str, str]) -> str:
    return "&".join(
        f"{urllib.parse.quote(key, safe='-_.~')}={urllib.parse.quote(value, safe='-_.~')}"
        for key, value in sorted(params.items())
    )


def signed_request(action: str, access_key: str, secret_key: str,
                   body: str = "{}", now: datetime | None = None) -> urllib.request.Request:
    """构造带火山引擎 V4 签名的 POST 请求（算法见火山引擎开放API签名机制文档）。"""
    moment = now or datetime.now(timezone.utc)
    x_date = moment.strftime("%Y%m%dT%H%M%SZ")
    short_date = moment.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    query = _canonical_query({
        "Action": action,
        "Region": REGION,
        "Version": API_VERSION,
    })
    canonical_headers = (
        f"content-type:{CONTENT_TYPE}\n"
        f"host:{HOST}\n"
        f"x-content-sha256:{payload_hash}\n"
        f"x-date:{x_date}\n"
    )
    canonical_request = "\n".join([
        "POST", "/", query, canonical_headers, SIGNED_HEADERS, payload_hash,
    ])
    credential_scope = f"{short_date}/{REGION}/{SERVICE}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256", x_date, credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signature = hmac.new(
        _signing_key(secret_key, short_date),
        string_to_sign.encode("utf-8"), hashlib.sha256,
    ).hexdigest()
    authorization = (
        f"HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={SIGNED_HEADERS}, Signature={signature}"
    )
    return urllib.request.Request(
        f"https://{HOST}/?{query}",
        data=body.encode("utf-8"),
        headers={
            "Content-Type": CONTENT_TYPE,
            "X-Date": x_date,
            "X-Content-Sha256": payload_hash,
            "Authorization": authorization,
        },
        method="POST",
    )


def call_api(action: str, access_key: str, secret_key: str,
             body: str = "{}") -> dict[str, Any]:
    request = signed_request(action, access_key, secret_key, body)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


# ─── 响应解析 ────────────────────────────────────────────────────────────────

def api_error(payload: dict[str, Any]) -> str | None:
    """提取 OpenAPI 错误（ResponseMetadata.Error），无错误返回 None。"""
    metadata = payload.get("ResponseMetadata")
    if not isinstance(metadata, dict):
        return None
    error = metadata.get("Error")
    if not isinstance(error, dict) or not error.get("Code"):
        return None
    detail = f"{error.get('Code')}: {error.get('Message', '')}".strip()
    return detail[:200] + "…" if len(detail) > 200 else detail


def http_error_payload(error: urllib.error.HTTPError) -> dict[str, Any] | None:
    """HTTP 错误响应体里也常有 OpenAPI 错误结构（如签名/权限失败）。"""
    try:
        return json.loads(error.read().decode("utf-8"))
    except Exception:
        return None


def reset_iso(timestamp: Any) -> str | None:
    try:
        value = int(timestamp)
    except (TypeError, ValueError):
        return None
    if value <= 0:  # -1 表示无重置时间
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def build_items(payload: dict[str, Any], language: str) -> list[dict[str, Any]]:
    result = payload.get("Result")
    if not isinstance(result, dict):
        return []
    quota_usage = result.get("QuotaUsage")
    if not isinstance(quota_usage, list):
        return []

    items: list[dict[str, Any]] = []
    for level, names in LEVEL_NAMES.items():
        entry = next(
            (item for item in quota_usage
             if isinstance(item, dict) and item.get("Level") == level),
            None,
        )
        if entry is None:
            continue
        percent = max(0.0, min(100.0, numeric(entry.get("Percent"))))
        items.append({
            "id": f"ark-{level}",
            "name": names.get(language) or names["zh-Hans"],
            "used": percent,
            "limit": 100,
            "displayStyle": "percent",
            "resetAt": reset_iso(entry.get("ResetTimestamp")),
            "status": status_for(percent, 100),
            "color": color_for_pct(percent),
        })
    return items


def fetch_plan_badge(access_key: str, secret_key: str) -> str | None:
    """查询 Coding Plan 套餐等级作为徽标；失败时静默跳过（不影响用量展示）。"""
    try:
        payload = call_api("GetPersonalPlan", access_key, secret_key,
                           json.dumps({"Plan": "CodingPlan"}))
    except Exception:
        return None
    result = payload.get("Result")
    if not isinstance(result, dict):
        return None
    plan_type = result.get("PlanType")
    return str(plan_type) if plan_type else None


# ─── 入口 ────────────────────────────────────────────────────────────────────

def run(params: dict[str, str]) -> dict[str, Any]:
    language = app_language(params)
    translate = make_translator(TRANSLATIONS)

    access_key = params.get("ACCESS_KEY", "").strip()
    secret_key = params.get("SECRET_KEY", "").strip()
    if not access_key or not secret_key:
        return failure_dict(translate(language, "missing_ak_sk"))

    try:
        payload = call_api("GetCodingPlanUsage", access_key, secret_key)
    except urllib.error.HTTPError as error:
        detail = api_error(http_error_payload(error) or {})
        return failure_dict(detail) if detail \
            else http_error_dict(error, translate, language)
    except urllib.error.URLError as error:
        return url_error_dict(error, translate, language)
    except TimeoutError:
        return failure_dict(translate(language, "request_timeout"))
    except json.JSONDecodeError:
        return failure_dict(translate(language, "usage_parse_failed"))
    except Exception:
        return failure_dict(translate(language, "network_error"))

    error_text = api_error(payload)
    if error_text:
        return failure_dict(error_text)

    try:
        items = build_items(payload, language)
    except Exception:
        return failure_dict(translate(language, "usage_parse_failed"))
    if not items:
        return failure_dict(translate(language, "no_quota_items"))

    badge = fetch_plan_badge(access_key, secret_key)
    return success_dict(items, badge=badge,
                        badgeColor=PLAN_BADGE_COLOR.get(badge or ""))


def main() -> int:
    params = parse_usageboard_params(sys.argv[1:])
    print(json.dumps(run(params), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
