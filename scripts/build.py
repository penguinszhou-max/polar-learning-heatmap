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
LEARNING_RECORDS_DATA_SOURCE_ID = os.environ.get("LEARNING_RECORDS_DATA_SOURCE_ID", "").strip()
CHAPTERS_DATA_SOURCE_ID = os.environ.get("CHAPTERS_DATA_SOURCE_ID", "").strip()
TIMEZONE_NAME = os.environ.get("TIMEZONE", "Asia/Shanghai")

DATE_PROPERTY = os.environ.get("DATE_PROPERTY", "日期")
MINUTES_PROPERTY = os.environ.get("MINUTES_PROPERTY", "实际分钟")
COUNT_PROPERTY = os.environ.get("COUNT_PROPERTY", "是否计入正式时长")

CHAPTER_TITLE_PROPERTY = os.environ.get("CHAPTER_TITLE_PROPERTY", "章节")
CHAPTER_STATUS_PROPERTY = os.environ.get("CHAPTER_STATUS_PROPERTY", "状态")
CHAPTER_NUMBER_PROPERTY = os.environ.get("CHAPTER_NUMBER_PROPERTY", "章节编号")
CURRENT_UNIT_PROPERTY = os.environ.get("CURRENT_UNIT_PROPERTY", "当前学习单元")
NEXT_ACTION_PROPERTY = os.environ.get("NEXT_ACTION_PROPERTY", "下一动作")
CHAPTER_ACTUAL_HOURS_PROPERTY = os.environ.get("CHAPTER_ACTUAL_HOURS_PROPERTY", "实际学习小时")
CHAPTER_EXPECTED_HOURS_PROPERTY = os.environ.get("CHAPTER_EXPECTED_HOURS_PROPERTY", "预计小时")

PUBLIC_DIR = Path("public")
PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

COURSE_START = date(2026, 7, 29)
COURSE_END = date(2026, 11, 10)

WEEK_PLAN = [
    ("7月29日—8月4日", date(2026, 7, 29), date(2026, 8, 4), 20),
    ("8月5日—8月11日", date(2026, 8, 5), date(2026, 8, 11), 20),
    ("8月12日—8月18日", date(2026, 8, 12), date(2026, 8, 18), 20),
    ("8月19日—8月25日", date(2026, 8, 19), date(2026, 8, 25), 21),
    ("8月26日—9月1日", date(2026, 8, 26), date(2026, 9, 1), 21),
    ("9月2日—9月8日", date(2026, 9, 2), date(2026, 9, 8), 23),
    ("9月9日—9月15日", date(2026, 9, 9), date(2026, 9, 15), 21),
    ("9月16日—9月22日", date(2026, 9, 16), date(2026, 9, 22), 20),
    ("9月23日—9月29日", date(2026, 9, 23), date(2026, 9, 29), 22),
    ("9月30日—10月6日", date(2026, 9, 30), date(2026, 10, 6), 24),
    ("10月7日—10月13日", date(2026, 10, 7), date(2026, 10, 13), 24),
    ("10月14日—10月20日", date(2026, 10, 14), date(2026, 10, 20), 24),
    ("10月21日—10月27日", date(2026, 10, 21), date(2026, 10, 27), 22),
    ("10月28日—11月3日", date(2026, 10, 28), date(2026, 11, 3), 22),
    ("11月4日—11月10日", date(2026, 11, 4), date(2026, 11, 10), 22),
]

PHASES = [
    {"id": 1, "name": "基础语言与海洋结构", "start": 1, "end": 5, "milestone": "基础"},
    {"id": 2, "name": "旋转海洋与收支", "start": 6, "end": 9, "milestone": "动力"},
    {"id": 3, "name": "极地过程与区域整合", "start": 10, "end": 13, "milestone": "极地"},
    {"id": 4, "name": "气候动力与综合验收", "start": 14, "end": 15, "milestone": "验收"},
]


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
        raise SystemExit("缺少GitHub Secret：" + ", ".join(missing))


def notion_request(method: str, path: str, *, payload: dict[str, Any] | None = None, max_attempts: int = 5) -> dict[str, Any]:
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
            time.sleep(min(2 ** attempt + random.random(), 12))
            continue

        raise NotionError(
            f"Notion API请求失败：HTTP {response.status_code}。\n{response.text[:1200]}"
        )
    raise NotionError("Notion API请求失败。")


def query_data_source(data_source_id: str, *, filter_obj=None, sorts=None) -> list[dict[str, Any]]:
    results = []
    cursor = None
    while True:
        payload: dict[str, Any] = {"page_size": 100}
        if filter_obj:
            payload["filter"] = filter_obj
        if sorts:
            payload["sorts"] = sorts
        if cursor:
            payload["start_cursor"] = cursor
        data = notion_request("POST", f"/data_sources/{data_source_id}/query", payload=payload)
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        if not cursor:
            break
    return results


def rich_text_to_plain(items):
    return "".join(str(item.get("plain_text", "")) for item in (items or [])).strip()


def parse_text(prop):
    t = prop.get("type")
    if t == "title":
        return rich_text_to_plain(prop.get("title"))
    if t == "rich_text":
        return rich_text_to_plain(prop.get("rich_text"))
    if t == "select":
        obj = prop.get("select")
        return obj.get("name", "") if obj else ""
    if t == "status":
        obj = prop.get("status")
        return obj.get("name", "") if obj else ""
    if t == "formula":
        f = prop.get("formula") or {}
        if f.get("type") == "string":
            return str(f.get("string") or "")
    return ""


def parse_number(prop):
    t = prop.get("type")
    if t == "number":
        value = prop.get("number")
    elif t == "formula":
        value = (prop.get("formula") or {}).get("number")
    elif t == "rollup":
        value = (prop.get("rollup") or {}).get("number")
    else:
        value = prop.get("number")
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_date(prop):
    obj = prop.get("date")
    if not obj or not obj.get("start"):
        return None
    try:
        return date.fromisoformat(str(obj["start"])[:10])
    except ValueError:
        return None


def aggregate_daily(records):
    by_day = defaultdict(lambda: {"minutes": 0, "record_count": 0})
    for page in records:
        props = page.get("properties", {})
        day = parse_date(props.get(DATE_PROPERTY, {}))
        minutes = int(round(parse_number(props.get(MINUTES_PROPERTY, {}))))
        if not day or minutes <= 0:
            continue
        by_day[day]["minutes"] += minutes
        by_day[day]["record_count"] += 1
    return by_day


def parse_chapters(pages):
    rows = []
    for page in pages:
        props = page.get("properties", {})
        rows.append({
            "number": int(round(parse_number(props.get(CHAPTER_NUMBER_PROPERTY, {})))),
            "title": parse_text(props.get(CHAPTER_TITLE_PROPERTY, {})),
            "status": parse_text(props.get(CHAPTER_STATUS_PROPERTY, {})),
            "current_unit": parse_text(props.get(CURRENT_UNIT_PROPERTY, {})),
            "next_action": parse_text(props.get(NEXT_ACTION_PROPERTY, {})),
            "actual_hours": round(parse_number(props.get(CHAPTER_ACTUAL_HOURS_PROPERTY, {})), 2),
            "expected_hours": round(parse_number(props.get(CHAPTER_EXPECTED_HOURS_PROPERTY, {})), 2),
            "url": page.get("url", ""),
        })
    return sorted(rows, key=lambda x: x["number"])


def current_week(today):
    for label, start, end, target in WEEK_PLAN:
        if start <= today <= end:
            return {"label": label, "start": start, "end": end, "target_hours": target}
    label, start, end, target = WEEK_PLAN[0] if today < COURSE_START else WEEK_PLAN[-1]
    return {"label": label, "start": start, "end": end, "target_hours": target}


def planned_hours_on(day):
    if day < COURSE_START:
        return 0.0
    if day >= COURSE_END:
        return float(sum(x[3] for x in WEEK_PLAN))
    total = 0.0
    for _, start, end, target in WEEK_PLAN:
        if day > end:
            total += target
        elif start <= day <= end:
            total += target * (((day - start).days + 1) / ((end - start).days + 1))
            break
        else:
            break
    return round(total, 2)


def make_global_payload(by_day, chapters):
    today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date()
    week = current_week(today)
    today_minutes = by_day.get(today, {}).get("minutes", 0)
    week_minutes = sum(v["minutes"] for d, v in by_day.items() if week["start"] <= d <= week["end"])
    week_hours = round(week_minutes / 60, 2)
    total_hours = round(sum(v["minutes"] for v in by_day.values()) / 60, 2)
    total_plan = sum(x[3] for x in WEEK_PLAN)
    passed = sum(1 for c in chapters if c["status"] == "已通过")
    overall_pct = round(total_hours / total_plan * 100, 2) if total_plan else 0
    gap = round(total_hours - planned_hours_on(today), 2)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": {
            "date": today.isoformat(),
            "actual_minutes": today_minutes,
            "record_count": by_day.get(today, {}).get("record_count", 0),
            "has_record": today_minutes > 0,
        },
        "week": {
            "label": week["label"],
            "actual_hours": week_hours,
            "target_hours": week["target_hours"],
            "remaining_hours": round(max(0, week["target_hours"] - week_hours), 2),
            "completion_pct": round(week_hours / week["target_hours"] * 100, 1) if week["target_hours"] else 0,
        },
        "overall": {
            "actual_hours": total_hours,
            "plan_total_hours": total_plan,
            "completion_pct": overall_pct,
            "passed_chapters": passed,
            "total_chapters": len(chapters),
            "gap_hours": gap,
        },
        "milestones": PHASES,
    }


def detect_phase(chapters):
    current = next((c for c in chapters if c["status"] == "学习中"), None)
    if current:
        number = current["number"]
    else:
        incomplete = next((c for c in chapters if c["status"] != "已通过"), None)
        number = incomplete["number"] if incomplete else 15
    return next(p for p in PHASES if p["start"] <= number <= p["end"])


def make_phase_payload(chapters):
    phase = detect_phase(chapters)
    phase_chapters = [c for c in chapters if phase["start"] <= c["number"] <= phase["end"]]
    completed = sum(1 for c in phase_chapters if c["status"] == "已通过")
    current = next((c for c in phase_chapters if c["status"] == "学习中"), None)
    if current is None:
        current = next((c for c in phase_chapters if c["status"] != "已通过"), phase_chapters[-1])
    next_chapter = next((c for c in phase_chapters if c["number"] > current["number"] and c["status"] != "已通过"), None)
    position = phase_chapters.index(current) if current in phase_chapters else completed
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": {
            **phase,
            "completed": completed,
            "total": len(phase_chapters),
            "completion_pct": round(completed / len(phase_chapters) * 100, 1) if phase_chapters else 0,
            "is_complete": completed == len(phase_chapters),
        },
        "current_chapter": current,
        "next_chapter": next_chapter,
        "boat_index": position,
        "chapters": phase_chapters,
    }



def intensity(minutes):
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


def make_heatmap_payload(by_day):
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weekly_target_hours": 20,
        "days": [
            {
                "date": d.isoformat(),
                "minutes": v["minutes"],
                "record_count": v["record_count"],
                "level": intensity(v["minutes"]),
            }
            for d, v in sorted(by_day.items())
        ],
    }


def make_weekly_payload(by_day):
    today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date()
    weeks = []
    total_actual = 0.0
    current = None
    for label, start, end, target in WEEK_PLAN:
        actual_minutes = sum(v["minutes"] for d, v in by_day.items() if start <= d <= end)
        actual_hours = round(actual_minutes / 60, 2)
        total_actual += actual_hours
        item = {
            "label": f"{start.month}.{start.day}–{end.month}.{end.day}",
            "date_label": label,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "target_hours": target,
            "actual_hours": actual_hours,
            "completion_pct": round(actual_hours / target * 100, 1) if target else 0,
        }
        weeks.append(item)
        if start <= today <= end:
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


def make_progress_payload(by_day):
    today = datetime.now(ZoneInfo(TIMEZONE_NAME)).date()
    display_end = min(max(today, COURSE_START), COURSE_END)
    actual_points = []
    cumulative = 0.0
    d = COURSE_START
    while d <= display_end:
        cumulative += by_day.get(d, {}).get("minutes", 0) / 60
        actual_points.append({"date": d.isoformat(), "hours": round(cumulative, 2)})
        d += timedelta(days=1)

    planned_points = [{"date": COURSE_START.isoformat(), "hours": 0.0}]
    running = 0.0
    for _, _, end, target in WEEK_PLAN:
        running += target
        planned_points.append({"date": end.isoformat(), "hours": round(running, 2)})

    plan_total = sum(x[3] for x in WEEK_PLAN)
    planned_to_date = planned_hours_on(display_end)
    gap = round(cumulative - planned_to_date, 2)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "course_start": COURSE_START.isoformat(),
        "course_end": COURSE_END.isoformat(),
        "today": display_end.isoformat(),
        "plan_total_hours": plan_total,
        "actual_total_hours": round(cumulative, 2),
        "planned_to_date_hours": planned_to_date,
        "gap_hours": gap,
        "completion_pct": round(cumulative / plan_total * 100, 1) if plan_total else 0,
        "actual_points": actual_points,
        "planned_points": planned_points,
    }

def write_json(name, payload):
    (PUBLIC_DIR / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    validate_environment()
    records = query_data_source(
        LEARNING_RECORDS_DATA_SOURCE_ID,
        filter_obj={"property": COUNT_PROPERTY, "checkbox": {"equals": True}},
        sorts=[{"property": DATE_PROPERTY, "direction": "ascending"}],
    )
    chapter_pages = query_data_source(
        CHAPTERS_DATA_SOURCE_ID,
        sorts=[{"property": CHAPTER_NUMBER_PROPERTY, "direction": "ascending"}],
    )
    by_day = aggregate_daily(records)
    chapters = parse_chapters(chapter_pages)

    write_json("data.json", make_heatmap_payload(by_day))
    write_json("weekly-data.json", make_weekly_payload(by_day))
    write_json("progress-data.json", make_progress_payload(by_day))
    write_json("polar-progress-data.json", make_global_payload(by_day, chapters))
    write_json("phase-voyage-data.json", make_phase_payload(chapters))
    (PUBLIC_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(
        f"构建完成：{len(records)}条学习记录，{len(chapters)}个章节；"
        "已更新热力图、每周小时、累计进度、总航标和阶段航线数据。"
    )


if __name__ == "__main__":
    main()
