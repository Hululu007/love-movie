import json
import re
import time
from pathlib import Path
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

DOUBAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Referer": "https://movie.douban.com/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
CACHE_PATH = Path("data/douban_cache.json")

def load_cache():
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def build_search_url(query):
    return f"https://search.douban.com/movie/subject_search?search_text={quote(query)}"

def fetch_douban_subject(douban_id):
    url = f"https://movie.douban.com/subject/{douban_id}/"
    result = {"douban_id": douban_id, "douban_url": url, "douban_title": "", "douban_rating": None}
    try:
        resp = requests.get(url, headers=DOUBAN_HEADERS, timeout=12)
        if resp.status_code != 200:
            return result
        soup = BeautifulSoup(resp.text, "lxml")
        h1 = soup.find("h1")
        if h1 and h1.find("span"):
            result["douban_title"] = h1.find("span").get_text(strip=True)
        rating_el = soup.select_one("strong.rating_num")
        if rating_el and rating_el.get_text(strip=True):
            try:
                result["douban_rating"] = float(rating_el.get_text(strip=True))
            except ValueError:
                pass
    except Exception:
        pass
    return result

def match_douban(title, year=None, explicit_douban_id="", cache=None, delay=1.0):
    cache = cache if cache is not None else {}
    cache_key = explicit_douban_id or f"{title}::{year or ''}"
    if cache_key in cache and cache[cache_key].get("douban_id"):
        return cache[cache_key]
    if explicit_douban_id:
        info = fetch_douban_subject(str(explicit_douban_id).strip())
        cache[cache_key] = info
        return info
    fallback = {"douban_id": "", "douban_url": build_search_url(title), "douban_title": "", "douban_rating": None}
    if not title:
        return fallback
    try:
        time.sleep(delay)
        resp = requests.get("https://movie.douban.com/j/subject_suggest", params={"q": title}, headers=DOUBAN_HEADERS, timeout=10)
        if resp.status_code != 200:
            return fallback
        items = resp.json()
        if not isinstance(items, list) or not items:
            return fallback
        chosen = next((i for i in items if year and str(i.get("year") or "") == str(year)), items[0])
        douban_id = str(chosen.get("id") or "")
        info = {
            "douban_id": douban_id,
            "douban_url": chosen.get("url") or (f"https://movie.douban.com/subject/{douban_id}/" if douban_id else fallback["douban_url"]),
            "douban_title": re.sub(r"\s+", " ", str(chosen.get("title") or "")).strip(),
            "douban_rating": None,
        }
        if douban_id:
            detail = fetch_douban_subject(douban_id)
            if detail.get("douban_rating") is not None:
                info["douban_rating"] = detail["douban_rating"]
            if detail.get("douban_title"):
                info["douban_title"] = detail["douban_title"]
        cache[cache_key] = info
        return info
    except Exception:
        return fallback
