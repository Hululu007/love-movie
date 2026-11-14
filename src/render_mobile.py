import json
from pathlib import Path

DATA_PATH = Path("data/tracker_data.json")
DOCS_DATA_PATH = Path("docs/data.json")
TRACKER_MD_PATH = Path("TRACKER.md")
README_PATH = Path("README.md")

def _fmt_rating(val):
    return f"⭐ {val}" if val not in (None, "") else "—"

def render_markdown(data):
    lines = []
    updated_at = data.get("updated_at") or "未知"
    lines.append(f"## 🎬 最新追影看板（更新于 {updated_at}）\n")
    changes = data.get("recent_changes") or []
    if changes:
        lines.append("### 🔥 本次新增 / 变动提醒")
        for ch in changes:
            lines.append(f"- **[{ch.get('type')}]** {ch.get('label')}")
        lines.append("")
    upcoming = []
    for p in data.get("people") or []:
        for w in p.get("credits") or p.get("works") or []:
            if w.get("production_status") or not w.get("year"):
                upcoming.append({"source": p.get("display_name") or p.get("name"), **w})
    for s in data.get("series") or []:
        for e in s.get("entries") or []:
            if e.get("production_status") or not e.get("year"):
                upcoming.append({"source": s.get("name"), **e})
    if upcoming:
        lines.append("### ⏳ 即将上映 / 制作中项目")
        lines.append("| 归属 | 片名 | 状态 | 年份 | 链接 |")
        lines.append("| :--- | :--- | :--- | :---: | :--- |")
        for u in upcoming[:20]:
            title_zh = f"（{u['douban_title']}）" if u.get("douban_title") else ""
            status = u.get("production_status") or "待定"
            yr = u.get("year") or "TBD"
            links = f"[IMDb]({u.get('imdb_url')}) / [豆瓣]({u.get('douban_url')})"
            lines.append(f"| {u['source']} | {u.get('title')}{title_zh} | {status} | {yr} | {links} |")
        lines.append("")
    lines.append("### 👤 追影人清单")
    for p in data.get("people") or []:
        pname = p.get("display_name") or p.get("name")
        works = p.get"credits") or p.get("works") or []
        lines.append(f"#### [{pname}]({p.get('imdb_url')})（共 {len(works)} 部）")
        if p.get("notes"):
            lines.append(f"> {p['notes']}\n")
        lines.append("<details>")
        lines.append(f"<summary>点击展开 {pname} 的作品表（最近 15 部）</summary>\n")
        lines.append("| 年份 | 片名 | 职责/状态 | IMDb | 豆瓣 |")
        lines.append("| :---: | :--- | :--- | :---: | :--- |")
        for w in works[:15]:
            yr = w.get("year") or "TBD"
            zh = f" / {w['douban_title']}" if w.get("douban_title") else ""
            roles = ", ".join(w.get("roles") or [])
            if w.get("production_status"):
                roles = f"{roles} ({w['production_status']})" if roles else w["production_status"]
            imdb_cell = f"[{_fmt_rating(w.get('imdb_rating'))}]({w.get('imdb_url')})"
            db_cell = f"[{_fmt_rating(w.get('douban_rating'))}]({w.get('douban_url')})"
            lines.append(f"| {yr} | **{w.get('title')}**{zh} | {roles or '—'} | {imdb_cell} | {db_cell} |")
        lines.append("\n</details>\n")
    lines.append("### 📺 影视系列清单")
    for s in data.get("series") or []:
        lines.append(f"#### {s.get('name')} `{s.get('status') or '追踪中'}`")
        if s.get("notes"):
            lines.append(f"> {s['notes']}\n")
        lines.append("| 年份 | 片名 | 类型/状态 | IMDb | 豆瓣 |")
        lines.append("| :---: | :--- | :--- | :---: | :--- |")
        for e in s.get("entries") or []:
            yr = e.get("year") or "TBD"
            zh = f"（{e['douban_title']}）" if e.get("douban_title") else ""
            meta = e.get("production_status") or e.get("title_type") or "—"
            imdb_cell = f"[{_fmt_rating(e.get('imdb_rating'))}]({e.get('imdb_url')})"
            db_cell = f"[{_fmt_rating(e.get('douban_rating'))}]({e.get('douban_url')})"
            lines.append(f"| {yr} | **{e.get('title')}**{zh} | {meta} | {imdb_cell} | {db_cell} |")
        lines.append("")
    return "\n".join(lines).strip() + "\n"

def update_readme(markdown_body):
    if not README_PATH.exists():
        return
    content = README_PATH.read_text(encoding="utf-8")
    marker = "## 🎬 最新追影看板"
    if marker in content:
        prefix = content.split(marker)[0].rstrip()
        README_PATH.write_text(f"{prefix}\n\n{markdown_body}", encoding="utf-8")
    else:
        README_PATH.write_text(f"{content.rstrip()}\n\n{markdown_body}", encoding="utf-8")

def render_all():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.exists() else {"updated_at": "尚未抓取", "people": [], "series": [], "recent_changes": []}
    md = render_markdown(data)
    TRACKER_MD_PATH.write_text(md, encoding="utf-8")
    update_readme(md)
    DOCS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
if __name__ == "__main__":
    render_all()
