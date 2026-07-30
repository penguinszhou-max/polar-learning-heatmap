from __future__ import annotations

import json
import os
import random
import re
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
        "id": 1, "name": "基础语言与海洋结构", "short": "基础",
        "start_chapter": 1, "end_chapter": 5,
        "start": date(2026, 7, 29), "end": date(2026, 8, 25),
    },
    {
        "id": 2, "name": "旋转海洋与收支", "short": "动力",
        "start_chapter": 6, "end_chapter": 9,
        "start": date(2026, 8, 26), "end": date(2026, 9, 22),
    },
    {
        "id": 3, "name": "极地过程与区域整合", "short": "极地",
        "start_chapter": 10, "end_chapter": 13,
        "start": date(2026, 9, 23), "end": date(2026, 10, 20),
    },
    {
        "id": 4, "name": "气候动力与综合验收", "short": "验收",
        "start_chapter": 14, "end_chapter": 15,
        "start": date(2026, 10, 21), "end": date(2026, 11, 10),
    },
]

PASSED_STATUSES = {"已通过", "通过", "已掌握", "已完成", "完成"}
ACTIVE_STATUSES = {"学习中", "进行中"}
REVIEW_STATUSES = {"待验收", "待复测", "复测中"}
REPAIR_STATUSES = {"待修复", "需修复", "局部修复"}
KNOWN_STATUSES = PASSED_STATUSES | ACTIVE_STATUSES | REVIEW_STATUSES | REPAIR_STATUSES | {
    "未开始", "暂停", "延后"
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
            + "。请检查Repository secrets。"
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

        if response.status_code in {429, 500, 502, 503, 504} and attempt < max_attempts:
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 2 ** attempt
            except ValueError:
                delay = 2 ** attempt
            time.sleep(min(delay + random.random(), 12))
            continue

        detail = response.text[:1200]
        hints = {
            401: "请检查NOTION_TOKEN。",
            403: "内部连接缺少Read content权限。",
            404: "请确认01和02数据库都连接到同一个Notion内部连接，并检查Data Source ID。",
        }
        raise NotionError(
            f"Notion API请求失败：HTTP {response.status_code}。"
            f"{hints.get(response.status_code, '请查看Actions日志。')}\n{detail}"
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


def rich_text_to_plain(items: list[dict[str, Any]] | None) -> str:
    if not items:
        return ""
    return "".join(str(item.get("plain_text", "")) for item in items).strip()


def parse_date(prop: dict[str, Any]) -> date | None:
    obj = prop.get("date")
    start = obj.get("start") if obj else None
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

    try:
        return 0.0 if value is None else float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_text(prop: dict[str, Any]) -> str:
    t = prop.get("type")
    if t == "title":
        return rich_text_to_plain(prop.get("title"))
    if t == "rich_text":
        return rich_text_to_plain(prop.get("rich_text"))
    if t == "select":
        obj = prop.get("select")
        return str(obj.get("name", "")).strip() if obj else ""
    if t == "status":
        obj = prop.get("status")
        return str(obj.get("name", "")).strip() if obj else ""
    if t == "formula":
        obj = prop.get("formula") or {}
        if obj.get("type") == "string":
            return str(obj.get("string") or "").strip()
    return ""


def chapter_number(value: float) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def normalize_title(number: int, title: str) -> str:
    title = re.sub(r"\s+", " ", (title or "").strip())
    title = re.sub(rf"^第\s*{number}\s*章\s*[｜|:：\-—]*\s*", "", title)
    return f"第{number}章｜{title}" if title else f"第{number}章"


def short_title(number: int, title: str) -> str:
    full = normalize_title(number, title)
    return full.split("｜", 1)[-1]


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


def parse_chapters(pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chapters = []
    unknown_statuses = set()
    missing_expected_hours = []

    for page in pages:
        props = page.get("properties", {})
        number = chapter_number(parse_number(props.get(CHAPTER_NUMBER_PROPERTY, {})))
        raw_title = parse_text(props.get(CHAPTER_TITLE_PROPERTY, {}))
        status = parse_text(props.get(CHAPTER_STATUS_PROPERTY, {})) or "未开始"
        actual = round(parse_number(props.get(CHAPTER_ACTUAL_HOURS_PROPERTY, {})), 2)
        expected = round(parse_number(props.get(CHAPTER_EXPECTED_HOURS_PROPERTY, {})), 2)

        if status not in KNOWN_STATUSES:
            unknown_statuses.add(status)

        passed = status in PASSED_STATUSES
        active = status in ACTIVE_STATUSES
        review = status in REVIEW_STATUSES
        repair = status in REPAIR_STATUSES

        if expected <= 0 and not passed:
            missing_expected_hours.append(number)

        if passed:
            time_progress = 100.0
        elif expected > 0:
            time_progress = min(99.0, round(actual / expected * 100, 1))
        else:
            time_progress = 0.0

        chapters.append(
            {
                "number": number,
                "title": normalize_title(number, raw_title),
                "short_title": short_title(number, raw_title),
                "status": status,
                "current_unit": parse_text(props.get(CURRENT_UNIT_PROPERTY, {})),
                "next_action": parse_text(props.get(NEXT_ACTION_PROPERTY, {})),
                "actual_hours": actual,
                "expected_hours": expected,
                "time_progress_pct": time_progress,
                "passed": passed,
                "active": active,
                "review": review,
                "repair": repair,
                "url": page.get("url", ""),
            }
        )

    chapters = sorted(chapters, key=lambda item: item["number"])
    diagnostics = {
        "active_chapter_count": sum(1 for c in chapters if c["active"]),
        "unknown_statuses": sorted(unknown_statuses),
        "missing_expected_hours": sorted(n for n in missing_expected_hours if n > 0),
    }
    return chapters, diagnostics


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


def format_date_range(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{start.month}月{start.day}日—{end.day}日"
    return f"{start.month}月{start.day}日—{end.month}月{end.day}日"


def compact_date_range(start: date, end: date) -> str:
    return f"{start.month}.{start.day}–{end.month}.{end.day}"


def current_week(today: date) -> dict[str, Any]:
    for internal_id, start, end, target in WEEK_PLAN:
        if start <= today <= end:
            return {
                "internal_id": internal_id,
                "start": start,
                "end": end,
                "target_hours": target,
            }
    internal_id, start, end, target = (
        WEEK_PLAN[0] if today < COURSE_START else WEEK_PLAN[-1]
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
        elapsed = (day - start).days + 1
        total += target * elapsed / total_days
        break
    return round(total, 2)


def phase_for_chapter(number: int) -> dict[str, Any]:
    for phase in PHASES:
        if phase["start_chapter"] <= number <= phase["end_chapter"]:
            return phase
    return PHASES[0] if number <= 0 else PHASES[-1]


def choose_current_chapter(chapters: list[dict[str, Any]]) -> dict[str, Any] | None:
    for predicate in (
        lambda c: c["active"],
        lambda c: c["review"],
        lambda c: c["repair"],
        lambda c: not c["passed"],
    ):
        found = next((c for c in chapters if predicate(c)), None)
        if found:
            return found
    return chapters[-1] if chapters else None


def heatmap_payload(by_day: dict[date, dict[str, int]]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weekly_target_hours": 20,
        "days": [
            {
                "date": day.isoformat(),
                "minutes": values["minutes"],
                "record_count": values["record_count"],
                "level": intensity(values["minutes"]),
            }
            for day, values in sorted(by_day.items())
        ],
    }


def weekly_payload(by_day: dict[date, dict[str, int]]) -> dict[str, Any]:
    weeks = []
    for internal_id, start, end, target in WEEK_PLAN:
        minutes = sum(
            v["minutes"] for d, v in by_day.items() if start <= d <= end
        )
        actual = round(minutes / 60, 2)
        weeks.append(
            {
                "internal_id": internal_id,
                "label": compact_date_range(start, end),
                "date_label": format_date_range(start, end),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "target_hours": target,
                "actual_hours": actual,
                "completion_pct": round(actual / target * 100, 1) if target else 0,
            }
        )

    today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date()
    current = next(
        (
            w for w in weeks
            if date.fromisoformat(w["start"]) <= today <= date.fromisoformat(w["end"])
        ),
        None,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "redline_hours": 18,
        "minimum_hours": 20,
        "standard_hours": 22,
        "sprint_hours": 24,
        "total_actual_hours": round(sum(w["actual_hours"] for w in weeks), 2),
        "current_week": current,
        "weeks": weeks,
    }


def progress_payload(by_day: dict[date, dict[str, int]]) -> dict[str, Any]:
    today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date()
    display_end = min(max(today, COURSE_START), COURSE_END)

    actual_points = []
    cumulative = 0.0
    day = COURSE_START
    while day <= display_end:
        cumulative += by_day.get(day, {}).get("minutes", 0) / 60
        actual_points.append({"date": day.isoformat(), "hours": round(cumulative, 2)})
        day += timedelta(days=1)

    planned_points = [{"date": COURSE_START.isoformat(), "hours": 0.0}]
    plan_total = 0.0
    for _, _, end, target in WEEK_PLAN:
        plan_total += target
        planned_points.append({"date": end.isoformat(), "hours": round(plan_total, 2)})

    planned_to_date = planned_hours_on(display_end)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "course_start": COURSE_START.isoformat(),
        "course_end": COURSE_END.isoformat(),
        "today": display_end.isoformat(),
        "plan_total_hours": int(plan_total),
        "actual_total_hours": round(cumulative, 2),
        "planned_to_date_hours": planned_to_date,
        "gap_hours": round(cumulative - planned_to_date, 2),
        "completion_pct": round(cumulative / plan_total * 100, 1),
        "actual_points": actual_points,
        "planned_points": planned_points,
    }


def beacon_payload(
    by_day: dict[date, dict[str, int]],
    chapters: list[dict[str, Any]],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date()
    week = current_week(today)
    current = choose_current_chapter(chapters)

    today_data = by_day.get(today, {"minutes": 0, "record_count": 0})
    week_minutes = sum(
        v["minutes"] for d, v in by_day.items()
        if week["start"] <= d <= week["end"]
    )
    week_hours = round(week_minutes / 60, 2)
    total_hours = round(sum(v["minutes"] for v in by_day.values()) / 60, 2)
    total_plan = int(sum(w[3] for w in WEEK_PLAN))
    planned_to_date = planned_hours_on(today)
    overall_pct = round(total_hours / total_plan * 100, 1)
    passed = sum(1 for c in chapters if c["passed"])

    current_phase = phase_for_chapter(current["number"] if current else 1)
    phases = []
    for phase in PHASES:
        items = [
            c for c in chapters
            if phase["start_chapter"] <= c["number"] <= phase["end_chapter"]
        ]
        completed = sum(1 for c in items if c["passed"])
        phases.append(
            {
                "id": phase["id"],
                "name": phase["name"],
                "short": phase["short"],
                "start_chapter": phase["start_chapter"],
                "end_chapter": phase["end_chapter"],
                "completed_chapters": completed,
                "total_chapters": len(items),
                "complete": bool(items) and completed == len(items),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": {
            "date": today.isoformat(),
            "minutes": today_data["minutes"],
            "record_count": today_data["record_count"],
            "has_learning": today_data["minutes"] > 0,
        },
        "week": {
            "label": format_date_range(week["start"], week["end"]),
            "actual_hours": week_hours,
            "target_hours": week["target_hours"],
            "completion_pct": round(week_hours / week["target_hours"] * 100, 1),
            "remaining_hours": round(max(0, week["target_hours"] - week_hours), 2),
        },
        "overall": {
            "actual_hours": total_hours,
            "plan_total_hours": total_plan,
            "completion_pct": overall_pct,
            "visual_progress_pct": max(1.5, overall_pct) if overall_pct > 0 else 0,
            "planned_to_date_hours": planned_to_date,
            "gap_hours": round(total_hours - planned_to_date, 2),
            "passed_chapters": passed,
            "total_chapters": len(chapters),
        },
        "context": current,
        "current_phase": {
            "id": current_phase["id"],
            "name": current_phase["name"],
            "short": current_phase["short"],
            "milestone": (
                f"完成第{current_phase['start_chapter']}—"
                f"{current_phase['end_chapter']}章"
            ),
        },
        "phases": phases,
        "diagnostics": diagnostics,
    }


def phase_voyage_payload(
    chapters: list[dict[str, Any]],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    current = choose_current_chapter(chapters)
    current_number = current["number"] if current else 1
    phase = phase_for_chapter(current_number)
    phase_chapters = [
        c for c in chapters
        if phase["start_chapter"] <= c["number"] <= phase["end_chapter"]
    ]

    completed = sum(1 for c in phase_chapters if c["passed"])
    total = len(phase_chapters)

    active_index = 0
    active_fraction = 0.0
    if current:
        for idx, item in enumerate(phase_chapters):
            if item["number"] == current["number"]:
                active_index = idx
                active_fraction = item["time_progress_pct"] / 100
                break
    if total:
        route_progress = (
            100.0 if completed >= total
            else round((active_index + active_fraction) / total * 100, 1)
        )
    else:
        route_progress = 0.0

    next_chapter = next(
        (c for c in phase_chapters if current and c["number"] > current["number"] and not c["passed"]),
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
            "passed_chapters": completed,
            "total_chapters": total,
            "acceptance_pct": round(completed / total * 100, 1) if total else 0,
            "route_progress_pct": route_progress,
            "complete": bool(total) and completed == total,
        },
        "current_chapter": current,
        "next_chapter": next_chapter,
        "chapters": phase_chapters,
        "diagnostics": diagnostics,
    }


def write_json(name: str, data: dict[str, Any]) -> None:
    (PUBLIC_DIR / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    validate_environment()
    records = query_learning_records()
    pages = query_chapters()
    by_day = aggregate_daily(records)
    chapters, diagnostics = parse_chapters(pages)

    write_json("data.json", heatmap_payload(by_day))
    write_json("weekly-data.json", weekly_payload(by_day))
    write_json("progress-data.json", progress_payload(by_day))
    write_json("polar-progress-data.json", beacon_payload(by_day, chapters, diagnostics))
    write_json("phase-voyage-data.json", phase_voyage_payload(chapters, diagnostics))
    (PUBLIC_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(
        f"统一构建完成：{len(records)}条正式记录，"
        f"{len(chapters)}章，{len(by_day)}个学习日。"
    )
    print(
        "已生成：data.json、weekly-data.json、progress-data.json、"
        "polar-progress-data.json、phase-voyage-data.json"
    )
    if diagnostics["active_chapter_count"] != 1:
        print(
            "诊断提示：学习中章节数量为"
            f"{diagnostics['active_chapter_count']}，建议保持恰好1章。"
        )
    if diagnostics["unknown_statuses"]:
        print("诊断提示：未知章节状态：", diagnostics["unknown_statuses"])
    if diagnostics["missing_expected_hours"]:
        print("诊断提示：缺少预计小时的章节：", diagnostics["missing_expected_hours"])


if __name__ == "__main__":
    main()
