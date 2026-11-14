import json
import re
import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
}
WIKIDATA_HEADERS = {"User-Agent": "LoveMovieTracker/1.0 (https://github.com/TangTangMo/love-movie)"}
IMDB_ID_PATTERN = re.compile(r"\b((?:nm|tt)\d{6,10})\b")

def extract_imdb_id(raw_value):
    if not raw_value:
        return None
    m = IMDB_ID_PATTERN.search(str(raw_value).strip())
    return m.group(1) if m is not None else None

def _fetch_imdb_suggestion(imdb_id):
    url = f"https://v3.sg.media-imdb.com/suggestion/x/{imdb_id}.json"
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=12)
        if r.status_code == 200:
            items = r.json().get("d") or []
            for item in items:
                if item.get("id") == imdb_id:
                    return item
            return items[0] if items else {}
    except Exception:
        pass
    return {}

def _find_wikidata_qid(imdb_id):
    try:
        r = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"haswbstatement:P345={imdb_id}",
                "format": "json",
            },
            headers=WIKIDATA_HEADERS,
            timeout=12,
        )
        if r.status_code == 200:
            hits = r.json().get("query", {}).get("search", [])
            if hits:
                return hits[0].get("title")
    except Exception:
        pass
    return None

def _query_wikidata_person(nm_id):
    qid = _find_wikidata_qid(nm_id)
    if not qid:
        return []
    sparql = f"""
    SELECT ?work ?imdb ?pubDate ?douban ?enLabel ?zhLabel ?role WHERE {{
      {{ ?work wdt:P57 wd:{qid} . BIND("Director" AS ?role) }}
      UNION
      {{ ?work wdt:P161 wd:{qid} . BIND("Actor" AS ?role) }}
      UNION
      {{ ?work wdt:P58 wd:{qid} . BIND("Writer" AS ?role) }}
      ?work wdt:P345 ?imdb .
      OPTIONAL {{ ?work wdt:P577 ?pubDate . }}
      OPTIONAL {{ ?work wdt:P4529 ?douban . }}
      OPTIONAL {{ ?work rdfs:label ?enLabel . FILTER(LANG(?enLabel) = "en") }}
      OPTIONAL {{ ?work rdfs:label ?zhLabel . FILTER(LANG(?zhLabel) = "zh") }}
    }}
    LIMIT 150
    """
    try:
        r = requests.get(
            "https://query.wikidata.org/sparql",
            params={"query": sparql, "format": "json"},
            headers=WIKIDATA_HEADERS,
            timeout=25,
        )
        if r.status_code == 200:
            return r.json().get("results", {}).get("bindings", [])
    except Exception:
        pass
    return []

def _query_wikidata_title(tt_id):
    qid = _find_wikidata_qid(tt_id)
    if not qid:
        return {}
    sparql = f"""
    SELECT ?enLabel ?zhLabel ?douban ?pubDate WHERE {{
      OPTIONAL {{ wd:{qid} wdt:P4529 ?douban . }}
      OPTIONAL {{ wd:{qid} wdt:P577 ?pubDate . }}
      OPTIONAL {{ wd:{qid} rdfs:label ?enLabel . FILTER(LANG(?enLabel) = "en") }}
      OPTIONAL {{ wd:{qid} rdfs:label ?zhLabel . FILTER(LANG(?zhLabel) = "zh") }}
    }}
    LIMIT 5
    """
    try:
        r = requests.get(
            "https://query.wikidata.org/sparql",
            params={"query": sparql, "format": "json"},
            headers=WIKIDATA_HEADERS,
            timeout=15,
        )
        if r.status_code == 200:
            rows = r.json().get("results", {}).get("bindings", [])
            return rows[0] if rows else {}
    except Exception:
        pass
    return {}

def _fetch_html_safe(url):
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return ""

def fetch_person(imdb_input, allowed_roles=None):
    nm_id = extract_imdb_id(imdb_input)
    if not nm_id or not nm_id.startswith("nm"):
        raise ValueError(f"Invalid IMDb person ID: {imdb_input}")
    url = f"https://www.imdb.com/name/{nm_id}/"
    sugg = _fetch_imdb_suggestion(nm_id)
    name = sugg.get("l") or nm_id
    avatar = (sugg.get("i") or {}).get("imageUrl") or ""
    role_filter = {r.lower() for r in (allowed_roles or [])}

    merged = {}
    for row in _query_wikidata_person(nm_id):
        tid = (row.get("imdb") or {}).get("value") or ""
        if not tid.startswith("tt"):
            continue
        role = (row.get("role") or {}).get("value") or ""
        if role_filter and role and not any(rf in role.lower() for rf in role_filter):
            continue
        pub = (row.get("pubDate") or {}).get("value") or ""
        year = int(pub[:4]) if len(pub) >= 4 and pub[:4].isdigit() else None
        title = (row.get("enLabel") or {}).get("value") or (row.get("zhLabel") or {}).get("value") or tid
        zh_title = (row.get("zhLabel") or {}).get("value") or ""
        douban_id = (row.get("douban") or {}).get("value") or ""
        prod_status = "Upcoming" if (year and year >= 2026) else ""
        if tid not in merged:
            merged[tid] = {
                "imdb_id": tid,
                "title": title,
                "douban_title": zh_title,
                "douban_id": douban_id,
                "douban_url": f"https://movie.douban.com/subject/{douban_id}/" if douban_id else "",
                "year": year,
                "title_type": "Movie/Series",
                "imdb_rating": None,
                "production_status": prod_status,
                "roles": [role] if role else [],
                "imdb_url": f"https://www.imdb.com/title/{tid}/",
            }
        else:
            if role and role not in merged[tid]["roles"]:
                merged[tid]["roles"].append(role)

    works = list(merged.values())
    works.sort(key=lambda x: (x.get("year") or 9999, x.get("title") or ""), reverse=True)
    return {"imdb_id": nm_id, "name": name, "avatar": avatar, "imdb_url": url, "works_count": len(works), "works": works}

def fetch_title(imdb_input):
    tt_id = extract_imdb_id(imdb_input)
    if not tt_id or not tt_id.startswith("tt"):
        raise ValueError(f"Invalid IMDb title ID: {imdb_input}")
    url = f"https://www.imdb.com/title/{tt_id}/"
    sugg = _fetch_imdb_suggestion(tt_id)
    wd = _query_wikidata_title(tt_id)

    title = sugg.get("l") or (wd.get("enLabel") or {}).get("value") or tt_id
    year = sugg.get("y")
    if not year:
        pub = (wd.get("pubDate") or {}).get("value") or ""
        if len(pub) >= 4 and pub[:4].isdigit():
            year = int(pub[:4])
    poster = (sugg.get("i") or {}).get("imageUrl") or ""
    title_type = sugg.get("qid") or sugg.get("q") or "Movie"
    zh_title = (wd.get("zhLabel") or {}).get("value") or ""
    douban_id = (wd.get("douban") or {}).get("value") or ""
    prod_status = "Upcoming" if (year and int(year) >= 2026) else ""

    html_text = _fetch_html_safe(url)
    rating = None
    if html_text:
        soup = BeautifulSoup(html_text, "lxml")
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                jd = json.loads(s.string or "{}")
                if isinstance(jd, dict) and jd.get("aggregateRating"):
                    rating = jd["aggregateRating"].get("ratingValue")
                    break
            except Exception:
                pass

    return {
        "imdb_id": tt_id,
        "title": title,
        "douban_title": zh_title,
        "douban_id": douban_id,
        "douban_url": f"https://movie.douban.com/subject/{douban_id}/" if douban_id else "",
        "year": year,
        "poster": poster,
        "title_type": title_type,
        "imdb_rating": rating,
        "production_status": prod_status,
        "imdb_url": url,
    }
