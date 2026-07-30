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

SCHEMA_VERSION = 3
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
    ("W1", date(2026,7,29), date(2026,8,4), 20),
    ("W2", date(2026,8,5), date(2026,8,11), 20),
    ("W3", date(2026,8,12), date(2026,8,18), 20),
    ("W4", date(2026,8,19), date(2026,8,25), 21),
    ("W5", date(2026,8,26), date(2026,9,1), 21),
    ("W6", date(2026,9,2), date(2026,9,8), 23),
    ("W7", date(2026,9,9), date(2026,9,15), 21),
    ("W8", date(2026,9,16), date(2026,9,22), 20),
    ("W9", date(2026,9,23), date(2026,9,29), 22),
    ("W10",date(2026,9,30), date(2026,10,6), 24),
    ("W11",date(2026,10,7), date(2026,10,13), 24),
    ("W12",date(2026,10,14), date(2026,10,20), 24),
    ("W13",date(2026,10,21), date(2026,10,27), 22),
    ("W14",date(2026,10,28), date(2026,11,3), 22),
    ("W15",date(2026,11,4), date(2026,11,10), 22),
]

PHASES = [
    {"id":1,"name":"基础语言与海洋结构","short":"基础","start_chapter":1,"end_chapter":5,"start":date(2026,7,29),"end":date(2026,8,25)},
    {"id":2,"name":"旋转海洋与收支","short":"动力","start_chapter":6,"end_chapter":9,"start":date(2026,8,26),"end":date(2026,9,22)},
    {"id":3,"name":"极地过程与区域整合","short":"极地","start_chapter":10,"end_chapter":13,"start":date(2026,9,23),"end":date(2026,10,20)},
    {"id":4,"name":"气候动力与综合验收","short":"验收","start_chapter":14,"end_chapter":15,"start":date(2026,10,21),"end":date(2026,11,10)},
]
PASSED_STATUSES={"已通过","通过","已掌握","已完成","完成"}
ACTIVE_STATUSES={"学习中","进行中"}
REVIEW_STATUSES={"待验收","待复测","复测中","待复习"}
REPAIR_STATUSES={"待修复","需修复","局部修复"}
KNOWN_STATUSES=PASSED_STATUSES|ACTIVE_STATUSES|REVIEW_STATUSES|REPAIR_STATUSES|{"未开始","暂停","延后"}

class NotionError(RuntimeError): pass

def validate_environment()->None:
    missing=[]
    if not TOKEN: missing.append("NOTION_TOKEN")
    if not LEARNING_RECORDS_DATA_SOURCE_ID: missing.append("LEARNING_RECORDS_DATA_SOURCE_ID")
    if not CHAPTERS_DATA_SOURCE_ID: missing.append("CHAPTERS_DATA_SOURCE_ID")
    if missing: raise SystemExit("缺少GitHub Secret："+", ".join(missing))

def notion_request(method:str,path:str,*,payload:dict[str,Any]|None=None,max_attempts:int=5)->dict[str,Any]:
    headers={"Authorization":f"Bearer {TOKEN}","Notion-Version":NOTION_VERSION,"Content-Type":"application/json"}
    for attempt in range(1,max_attempts+1):
        try:
            response=requests.request(method,f"{NOTION_API_BASE}{path}",headers=headers,json=payload,timeout=45)
        except requests.RequestException as exc:
            if attempt==max_attempts: raise NotionError(f"Notion网络请求失败：{exc}") from exc
            time.sleep(min(2**attempt+random.random(),12)); continue
        if response.ok: return response.json()
        if response.status_code in {429,500,502,503,504} and attempt<max_attempts:
            delay=float(response.headers.get("Retry-After") or 2**attempt)
            time.sleep(min(delay+random.random(),12)); continue
        hints={401:"检查NOTION_TOKEN",403:"内部连接缺少读取权限",404:"检查Data Source ID及数据库连接授权"}
        raise NotionError(f"Notion API HTTP {response.status_code}：{hints.get(response.status_code,'查看Actions日志')}\n{response.text[:1000]}")
    raise NotionError("Notion API请求达到最大重试次数")

def query_data_source(data_source_id:str,*,filter_obj:dict[str,Any]|None=None,sorts:list[dict[str,Any]]|None=None)->list[dict[str,Any]]:
    results=[]; cursor=None
    while True:
        payload={"page_size":100}
        if filter_obj: payload["filter"]=filter_obj
        if sorts: payload["sorts"]=sorts
        if cursor: payload["start_cursor"]=cursor
        data=notion_request("POST",f"/data_sources/{data_source_id}/query",payload=payload)
        results.extend(data.get("results",[]))
        if not data.get("has_more"): break
        cursor=data.get("next_cursor")
        if not cursor: break
    return results

def rich_text_to_plain(items:list[dict[str,Any]]|None)->str:
    return "" if not items else "".join(str(x.get("plain_text","")) for x in items).strip()

def parse_date(prop:dict[str,Any])->date|None:
    obj=prop.get("date") or {}; start=obj.get("start")
    if not start: return None
    try: return date.fromisoformat(str(start)[:10])
    except ValueError: return None

def parse_number(prop:dict[str,Any])->float:
    t=prop.get("type")
    if t=="number": v=prop.get("number")
    elif t=="formula": v=(prop.get("formula") or {}).get("number")
    elif t=="rollup": v=(prop.get("rollup") or {}).get("number")
    else: v=prop.get("number")
    try: return 0.0 if v is None else float(v)
    except (TypeError,ValueError): return 0.0

def parse_text(prop:dict[str,Any])->str:
    t=prop.get("type")
    if t=="title": return rich_text_to_plain(prop.get("title"))
    if t=="rich_text": return rich_text_to_plain(prop.get("rich_text"))
    if t=="select": return str((prop.get("select") or {}).get("name") or "").strip()
    if t=="status": return str((prop.get("status") or {}).get("name") or "").strip()
    if t=="formula":
        f=prop.get("formula") or {}
        if f.get("type")=="string": return str(f.get("string") or "").strip()
    return ""

def chapter_number(value:float)->int:
    try: return int(round(float(value)))
    except (TypeError,ValueError): return 0

def normalize_title(number:int,title:str)->str:
    title=re.sub(r"\s+"," ",(title or "").strip())
    title=re.sub(rf"^第\s*{number}\s*章\s*[｜|:：\-—]*\s*","",title)
    return f"第{number}章｜{title}" if title else f"第{number}章"

def query_learning_records()->list[dict[str,Any]]:
    return query_data_source(LEARNING_RECORDS_DATA_SOURCE_ID,filter_obj={"property":COUNT_PROPERTY,"checkbox":{"equals":True}},sorts=[{"property":DATE_PROPERTY,"direction":"ascending"}])

def query_chapters()->list[dict[str,Any]]:
    return query_data_source(CHAPTERS_DATA_SOURCE_ID,sorts=[{"property":CHAPTER_NUMBER_PROPERTY,"direction":"ascending"}])

def aggregate_daily(records:list[dict[str,Any]])->dict[date,dict[str,int]]:
    by_day=defaultdict(lambda:{"minutes":0,"record_count":0})
    for page in records:
        props=page.get("properties",{}); day=parse_date(props.get(DATE_PROPERTY,{})); minutes=int(round(parse_number(props.get(MINUTES_PROPERTY,{}))))
        if day and minutes>0:
            by_day[day]["minutes"]+=minutes; by_day[day]["record_count"]+=1
    return by_day

def parse_chapters(pages:list[dict[str,Any]])->tuple[list[dict[str,Any]],dict[str,Any]]:
    chapters=[]; unknown=set(); missing=[]
    for page in pages:
        props=page.get("properties",{})
        number=chapter_number(parse_number(props.get(CHAPTER_NUMBER_PROPERTY,{})))
        status=parse_text(props.get(CHAPTER_STATUS_PROPERTY,{})) or "未开始"
        actual=round(parse_number(props.get(CHAPTER_ACTUAL_HOURS_PROPERTY,{})),2)
        expected=round(parse_number(props.get(CHAPTER_EXPECTED_HOURS_PROPERTY,{})),2)
        passed=status in PASSED_STATUSES; active=status in ACTIVE_STATUSES; review=status in REVIEW_STATUSES; repair=status in REPAIR_STATUSES
        if status not in KNOWN_STATUSES: unknown.add(status)
        if expected<=0 and not passed and number>0: missing.append(number)
        time_progress=100.0 if passed else (min(99.0,round(actual/expected*100,1)) if expected>0 else 0.0)
        chapters.append({
            "number":number,"title":normalize_title(number,parse_text(props.get(CHAPTER_TITLE_PROPERTY,{}))),"status":status,
            "current_unit":parse_text(props.get(CURRENT_UNIT_PROPERTY,{})),"next_action":parse_text(props.get(NEXT_ACTION_PROPERTY,{})),
            "actual_hours":actual,"expected_hours":expected,"time_progress_pct":time_progress,"progress_pct":time_progress,
            "passed":passed,"active":active,"review":review,"repair":repair,"url":page.get("url","")
        })
    chapters=sorted((c for c in chapters if c["number"]>0),key=lambda c:c["number"])
    return chapters,{"active_chapter_count":sum(c["active"] for c in chapters),"unknown_statuses":sorted(unknown),"missing_expected_hours":sorted(set(missing))}

def intensity(minutes:int)->int:
    if minutes<=0:return 0
    if minutes<45:return 1
    if minutes<90:return 2
    if minutes<150:return 3
    if minutes<210:return 4
    if minutes<270:return 5
    return 6

def format_date_range(start:date,end:date)->str:
    return f"{start.month}月{start.day}日—{end.day}日" if start.month==end.month else f"{start.month}月{start.day}日—{end.month}月{end.day}日"

def compact_date_range(start:date,end:date)->str: return f"{start.month}.{start.day}–{end.month}.{end.day}"

def current_week(today:date)->dict[str,Any]:
    for internal,start,end,target in WEEK_PLAN:
        if start<=today<=end:return {"internal_id":internal,"start":start,"end":end,"target_hours":target}
    internal,start,end,target=WEEK_PLAN[0] if today<COURSE_START else WEEK_PLAN[-1]
    return {"internal_id":internal,"start":start,"end":end,"target_hours":target}

def planned_hours_on(day:date)->float:
    if day<COURSE_START:return 0.0
    if day>=COURSE_END:return float(sum(w[3] for w in WEEK_PLAN))
    total=0.0
    for _,start,end,target in WEEK_PLAN:
        if day>end: total+=target; continue
        if day<start: break
        total+=target*((day-start).days+1)/((end-start).days+1); break
    return round(total,2)

def phase_for_chapter(number:int)->dict[str,Any]:
    for p in PHASES:
        if p["start_chapter"]<=number<=p["end_chapter"]:return p
    return PHASES[0] if number<=0 else PHASES[-1]

def choose_current_chapter(chapters:list[dict[str,Any]])->dict[str,Any]|None:
    for key in ("active","review","repair"):
        found=next((c for c in chapters if c[key]),None)
        if found:return found
    return next((c for c in chapters if not c["passed"]),chapters[-1] if chapters else None)

def heatmap_payload(by_day):
    return {"schema_version":SCHEMA_VERSION,"generated_at":datetime.now(timezone.utc).isoformat(),"weekly_target_hours":20,"days":[{"date":d.isoformat(),"minutes":v["minutes"],"record_count":v["record_count"],"level":intensity(v["minutes"])} for d,v in sorted(by_day.items())]}

def weekly_payload(by_day):
    today=datetime.now(ZoneInfo(TIMEZONE_NAME)).date(); weeks=[]; current=None
    for internal,start,end,target in WEEK_PLAN:
        actual=round(sum(v["minutes"] for d,v in by_day.items() if start<=d<=end)/60,2)
        item={"internal_id":internal,"label":compact_date_range(start,end),"date_label":format_date_range(start,end),"start":start.isoformat(),"end":end.isoformat(),"target_hours":target,"actual_hours":actual,"completion_pct":round(actual/target*100,1) if target else 0}
        weeks.append(item)
        if start<=today<=end:current=item
    return {"schema_version":SCHEMA_VERSION,"generated_at":datetime.now(timezone.utc).isoformat(),"redline_hours":18,"minimum_hours":20,"standard_hours":22,"sprint_hours":24,"total_actual_hours":round(sum(w["actual_hours"] for w in weeks),2),"current_week":current,"weeks":weeks}

def progress_payload(by_day):
    today=datetime.now(ZoneInfo(TIMEZONE_NAME)).date(); end=min(max(today,COURSE_START),COURSE_END); actual=[]; cum=0.0; d=COURSE_START
    while d<=end:
        cum+=by_day.get(d,{}).get("minutes",0)/60; actual.append({"date":d.isoformat(),"hours":round(cum,2)}); d+=timedelta(days=1)
    planned=[{"date":COURSE_START.isoformat(),"hours":0.0}]; total=0.0
    for _,_,week_end,target in WEEK_PLAN:
        total+=target; planned.append({"date":week_end.isoformat(),"hours":round(total,2)})
    planned_to_date=planned_hours_on(end)
    return {"schema_version":SCHEMA_VERSION,"generated_at":datetime.now(timezone.utc).isoformat(),"course_start":COURSE_START.isoformat(),"course_end":COURSE_END.isoformat(),"today":end.isoformat(),"plan_total_hours":int(total),"actual_total_hours":round(cum,2),"planned_to_date_hours":planned_to_date,"gap_hours":round(cum-planned_to_date,2),"completion_pct":round(cum/total*100,1) if total else 0,"actual_points":actual,"planned_points":planned}

def beacon_payload(by_day,chapters,diagnostics):
    today=datetime.now(ZoneInfo(TIMEZONE_NAME)).date(); week=current_week(today); current=choose_current_chapter(chapters)
    td=by_day.get(today,{"minutes":0,"record_count":0}); week_hours=round(sum(v["minutes"] for d,v in by_day.items() if week["start"]<=d<=week["end"])/60,2)
    total_hours=round(sum(v["minutes"] for v in by_day.values())/60,2); total_plan=int(sum(w[3] for w in WEEK_PLAN)); pct=round(total_hours/total_plan*100,1) if total_plan else 0; planned=planned_hours_on(today)
    phase=phase_for_chapter(current["number"] if current else 1); phase_items=[]
    for p in PHASES:
        items=[c for c in chapters if p["start_chapter"]<=c["number"]<=p["end_chapter"]]; completed=sum(c["passed"] for c in items)
        phase_items.append({"id":p["id"],"name":p["name"],"short":p["short"],"completed_chapters":completed,"passed_chapters":completed,"total_chapters":len(items),"complete":bool(items) and completed==len(items)})
    return {"schema_version":SCHEMA_VERSION,"generated_at":datetime.now(timezone.utc).isoformat(),
        "today":{"date":today.isoformat(),"minutes":td["minutes"],"record_count":td["record_count"],"has_learning":td["minutes"]>0},
        "week":{"label":format_date_range(week["start"],week["end"]),"actual_hours":week_hours,"target_hours":week["target_hours"],"completion_pct":round(week_hours/week["target_hours"]*100,1),"remaining_hours":round(max(0,week["target_hours"]-week_hours),2)},
        "overall":{"actual_hours":total_hours,"plan_total_hours":total_plan,"completion_pct":pct,"visual_progress_pct":max(1.5,pct) if pct>0 else 0,"planned_to_date_hours":planned,"gap_hours":round(total_hours-planned,2),"passed_chapters":sum(c["passed"] for c in chapters),"total_chapters":len(chapters)},
        "context":current,"current_chapter":current,
        "current_phase":{"id":phase["id"],"name":phase["name"],"short":phase["short"],"milestone":f"完成第{phase['start_chapter']}—{phase['end_chapter']}章"},
        "phases":phase_items,"diagnostics":diagnostics}

def phase_voyage_payload(chapters,diagnostics):
    current=choose_current_chapter(chapters); num=current["number"] if current else 1; phase=phase_for_chapter(num); items=[c for c in chapters if phase["start_chapter"]<=c["number"]<=phase["end_chapter"]]
    completed=sum(c["passed"] for c in items); total=len(items); active_index=0; fraction=0.0
    if current:
        for i,c in enumerate(items):
            if c["number"]==current["number"]:active_index=i;fraction=c["time_progress_pct"]/100;break
    route=100.0 if total and completed==total else (round((active_index+fraction)/total*100,1) if total else 0)
    next_chapter=next((c for c in items if current and c["number"]>current["number"] and not c["passed"]),None)
    phase_obj={"id":phase["id"],"name":phase["name"],"short":phase["short"],"start_chapter":phase["start_chapter"],"end_chapter":phase["end_chapter"],"date_label":format_date_range(phase["start"],phase["end"]),"passed_chapters":completed,"completed_chapters":completed,"total_chapters":total,"acceptance_pct":round(completed/total*100,1) if total else 0,"completion_pct":round(completed/total*100,1) if total else 0,"route_progress_pct":route,"complete":bool(total) and completed==total}
    return {"schema_version":SCHEMA_VERSION,"generated_at":datetime.now(timezone.utc).isoformat(),"phase":phase_obj,"current_chapter":current,"next_chapter":next_chapter,"chapters":items,"diagnostics":diagnostics}

def validate_payloads(payloads:dict[str,dict[str,Any]])->None:
    assert payloads["polar-progress-data.json"]["current_phase"]["name"]
    p=payloads["phase-voyage-data.json"]["phase"]
    assert isinstance(p["passed_chapters"],int) and isinstance(p["total_chapters"],int)
    assert isinstance(payloads["phase-voyage-data.json"]["chapters"],list)
    for name,data in payloads.items():
        assert data.get("schema_version")==SCHEMA_VERSION, name

def write_json(name,data):
    (PUBLIC_DIR/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def main()->None:
    validate_environment(); records=query_learning_records(); pages=query_chapters(); by_day=aggregate_daily(records); chapters,diagnostics=parse_chapters(pages)
    payloads={"data.json":heatmap_payload(by_day),"weekly-data.json":weekly_payload(by_day),"progress-data.json":progress_payload(by_day),"polar-progress-data.json":beacon_payload(by_day,chapters,diagnostics),"phase-voyage-data.json":phase_voyage_payload(chapters,diagnostics)}
    validate_payloads(payloads)
    for name,data in payloads.items():write_json(name,data)
    (PUBLIC_DIR/".nojekyll").write_text("",encoding="utf-8")
    print(f"统一构建完成：{len(records)}条正式记录，{len(chapters)}章，{len(by_day)}个学习日。")
    print("已生成："+"、".join(payloads))
    if diagnostics["active_chapter_count"]!=1:print("诊断：学习中章节数量",diagnostics["active_chapter_count"])
    if diagnostics["unknown_statuses"]:print("诊断：未知状态",diagnostics["unknown_statuses"])
    if diagnostics["missing_expected_hours"]:print("诊断：缺少预计小时",diagnostics["missing_expected_hours"])

if __name__=="__main__":main()
