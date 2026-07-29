from __future__ import annotations

import json
import os
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"

TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
DATA_SOURCE_ID = os.environ.get("LEARNING_RECORDS_DATA_SOURCE_ID", "").strip()
WEEKLY_TARGET_HOURS = float(os.environ.get("WEEKLY_TARGET_HOURS", "20"))

DATE_PROPERTY = os.environ.get("DATE_PROPERTY", "日期")
MINUTES_PROPERTY = os.environ.get("MINUTES_PROPERTY", "实际分钟")
COUNT_PROPERTY = os.environ.get("COUNT_PROPERTY", "是否计入正式时长")

PUBLIC_DIR = Path("public")
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)


class NotionError(RuntimeError):
    pass


def validate_environment() -> None:
    missing = []
    if not TOKEN:
        missing.append("NOTION_TOKEN")
    if not DATA_SOURCE_ID:
        missing.append("LEARNING_RECORDS_DATA_SOURCE_ID")
    if missing:
        raise SystemExit(
            "缺少GitHub Secret："
            + ", ".join(missing)
            + "。请按README配置后重新运行工作流。"
        )


def notion_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 5,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.request(
                method,
                f"{NOTION_API_BASE}{path}",
                headers=headers,
                json=payload,
                timeout=45,
            )
        except requests.RequestException as exc:
            if attempt == max_attempts:
                raise NotionError(f"Notion网络请求失败：{exc}") from exc
            time.sleep(min(2 ** attempt + random.random(), 12))
            continue

        if response.ok:
            return response.json()

        retryable = response.status_code in {429, 500, 502, 503, 504}
        if retryable and attempt < max_attempts:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 2 ** attempt
            else:
                delay = min(2 ** attempt + random.random(), 12)
            time.sleep(delay)
            continue

        detail = response.text[:1000]
        if response.status_code == 401:
            hint = "请检查GitHub Secret NOTION_TOKEN。"
        elif response.status_code == 403:
            hint = "内部连接缺少Read content权限。"
        elif response.status_code == 404:
            hint = (
                "请确认Data Source ID正确，并在“02｜学习记录”右上角"
                "“••• → 连接”中添加该内部连接。"
            )
        else:
            hint = "请查看GitHub Actions日志中的Notion错误信息。"

        raise NotionError(
            f"Notion API请求失败：HTTP {response.status_code}。{hint}\n{detail}"
        )

    raise NotionError("Notion API请求失败，已达到最大重试次数。")


def query_learning_records() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        payload: dict[str, Any] = {
            "page_size": 100,
            "filter": {
                "property": COUNT_PROPERTY,
                "checkbox": {"equals": True},
            },
            "sorts": [
                {
                    "property": DATE_PROPERTY,
                    "direction": "ascending",
                }
            ],
        }
        if cursor:
            payload["start_cursor"] = cursor

        data = notion_request(
            "POST",
            f"/data_sources/{DATA_SOURCE_ID}/query",
            payload=payload,
        )
        results.extend(data.get("results", []))

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor:
            break

    return results


def parse_date(prop: dict[str, Any]) -> str | None:
    date_obj = prop.get("date")
    if not date_obj:
        return None
    start = date_obj.get("start")
    if not start:
        return None
    return str(start)[:10]


def parse_number(prop: dict[str, Any]) -> float:
    value = prop.get("number")
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def intensity(minutes: int) -> int:
    if minutes <= 0:
        return 0
    if minutes < 45:
        return 1
    if minutes < 90:
        return 2
    if minutes < 150:
        return 3
    if minutes < 210:
        return 4
    if minutes < 270:
        return 5
    return 6


def aggregate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, int]] = defaultdict(
        lambda: {"minutes": 0, "record_count": 0}
    )

    skipped_missing_date = 0
    skipped_nonpositive = 0

    for page in records:
        props = page.get("properties", {})
        day = parse_date(props.get(DATE_PROPERTY, {}))
        minutes = int(round(parse_number(props.get(MINUTES_PROPERTY, {}))))

        if not day:
            skipped_missing_date += 1
            continue
        if minutes <= 0:
            skipped_nonpositive += 1
            continue

        by_day[day]["minutes"] += minutes
        by_day[day]["record_count"] += 1

    days = []
    for day in sorted(by_day):
        minutes = by_day[day]["minutes"]
        days.append(
            {
                "date": day,
                "minutes": minutes,
                "record_count": by_day[day]["record_count"],
                "level": intensity(minutes),
            }
        )

    if skipped_missing_date:
        print(f"跳过 {skipped_missing_date} 条缺少日期的记录。")
    if skipped_nonpositive:
        print(f"跳过 {skipped_nonpositive} 条分钟数不大于0的记录。")

    return days


def write_output(days: list[dict[str, Any]]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weekly_target_hours": WEEKLY_TARGET_HOURS,
        "days": days,
    }
    (PUBLIC_DIR / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (PUBLIC_DIR / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    validate_environment()
    records = query_learning_records()
    days = aggregate(records)
    write_output(days)

    total_minutes = sum(day["minutes"] for day in days)
    print(
        f"构建完成：{len(records)} 条正式记录，"
        f"{len(days)} 个学习日，累计 {total_minutes} 分钟。"
    )


if __name__ == "__main__":
    main()
