import gzip
import io
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
_IMDB_RATINGS_CACHE = None


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
        print(f"[imdb_suggestion] {imdb_id}: HTTP {r.status_code}", flush=True)
    except Exception as e:
        print(f"[imdb_suggestion] {imdb_id}: error {e}", flush=True)
    return {}


def _load_imdb_ratings():
    global _IMDB_RATINGS_CACHE
    if _IMDB_RATINGS_CACHE is not None:
        return _IMDB_RATINGS_CACHE
    ratings = {}
    url = "https://datasets.imdbws.com/title.ratings.tsv.gz"
    try:
        print(f"[imdb_ratings] Downloading {url}", flush=True)
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=60)
        if r.status_code == 200:
            with gzip.GzipFile(fileobj=io.BytesIO(r.content)) as gz:
                for i, raw_line in enumerate(gz):
                    if i == 0:
                        continue
                    parts = raw_line.decode("utf-8", errors="ignore").rstrip("\r\n").split("\t")
                    if len(parts) >= 2:
                        try:
                            ratings[parts[0]] = float(parts[1])
                        except ValueError:
                            pass
            print(f"[imdb_ratings] Loaded {len(ratings)} ratings", flush=True)
        else:
            print(f"[imdb_ratings] HTTP {r.status_code}", flush=True)
    except Exception as e:
        print(f"[imdb_ratings] error {e}", flush=True)
    _IMDB_RATINGS_CACHE = ratings
    return _IMDB_RATINGS_CACHE


def _query_wikidata_person(nm_id):
    sparql = f'''SELECT ?work ?imdb ?pubDate ?douban ?role WHERE {{
  ?person wdt:P345 "{nm_id}" .
  {{
    {{ ?work wdt:P57 ?person . BIND("Director" AS ?role) }}
    UNION
    {{ ?work wdt:P58 ?person . BIND("Writer" AS ?role) }}
    UNION
    {{ ?work wdt:P162 ?person . BIND("Producer" AS ?role) }}
    UNION
    {{ ?work wdt:P161 ?person . BIND("Actor" AS ?role) }}
  }}
  ?work wdt:P345 ?imdb .
  OPTIONAL {{ ?work wdt:P577 ?pubDate . }}
  OPTIONAL {{ ?work wdt:P4529 ?douban . }}
}}
LIMIT 300'''
    try:
        r = requests.get(
            "https://query.wikidata.org/sparql",
            params={"query": sparql, "format": "json"},
            headers=WIKIDATA_HEADERS,
            timeout=30,
        )
        if r.status_code == 200:
            rows = r.json().get("results", {}).get("bindings", [])
            print(f"[wikidata_person] {nm_id}: {len(rows)} rows", flush=True)
            return rows
        print(f"[wikidata_person] {nm_id}: HTTP {r.status_code} {r.text[:200]}", flush=True)
    except Exception as e:
        print(f"[wikidata_person] {nm_id}: error {e}", flush=True)
    return []


def _query_wikidata_title(tt_id):
    sparql = f'''SELECT ?enLabel ?zhLabel ?douban ?pubDate WHERE {{
  ?work wdt:P345 "{tt_id}" .
  OPTIONAL {{ ?work wdt:P4529 ?douban . }}
  OPTIONAL {{ ?work wdt:P577 ?pubDate . }}
  OPTIONAL {{ ?work rdfs:label ?enLabel . FILTER(LANG(?enLabel) = "en") }}
  OPTIONAL {{ ?work rdfs:label ?zhLabel . FILTER(LANG(?zhLabel) = "zh") }}
}}
LIMIT 5'''
    try:
        r = requests.get(
            "https://query.wikidata.org/sparql",
            params={"query": sparql, "format": "json"},
            headers=WIKIDATA_HEADERS,
            timeout=30,
        )
        if r.status_code == 200:
            rows = r.json().get("results", {}).get("bindings", [])
            if rows:
                return rows[0]
            print(f"[wikidata_title] {tt_id}: 0 rows", flush=True)
        else:
            print(f"[wikidata_title] {tt_id}: HTTP {r.status_code} {r.text[:200]}", flush=True)
    except Exception as e:
        print(f"[wikidata_title] {tt_id}: error {e}", flush=True)
    return {}


def _fetch_html_safe(url):
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=12)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            return r.text
    except Exception as e:
        print(f"[html_safe] {url}: error {e}", flush=True)
    return ""


def _fetch_wikidata_labels(qids):
    labels = {}
    qids = [q for q in dict.fromkeys(qids) if q]
    for i in range(0, len(qids), 50):
        batch = qids[i : i + 50]
        try:
            r = requests.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "labels",
                    "languages": "zh-cn|zh-hans|zh|en",
                    "format": "json",
                },
                headers=WIKIDATA_HEADERS,
                timeout=30,
            )
            if r.status_code == 200:
                entities = r.json().get("entities", {})
                for qid, ent in entities.items():
                    ent_labels = ent.get("labels", {})
                    zh = ""
                    for lang in ("zh-cn", "zh-hans", "zh"):
                        if lang in ent_labels:
                            zh = ent_labels[lang].get("value", "")
                            if zh:
                                break
                    en = (ent_labels.get("en") or {}).get("value", "")
                    labels[qid] = (zh, en)
            else:
                print(f"[wikidata_labels] HTTP {r.status_code} {r.text[:200]}", flush=True)
        except Exception as e:
            print(f"[wikidata_labels] error {e}", flush=True)
    return labels


def fetch_person(imdb_input, allowed_roles=None):
    nm_id = extract_imdb_id(imdb_input)
    if not nm_id or not nm_id.startswith("nm"):
        raise ValueError(f"Invalid IMDb person ID: {imdb_input}")
    url = f"https://www.imdb.com/name/{nm_id}/"
    sug = _fetch_imdb_suggestion(nm_id)
    name = sug.get("l") or nm_id
    avatar = (sug.get("i") or {}).get("imageUrl", "")
    rows = _query_wikidata_person(nm_id)
    by_tt = {}
    ratings = _load_imdb_ratings()
    tt_to_qid = {}
    for row in rows:
        tt_id = extract_imdb_id((row.get("imdb") or {}).get("value"))
        if not tt_id or not tt_id.startswith("tt"):
            continue
        role = (row.get("role") or {}).get("value", "")
        if allowed_roles and role not in allowed_roles:
            continue
        entry = by_tt.setdefault(tt_id, {
            "imdb_id": tt_id,
            "title": "",
            "year": None,
            "release_date": "",
            "roles": set(),
            "url": f"https://www.imdb.com/title/{tt_id}/",
            "poster": "",
            "douban_id": "",
            "imdb_rating": ratings.get(tt_id),
        })
        qid = (row.get("work") or {}).get("value", "").rsplit("/", 1)[-1]
        if qid and tt_id not in tt_to_qid:
            tt_to_qid[tt_id] = qid
        if role:
            entry["roles"].add(role)
        pub = (row.get("pubDate") or {}).get("value", "")[:10]
        if pub and (not entry["release_date"] or pub < entry["release_date"]):
            entry["release_date"] = pub
            if pub[:4].isdigit():
                entry["year"] = int(pub[:4])
        douban = (row.get("douban") or {}).get("value", "")
        if douban and not entry["douban_id"]:
            entry["douban_id"] = douban
    labels_by_qid = _fetch_wikidata_labels(tt_to_qid.values()) if tt_to_qid else {}
    credits = []
    for entry in by_tt.values():
        qid = tt_to_qid.get(entry["imdb_id"], "")
        zh, en = labels_by_qid.get(qid, ("", ""))
        if zh:
            entry["title"] = zh
        elif en:
            entry["title"] = en
        if not entry["title"]:
            entry["title"] = entry["imdb_id"]
        entry["roles"] = sorted(entry["roles"])
        credits.append(entry)
    credits.sort(key=lambda x: x["year"] or 0, reverse=True)
    return {
        "imdb_id": nm_id,
        "name": name,
        "avatar": avatar,
        "url": url,
        "credits": credits,
    }


def fetch_title(imdb_input):
    tt_id = extract_imdb_id(imdb_input)
    if not tt_id or not tt_id.startswith("tt"):
        raise ValueError(f"Invalid IMDb title ID: {imdb_input}")
    url = f"https://www.imdb.com/title/{tt_id}/"
    sug = _fetch_imdb_suggestion(tt_id)
    wd = _query_wikidata_title(tt_id)
    title = (wd.get("zhLabel") or {}).get("value") or (wd.get("enLabel") or {}).get("value") or sug.get("l") or tt_id
    pub = (wd.get("pubDate") or {}).get("value", "")[:10]
    year = int(pub[:4]) if pub[:4].isdigit() else sug.get("y")
    release_date = pub or (str(year) if year else "")
    poster = (sug.get("i") or {}).get("imageUrl", "")
    douban_id = (wd.get("douban") or {}).get("value", "")
    imdb_rating = _load_imdb_ratings().get(tt_id)
    if imdb_rating is None:
        html = _fetch_html_safe(url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "{}")
                    agg = data.get("aggregateRating") or {}
                    if agg.get("ratingValue") is not None:
                        imdb_rating = float(agg["ratingValue"])
                        break
                except Exception:
                    pass
    return {
        "imdb_id": tt_id,
        "title": title,
        "year": year,
        "release_date": release_date,
        "imdb_rating": imdb_rating,
        "poster": poster,
        "url": url,
        "douban_id": douban_id,
    }
