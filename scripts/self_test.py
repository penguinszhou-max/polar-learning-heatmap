import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import date
from scripts import build

def prop_num(v): return {"type":"number","number":v}
def prop_text(v): return {"type":"rich_text","rich_text":[{"plain_text":v}]}
def prop_title(v): return {"type":"title","title":[{"plain_text":v}]}
def prop_status(v): return {"type":"status","status":{"name":v}}

def chapter(n,title,status,actual,expected,unit="",action=""):
    return {"url":"https://example.test","properties":{
        build.CHAPTER_NUMBER_PROPERTY:prop_num(n),build.CHAPTER_TITLE_PROPERTY:prop_title(title),build.CHAPTER_STATUS_PROPERTY:prop_status(status),
        build.CHAPTER_ACTUAL_HOURS_PROPERTY:prop_num(actual),build.CHAPTER_EXPECTED_HOURS_PROPERTY:prop_num(expected),
        build.CURRENT_UNIT_PROPERTY:prop_text(unit),build.NEXT_ACTION_PROPERTY:prop_text(action)}}

pages=[chapter(1,"第1章｜海洋是一个怎样的物理系统","学习中",2,4,"已完成1.1—1.4；下一单元1.5","进入1.5")]+[chapter(i,f"第{i}章","未开始",0,10) for i in range(2,16)]
chapters,diag=build.parse_chapters(pages)
assert chapters[0]["title"]=="第1章｜海洋是一个怎样的物理系统"
assert diag["active_chapter_count"]==1
by_day={date.today():{"minutes":120,"record_count":1}}
b=build.beacon_payload(by_day,chapters,diag); p=build.phase_voyage_payload(chapters,diag)
assert b["current_phase"]["name"]=="基础语言与海洋结构"
assert b["context"]["number"]==1
assert p["phase"]["passed_chapters"]==0
assert p["phase"]["total_chapters"]==5
assert p["phase"]["route_progress_pct"]==10.0
assert len(p["chapters"])==5
build.validate_payloads({"polar-progress-data.json":b,"phase-voyage-data.json":p,"data.json":build.heatmap_payload(by_day),"weekly-data.json":build.weekly_payload(by_day),"progress-data.json":build.progress_payload(by_day)})
print("SELF_TEST_OK")
