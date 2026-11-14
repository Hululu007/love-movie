import json
import re
import time
import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
}
IMDB_ID_PATTERN = re.compile(r"\b((?:nm|tt)\d{6,10})\b")

def extract_imdb_id(raw_value):
    if not raw_value:
        return None
    m = IMDB_ID_PATTERN.search(str(raw_value).strip())
    return m.group(1) if m else None

def _fetch_html(url, retries=3, delay=1.5):
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code in (429, 503):
                time.sleep(delay * (attempt + 2))
                continue
            resp.raise_for_status()
        except Exception as exc:
            last_err = exc
            time.sleep(delay * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")

def _extract_next_data(soup):
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            return json.loads(script.string)
        except json.JSONDecodeError:
            return {}
    return {}

def _extract_json_ld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return {}

def _walk_find_credits(obj, results):
    if isinstance(obj, dict):
        if "node" in obj and isinstance(obj["node"], dict):
            node = obj["node"]
            title_obj = node.get("title")
            if isinstance(title_obj, dict) and title_obj.get("id", "").startswith("tt"):
                title_text = (title_obj.get("titleText") or {}).get("text") or (title_obj.get("originalTitleText") or {}).get("text") or ""
                release_year = (title_obj.get("releaseYear") or {}).get("year")
                title_type = (title_obj.get("titleType") or {}).get("text") or ""
                rating = (title_obj.get("ratingsSummary") or {}).get("aggregateRating")
                prod_status = ((title_obj.get("productionStatus") or {}).get("currentProductionStage") or {}).get("text") or ""
                category = (node.get("category") or {}).get("text") or ""
                if title_text:
                    results.append({
                        "imdb_id": title_obj["id"],
                        "title": title_text,
                        "year": release_year,
                        "title_type": title_type,
                        "imdb_rating": rating,
                        "production_status": prod_status,
                        "role_category": category,
                        "imdb_url": f"https://www.imdb.com/title/{title_obj['id']}/",
                    })
                return
        for val in obj.values():
            _walk_find_credits(val, results)
    elif isinstance(obj, list):
        for item in obj:
            _walk_find_credits(item, results)

def fetch_person(imdb_input, allowed_roles=None):
    nm_id = extract_imdb_id(imdb_input)
    if not nm_id or not nm_id.startswith("nm"):
        raise ValueError(f"Invalid IMDb person ID: {imdb_input}")
    url = f"https://www.imdb.com/name/{nm_id}/"
    soup = BeautifulSoup(_fetch_html(url), "lxml")
    next_data = _extract_next_data(soup)
    json_ld = _extract_json_ld(soup)
    name = json_ld.get("name") or (soup.find("h1").get_text(strip=True) if soup.find("h1") else nm_id)
    raw_credits = []
    _walk_find_credits(next_data, raw_credits)
    merged = {}
    role_filter = {r.lower() for r in (allowed_roles or [])}
    for item in raw_credits:
        cat = item.get("role_category") or ""
        if role_filter and cat and not any(rf in cat.lower() for rf in role_filter):
            continue
        tid = item["imdb_id"]
        if tid not in merged:
            item["roles"] = [cat] if cat else []
            merged[tid] = item
        else:
            if cat and cat not in merged[tid]["roles"]:
                merged[tid]["roles"].append(cat)
    works = list(merged.values())
    works.sort(key=lambda x: (x.get("year") or 9999, x.get("title") or ""), reverse=True)
    return {"imdb_id": nm_id, "name": name, "imdb_url": url, "works_count": len(works), "works": works}

def fetch_title(imdb_input):
    tt_id = extract_imdb_id(imdb_input)
    if not tt_id or not tt_id.startswith("tt"):
        raise ValueError(f"Invalid IMDb title ID: {imdb_input}")
    url = f"https://www.imdb.com/title/{tt_id}/"
    soup = BeautifulSoup(_fetch_html(url), "lxml")
    next_data = _extract_next_data(soup)
    json_ld = _extract_json_ld(soup)
    above = next_data.get("props", {}).get("pageProps", {}).get("aboveTheFoldData", {})
    title = (above.get("titleText") or {}).get("text") or json_ld.get("name") or tt_id
    year = (above.get("releaseYear") or {}).get("year")
    title_type = (above.get("titleType") or {}).get("text") or "Movie"
    rating = (above.get("ratingsSummary") or {}).get("aggregateRating") or (json_ld.get("aggregateRating") or {}).get("ratingValue")
    prod_status = ((above.get("productionStatus") or {}).get("currentProductionStage") or {}).get("text") or ""
    return {
        "imdb_id": tt_id,
        "title": title,
        "year": year,
        "title_type": title_type,
        "imdb_rating": rating,
        "production_status": prod_status,
        "imdb_url": url,
    }
