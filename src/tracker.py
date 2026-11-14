import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import yaml
from src.douban_helper import load_cache, match_douban, save_cache
from src.imdb_scraper import extract_imdb_id, fetch_person, fetch_title

WATCHLIST_PATH = Path("watchlist.yaml")
DATA_PATH = Path("data/tracker_data.json")
BJ_TZ = timezone(timedelta(hours=8))

def load_watchlist(path=WATCHLIST_PATH):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

def load_previous_data(path=DATA_PATH):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def detect_changes(old_data, new_data):
    changes = []
    if not old_data:
        return changes
    old_people = {p.get("imdb_id"): p for p in old_data.get("people", [])}
    for person in new_data.get("people", []):
        pid = person.get("imdb_id")
        prev_person = old_people.get(pid)
        if not prev_person:
            changes.append({"type": "新追影人", "label": person.get("display_name") or person.get("name", pid)})
            continue
        prev_works = {w.get("imdb_id"): w for w in prev_person.get("works", [])}
        for work in person.get("works", []):
            wid = work.get("imdb_id")
            if wid not in prev_works:
                changes.append({"type": "影人新作", "label": f"{person.get('display_name') or person.get('name')} -> {work.get('title')} ({work.get('year') or '待定'})"})
            else:
                old_s = prev_works[wid].get("production_status") or ""
                new_s = work.get("production_status") or ""
                if new_s and new_s != old_s:
                    changes.append({"type": "状态更新", "label": f"{work.get('title')}: {old_s or '未知'} -> {new_s}"})
    old_series = {s.get("name"): s for s in old_data.get("series", [])}
    for series in new_data.get("series", []):
        sname = series.get("name")
        prev_s = old_series.get(sname)
        if not prev_s:
            changes.append({"type": "新追踪系列", "label": sname})
            continue
        prev_entries = {e.get("imdb_id"): e for e in prev_s.get("entries", [])}
        for entry in series.get("entries", []):
            eid = entry.get("imdb_id")
            if eid not in prev_entries:
                changes.append({"type": "系列新条目", "label": f"{sname} -> {entry.get('title')}"})
    return changes

def run_tracker():
    watchlist = load_watchlist()
    settings = watchlist.get("settings") or {}
    delay = float(settings.get("request_delay_seconds", 1.5))
    use_douban = bool(settings.get("enable_douban_helper", True))
    recent_years = int(settings.get("recent_years_limit", 0))
    current_year = datetime.now(BJ_TZ).year
    old_data = load_previous_data()
    douban_cache = load_cache()
    people_results = []
    for p_cfg in watchlist.get("people") or []:
        nm_id = extract_imdb_id(p_cfg.get("imdb") or p_cfg.get("imdb_id") or "")
        if not nm_id:
            continue
        try:
            person_data = fetch_person(nm_id, allowed_roles=p_cfg.get("roles"))
        except Exception as exc:
            person_data = {"imdb_id": nm_id, "name": p_cfg.get("name") or nm_id, "imdb_url": f"https://www.imdb.com/name/{nm_id}/", "works": [], "error": str(exc)}
        person_data["display_name"] = p_cfg.get("name") or person_data.get("name")
        person_data["notes"] = p_cfg.get("notes") or ""
        filtered_works = []
        for w in person_data.get("works", []):
            yr = w.get("year")
            if recent_years > 0 and yr and yr < (current_year - recent_years):
                continue
            if use_douban and (w.get("production_status") or not yr or yr >= current_year - 3):
                w.update(match_douban(w["title"], year=yr, cache=douban_cache, delay=0.5))
            else:
                w.setdefault("douban_url", f"https://search.douban.com/movie/subject_search?search_text={w['title']}")
                w.setdefault("douban_title", "")
                w.setdefault("douban_rating", None)
            filtered_works.append(w)
        person_data["works"] = filtered_works
        person_data["works_count"] = len(filtered_works)
        people_results.append(person_data)
        time.sleep(delay)
    series_results = []
    for s_cfg in watchlist.get("series") or []:
        entries_out = []
        for entry in s_cfg.get("entries") or []:
            tt_id = extract_imdb_id(entry.get("imdb") or entry.get("imdb_id") or "")
            if not tt_id:
                continue
            try:
                t_data = fetch_title(tt_id)
            except Exception as exc:
                t_data = {"imdb_id": tt_id, "title": entry.get("title") or tt_id, "year": None, "imdb_rating": None, "production_status": "", "imdb_url": f"https://www.imdb.com/title/{tt_id}/", "error": str(exc)}
            if use_douban:
                t_data.update(match_douban(t_data.get("title") or entry.get("title") or "", year=t_data.get("year"), explicit_douban_id=str(entry.get("douban_id") or ""), cache=douban_cache, delay=0.8))
            entries_out.append(t_data)
            time.sleep(delay)
        series_results.append({"name": s_cfg.get("name") or "未命名系列", "status": s_cfg.get("status") or "", "notes": s_cfg.get("notes") or "", "entries": entries_out})
    save_cache(douban_cache)
    new_data = {"updated_at": datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M UTC+8"), "people": people_results, "series": series_results, "recent_changes": []}
    new_data["recent_changes"] = detect_changes(old_data, new_data)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return new_data

if __name__ == "__main__":
    run_tracker()
