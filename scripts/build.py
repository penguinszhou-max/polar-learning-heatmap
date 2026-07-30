from __future__ import annotations

import json
import os
import random
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = os.environ.get("NOTION_VERSION", "2025-09-03")

TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
LEARNING_RECORDS_DATA_SOURCE_ID = os.environ.get(
    "LEARNING_RECORDS_DATA_SOURCE_ID", ""
).strip()
CHAPTERS_DATA_SOURCE_ID = os.environ.get(
    "CHAPTERS_DATA_SOURCE_ID", ""
).strip()
TIMEZONE_NAME = os.environ.get("TIMEZONE", "Asia/Shanghai")

DATE_PROPERTY = os.environ.get("DATE_PROPERTY", "日期")
MINUTES_PROPERTY = os.environ.get("MINUTES_PROPERTY", "实际分钟")
COUNT_PROPERTY = os.environ.get("COUNT_PROPERTY", "是否计入正式时长")

CHAPTER_TITLE_PROPERTY = os.environ.get("CHAPTER_TITLE_PROPERTY", "章节")
CHAPTER_STATUS_PROPERTY = os.environ.get("CHAPTER_STATUS_PROPERTY", "状态")
CHAPTER_NUMBER_PROPERTY = os.environ.get("CHAPTER_NUMBER_PROPERTY", "章节编号")
CURRENT_UNIT_PROPERTY = os.environ.get("CURRENT_UNIT_PROPERTY", "当前学习单元")
NEXT_ACTION_PROPERTY = os.environ.get("NEXT_ACTION_PROPERTY", "下一动作")
CHAPTER_ACTUAL_HOURS_PROPERTY = os.environ.get(
    "CHAPTER_ACTUAL_HOURS_PROPERTY", "实际学习小时"
)
CHAPTER_EXPECTED_HOURS_PROPERTY = os.environ.get(
    "CHAPTER_EXPECTED_HOURS_PROPERTY", "预计小时"
)

PUBLIC_DIR = Path("public")
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

COURSE_START = date(2026, 7, 29)
COURSE_END = date(2026, 11, 10)

WEEK_PLAN = [
    ("W1",  date(2026, 7, 29), date(2026, 8, 4),  20),
    ("W2",  date(2026, 8, 5),  date(2026, 8, 11), 20),
    ("W3",  date(2026, 8, 12), date(2026, 8, 18), 20),
    ("W4",  date(2026, 8, 19), date(2026, 8, 25), 21),
    ("W5",  date(2026, 8, 26), date(2026, 9, 1),  21),
    ("W6",  date(2026, 9, 2),  date(2026, 9, 8),  23),
    ("W7",  date(2026, 9, 9),  date(2026, 9, 15), 21),
    ("W8",  date(2026, 9, 16), date(2026, 9, 22), 20),
    ("W9",  date(2026, 9, 23), date(2026, 9, 29), 22),
    ("W10", date(2026, 9, 30), date(2026, 10, 6), 24),
    ("W11", date(2026, 10, 7), date(2026, 10, 13), 24),
    ("W12", date(2026, 10, 14), date(2026, 10, 20), 24),
    ("W13", date(2026, 10, 21), date(2026, 10, 27), 22),
    ("W14", date(2026, 10, 28), date(2026, 11, 3), 22),
    ("W15", date(2026, 11, 4), date(2026, 11, 10), 22),
]

PHASES = [
    {
        "id": 1,
        "name": "基础语言与海洋结构",
        "short": "基础",
        "start_chapter": 1,
        "end_chapter": 5,
        "start": date(2026, 7, 29),
        "end": date(2026, 8, 25),
    },
    {
        "id": 2,
        "name": "旋转海洋与收支",
        "short": "动力",
        "start_chapter": 6,
        "end_chapter": 9,
        "start": date(2026, 8, 26),
        "end": date(2026, 9, 22),
    },
    {
        "id": 3,
        "name": "极地过程与区域整合",
        "short": "极地",
        "start_chapter": 10,
        "end_chapter": 13,
        "start": date(2026, 9, 23),
        "end": date(2026, 10, 20),
    },
    {
        "id": 4,
        "name": "气候动力与综合验收",
        "short": "验收",
        "start_chapter": 14,
        "end_chapter": 15,
        "start": date(2026, 10, 21),
        "end": date(2026, 11, 10),
    },
]

PASSED_STATUSES = {
    "已通过",
    "已掌握",
    "完成",
    "已完成",
    "通过",
}
ACTIVE_STATUSES = {
    "学习中",
    "进行中",
    "待验收",
    "待复习",
    "待修复",
}


class NotionError(RuntimeError):
    pass


def validate_environment() -> None:
    missing = []
    if not TOKEN:
        missing.append("NOTION_TOKEN")
    if not LEARNING_RECORDS_DATA_SOURCE_ID:
        missing.append("LEARNING_RECORDS_DATA_SOURCE_ID")
    if not CHAPTERS_DATA_SOURCE_ID:
        missing.append("CHAPTERS_DATA_SOURCE_ID")
    if missing:
        raise SystemExit(
            "缺少GitHub Secret：" + ", ".join(missing)
            + "。请检查仓库Actions Secrets。"
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
            try:
                delay = float(retry_after) if retry_after else 2 ** attempt
            except ValueError:
                delay = 2 ** attempt
            time.sleep(min(delay + random.random(), 12))
            continue

        detail = response.text[:1200]
        if response.status_code == 401:
            hint = "请检查NOTION_TOKEN。"
        elif response.status_code == 403:
            hint = "内部连接缺少Read content权限。"
        elif response.status_code == 404:
            hint = "请确认01和02数据库均已连接到同一个Notion内部连接。"
        else:
            hint = "请查看GitHub Actions日志。"

        raise NotionError(
            f"Notion API请求失败：HTTP {response.status_code}。{hint}\n{detail}"
        )

    raise NotionError("Notion API请求失败，达到最大重试次数。")


def query_data_source(
    data_source_id: str,
    *,
    filter_obj: dict[str, Any] | None = None,
    sorts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        payload: dict[str, Any] = {"page_size": 100}
        if filter_obj:
            payload["filter"] = filter_obj
        if sorts:
            payload["sorts"] = sorts
        if cursor:
            payload["start_cursor"] = cursor

        data = notion_request(
            "POST",
            f"/data_sources/{data_source_id}/query",
            payload=payload,
        )
        results.extend(data.get("results", []))

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor:
            break

    return results


def query_learning_records() -> list[dict[str, Any]]:
    return query_data_source(
        LEARNING_RECORDS_DATA_SOURCE_ID,
        filter_obj={
            "property": COUNT_PROPERTY,
            "checkbox": {"equals": True},
        },
        sorts=[{"property": DATE_PROPERTY, "direction": "ascending"}],
    )


def query_chapters() -> list[dict[str, Any]]:
    return query_data_source(
        CHAPTERS_DATA_SOURCE_ID,
        sorts=[{"property": CHAPTER_NUMBER_PROPERTY, "direction": "ascending"}],
    )


def rich_text_to_plain(items: list[dict[str, Any]] | None) -> str:
    if not items:
        return ""
    return "".join(str(item.get("plain_text", "")) for item in items).strip()


def parse_date(prop: dict[str, Any]) -> date | None:
    date_obj = prop.get("date")
    if not date_obj:
        return None
    start = date_obj.get("start")
    if not start:
        return None
    try:
        return date.fromisoformat(str(start)[:10])
    except ValueError:
        return None


def parse_number(prop: dict[str, Any]) -> float:
    prop_type = prop.get("type")
    if prop_type == "number":
        value = prop.get("number")
    elif prop_type == "formula":
        value = (prop.get("formula") or {}).get("number")
    elif prop_type == "rollup":
        value = (prop.get("rollup") or {}).get("number")
    else:
        value = prop.get("number")

    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_text(prop: dict[str, Any]) -> str:
    prop_type = prop.get("type")
    if prop_type == "title":
        return rich_text_to_plain(prop.get("title"))
    if prop_type == "rich_text":
        return rich_text_to_plain(prop.get("rich_text"))
    if prop_type == "select":
        selected = prop.get("select")
        return str(selected.get("name", "")).strip() if selected else ""
    if prop_type == "status":
        selected = prop.get("status")
        return str(selected.get("name", "")).strip() if selected else ""
    if prop_type == "formula":
        formula = prop.get("formula") or {}
        if formula.get("type") == "string":
            return str(formula.get("string") or "").strip()
    return ""


def chapter_number(raw: float) -> int:
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return 0


def aggregate_daily(records: list[dict[str, Any]]) -> dict[date, dict[str, int]]:
    by_day: dict[date, dict[str, int]] = defaultdict(
        lambda: {"minutes": 0, "record_count": 0}
    )
    for page in records:
        props = page.get("properties", {})
        day = parse_date(props.get(DATE_PROPERTY, {}))
        minutes = int(round(parse_number(props.get(MINUTES_PROPERTY, {}))))
        if day and minutes > 0:
            by_day[day]["minutes"] += minutes
            by_day[day]["record_count"] += 1
    return by_day


def parse_chapters(chapter_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chapters = []
    for page in chapter_pages:
        props = page.get("properties", {})
        status = parse_text(props.get(CHAPTER_STATUS_PROPERTY, {}))
        actual = round(
            parse_number(props.get(CHAPTER_ACTUAL_HOURS_PROPERTY, {})), 2
        )
        expected = round(
            parse_number(props.get(CHAPTER_EXPECTED_HOURS_PROPERTY, {})), 2
        )
        if status in PASSED_STATUSES:
            progress = 100.0
        elif expected > 0:
            progress = min(99.0, round(actual / expected * 100, 1))
        else:
            progress = 0.0

        chapters.append(
            {
                "number": chapter_number(
                    parse_number(props.get(CHAPTER_NUMBER_PROPERTY, {}))
                ),
                "title": parse_text(props.get(CHAPTER_TITLE_PROPERTY, {})),
                "status": status or "未开始",
                "current_unit": parse_text(
                    props.get(CURRENT_UNIT_PROPERTY, {})
                ),
                "next_action": parse_text(
                    props.get(NEXT_ACTION_PROPERTY, {})
                ),
                "actual_hours": actual,
                "expected_hours": expected,
                "progress_pct": progress,
                "url": page.get("url", ""),
                "passed": status in PASSED_STATUSES,
                "active": status in ACTIVE_STATUSES,
            }
        )
    return sorted(chapters, key=lambda item: item["number"])


def current_week(local_today: date) -> dict[str, Any]:
    for internal_id, start, end, target in WEEK_PLAN:
        if start <= local_today <= end:
            return {
                "internal_id": internal_id,
                "start": start,
                "end": end,
                "target_hours": target,
            }
    internal_id, start, end, target = (
        WEEK_PLAN[0] if local_today < COURSE_START else WEEK_PLAN[-1]
    )
    return {
        "internal_id": internal_id,
        "start": start,
        "end": end,
        "target_hours": target,
    }


def planned_hours_on(day: date) -> float:
    if day < COURSE_START:
        return 0.0
    if day >= COURSE_END:
        return float(sum(item[3] for item in WEEK_PLAN))
    total = 0.0
    for _, start, end, target in WEEK_PLAN:
        if day > end:
            total += target
            continue
        if day < start:
            break
        total_days = (end - start).days + 1
        elapsed_days = (day - start).days + 1
        total += target * elapsed_days / total_days
        break
    return round(total, 2)


def phase_for_chapter(number: int) -> dict[str, Any]:
    for phase in PHASES:
        if phase["start_chapter"] <= number <= phase["end_chapter"]:
            return phase
    return PHASES[0] if number <= 0 else PHASES[-1]


def format_date_range(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{start.month}月{start.day}日—{end.day}日"
    return f"{start.month}月{start.day}日—{end.month}月{end.day}日"



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


def heatmap_payload(by_day: dict[date, dict[str, int]]) -> dict[str, Any]:
    days = []
    for day in sorted(by_day):
        minutes = by_day[day]["minutes"]
        days.append(
            {
                "date": day.isoformat(),
                "minutes": minutes,
                "record_count": by_day[day]["record_count"],
                "level": intensity(minutes),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weekly_target_hours": 20,
        "days": days,
    }


def compact_range(start: date, end: date) -> str:
    return f"{start.month}.{start.day}–{end.month}.{end.day}"


def weekly_payload(by_day: dict[date, dict[str, int]]) -> dict[str, Any]:
    local_today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date()
    weeks = []
    total_actual = 0.0
    current = None
    for internal_id, start, end, target in WEEK_PLAN:
        actual_minutes = sum(
            values["minutes"]
            for day, values in by_day.items()
            if start <= day <= end
        )
        actual_hours = round(actual_minutes / 60, 2)
        total_actual += actual_hours
        item = {
            "internal_id": internal_id,
            "label": compact_range(start, end),
            "date_label": format_date_range(start, end),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "target_hours": target,
            "actual_hours": actual_hours,
            "completion_pct": round(actual_hours / target * 100, 1) if target else 0,
        }
        weeks.append(item)
        if start <= local_today <= end:
            current = item
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "redline_hours": 18,
        "minimum_hours": 20,
        "standard_hours": 22,
        "sprint_hours": 24,
        "total_actual_hours": round(total_actual, 2),
        "current_week": current,
        "weeks": weeks,
    }


def cumulative_progress_payload(by_day: dict[date, dict[str, int]]) -> dict[str, Any]:
    local_today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date()
    display_end = min(max(local_today, COURSE_START), COURSE_END)

    actual_points = []
    cumulative_actual = 0.0
    day = COURSE_START
    while day <= display_end:
        cumulative_actual += by_day.get(day, {}).get("minutes", 0) / 60
        actual_points.append({"date": day.isoformat(), "hours": round(cumulative_actual, 2)})
        day += timedelta(days=1)

    planned_points = [{"date": COURSE_START.isoformat(), "hours": 0.0}]
    cumulative_plan = 0.0
    for _, _, end, target in WEEK_PLAN:
        cumulative_plan += target
        planned_points.append({"date": end.isoformat(), "hours": round(cumulative_plan, 2)})

    planned_to_date = planned_hours_on(display_end)
    total_plan = sum(item[3] for item in WEEK_PLAN)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "course_start": COURSE_START.isoformat(),
        "course_end": COURSE_END.isoformat(),
        "today": display_end.isoformat(),
        "plan_total_hours": total_plan,
        "actual_total_hours": round(cumulative_actual, 2),
        "planned_to_date_hours": planned_to_date,
        "gap_hours": round(cumulative_actual - planned_to_date, 2),
        "completion_pct": round(cumulative_actual / total_plan * 100, 1) if total_plan else 0,
        "actual_points": actual_points,
        "planned_points": planned_points,
    }


def global_payload(
    by_day: dict[date, dict[str, int]],
    chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    local_today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date()
    week = current_week(local_today)
    today_minutes = by_day.get(local_today, {}).get("minutes", 0)
    today_records = by_day.get(local_today, {}).get("record_count", 0)

    week_minutes = sum(
        values["minutes"]
        for day, values in by_day.items()
        if week["start"] <= day <= week["end"]
    )
    week_hours = round(week_minutes / 60, 2)
    total_hours = round(
        sum(values["minutes"] for values in by_day.values()) / 60,
        2,
    )
    total_plan = sum(item[3] for item in WEEK_PLAN)
    overall_pct = round(total_hours / total_plan * 100, 1)
    planned_to_date = planned_hours_on(local_today)
    gap = round(total_hours - planned_to_date, 2)
    passed = sum(1 for item in chapters if item["passed"])

    phase_items = []
    for phase in PHASES:
        phase_chapters = [
            item for item in chapters
            if phase["start_chapter"] <= item["number"] <= phase["end_chapter"]
        ]
        completed = sum(1 for item in phase_chapters if item["passed"])
        phase_items.append(
            {
                "id": phase["id"],
                "name": phase["name"],
                "short": phase["short"],
                "start": phase["start"].isoformat(),
                "end": phase["end"].isoformat(),
                "completed_chapters": completed,
                "total_chapters": len(phase_chapters),
                "complete": bool(phase_chapters) and completed == len(phase_chapters),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": {
            "date": local_today.isoformat(),
            "minutes": today_minutes,
            "record_count": today_records,
            "has_learning": today_minutes > 0,
        },
        "week": {
            "label": format_date_range(week["start"], week["end"]),
            "actual_hours": week_hours,
            "target_hours": week["target_hours"],
            "completion_pct": round(
                week_hours / week["target_hours"] * 100, 1
            ),
            "remaining_hours": round(
                max(0, week["target_hours"] - week_hours), 2
            ),
        },
        "overall": {
            "actual_hours": total_hours,
            "plan_total_hours": total_plan,
            "completion_pct": overall_pct,
            "planned_to_date_hours": planned_to_date,
            "gap_hours": gap,
            "passed_chapters": passed,
            "total_chapters": len(chapters),
        },
        "phases": phase_items,
    }


def phase_payload(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    active = next((item for item in chapters if item["active"]), None)
    if active is None:
        active = next((item for item in chapters if not item["passed"]), None)
    if active is None and chapters:
        active = chapters[-1]

    active_number = active["number"] if active else 1
    phase = phase_for_chapter(active_number)
    phase_chapters = [
        item for item in chapters
        if phase["start_chapter"] <= item["number"] <= phase["end_chapter"]
    ]

    if not phase_chapters:
        phase_chapters = [
            {
                "number": n,
                "title": f"第{n}章",
                "status": "未开始",
                "current_unit": "",
                "next_action": "",
                "actual_hours": 0,
                "expected_hours": 0,
                "progress_pct": 0,
                "url": "",
                "passed": False,
                "active": n == active_number,
            }
            for n in range(phase["start_chapter"], phase["end_chapter"] + 1)
        ]

    completed = sum(1 for item in phase_chapters if item["passed"])
    total = len(phase_chapters)

    active_index = 0
    active_progress = 0.0
    for idx, item in enumerate(phase_chapters):
        if item["number"] == active_number:
            active_index = idx
            active_progress = item["progress_pct"]
            break
    else:
        if completed >= total:
            active_index = total
            active_progress = 100.0
        else:
            active_index = min(completed, max(0, total - 1))

    route_progress = (
        100.0 if completed >= total
        else round((active_index + active_progress / 100) / total * 100, 1)
    )

    next_chapter = next(
        (
            item for item in phase_chapters
            if item["number"] > active_number and not item["passed"]
        ),
        None,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": {
            "id": phase["id"],
            "name": phase["name"],
            "short": phase["short"],
            "start_chapter": phase["start_chapter"],
            "end_chapter": phase["end_chapter"],
            "date_label": format_date_range(phase["start"], phase["end"]),
            "completed_chapters": completed,
            "total_chapters": total,
            "completion_pct": round(completed / total * 100, 1) if total else 0,
            "route_progress_pct": route_progress,
            "complete": completed >= total and total > 0,
        },
        "current_chapter": active,
        "next_chapter": next_chapter,
        "chapters": phase_chapters,
    }


def write_json(filename: str, payload: dict[str, Any]) -> None:
    (PUBLIC_DIR / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    validate_environment()
    records = query_learning_records()
    chapter_pages = query_chapters()
    by_day = aggregate_daily(records)
    chapters = parse_chapters(chapter_pages)

    write_json("data.json", heatmap_payload(by_day))
    write_json("weekly-data.json", weekly_payload(by_day))
    write_json("progress-data.json", cumulative_progress_payload(by_day))
    write_json("polar-progress-data.json", global_payload(by_day, chapters))
    write_json("phase-voyage-data.json", phase_payload(chapters))
    (PUBLIC_DIR / ".nojekyll").write_text("", encoding="utf-8")

    # Existing data files are left to the current builder if present.
    print(
        f"航标数据构建完成：{len(records)}条正式记录，"
        f"{len(chapters)}章，{len(by_day)}个学习日。"
    )
    print(
        "已生成：data.json、weekly-data.json、progress-data.json、"
        "polar-progress-data.json、phase-voyage-data.json"
    )


if __name__ == "__main__":
    main()
