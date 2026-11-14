let DATA = { updated_at: "尚未抓取", people: [], series: [], recent_changes: [] };
let activeTab = "home";
let keyword = "";

function esc(s) {
  return String(s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function matchQ(text) {
  const q = keyword.trim().toLowerCase();
  return !q || String(text || "").toLowerCase().includes(q);
}

function doubanUrl(item) {
  if (item.douban_url) return item.douban_url;
  const q = encodeURIComponent(item.douban_title || item.title || "");
  return `https://search.douban.com/movie/subject_search?search_text=${q}`;
}

function workCard(item, sourceLabel) {
  const zh = item.douban_title ? ` · ${esc(item.douban_title)}` : "";
  const yr = item.year || "待定";
  const roles = (item.roles || []).join(" / ");
  const st = item.production_status || roles || item.title_type || "";
  const isUp = Boolean(item.production_status || !item.year);
  const imdbTxt = item.imdb_rating ? `IMDb ${item.imdb_rating}` : "IMDb 档案";
  const dbTxt = item.douban_rating ? `豆瓣 ${item.douban_rating}` : "豆瓣查看";
  return `
    <div class="work-card">
      <div class="work-top">
        <div>
          <div class="work-title">${esc(item.title)}${zh}</div>
          <div class="work-sub">${esc(sourceLabel)}${st ? " · " + esc(st) : ""}</div>
        </div>
        <span class="pill ${isUp ? "gold" : ""}">${isUp ? "✨ " + yr : yr}</span>
      </div>
      <div class="btn-row">
        <a class="btn-link btn-imdb" href="${esc(item.imdb_url)}" target="_blank" rel="noopener">★ ${imdbTxt}</a>
        <a class="btn-link btn-douban" href="${esc(doubanUrl(item))}" target="_blank" rel="noopener">❀ ${dbTxt}</a>
      </div>
    </div>
  `;
}

function openMuseDrawer(person) {
  const pname = person.display_name || person.name;
  document.getElementById("drawerTitle").textContent = `💫 ${pname}`;
  const works = person.works || [];
  let html = `
    <div class="btn-row" style="margin-bottom:14px;">
      <a class="btn-link btn-imdb" href="${esc(person.imdb_url)}" target="_blank" rel="noopener">★ IMDb 影人主页</a>
      <span class="pill gold">收录 ${works.length} 部作品</span>
    </div>
  `;
  if (!works.length) {
    html += `<div class="empty">暂无作品数据，请点击 GitHub Actions 运行一次抓取。</div>`;
  } else {
    works.slice(0, 40).forEach(w => { html += workCard(w, pname); });
  }
  document.getElementById("drawerBody").innerHTML = html;
  document.getElementById("drawer").classList.add("open");
}

function renderMuseCard(person, idx) {
  const pname = person.display_name || person.name;
  const works = person.works || [];
  const upcomingCount = works.filter(w => w.production_status || !w.year).length;
  const initial = pname.trim().charAt(0).toUpperCase();
  const avatarHtml = person.avatar
    ? `<img class="muse-avatar" src="${esc(person.avatar)}" alt="${esc(pname)}" />`
    : `<div class="muse-avatar">${esc(initial)}</div>`;
  return `
    <div class="muse-card" data-person-idx="${idx}">
      ${avatarHtml}
      <div class="muse-info">
        <div class="muse-name">${esc(pname)}</div>
        <div class="muse-note">${esc(person.notes || "点击展开星光作品全档案")}</div>
        <div class="muse-tags">
          <span class="pill gold">羁绊作品 ${works.length}</span>
          ${upcomingCount ? `<span class="pill">⏳ 待映新作 ${upcomingCount}</span>` : ""}
        </div>
      </div>
    </div>
  `;
}

function render() {
  const app = document.getElementById("app");
  let out = "";

  if (activeTab === "home") {
    const changes = (DATA.recent_changes || []).filter(c => matchQ(c.label + c.type));
    if (changes.length) {
      out += `<div class="chapter-title">✨ 心动速报</div>`;
      changes.forEach(c => { out += `<div class="work-card"><div class="work-title">[${esc(c.type)}] ${esc(c.label)}</div></div>`; });
    }
    const people = (DATA.people || []).filter(p => matchQ((p.display_name || p.name) + (p.notes || "")));
    if (people.length) {
      out += `<div class="chapter-title">💫 羁绊影人</div>`;
      people.forEach((p, idx) => { out += renderMuseCard(p, DATA.people.indexOf(p)); });
    }
    const series = DATA.series || [];
    if (series.length) {
      out += `<div class="chapter-title">📖 影视篇章</div>`;
      series.forEach(s => {
        const es = (s.entries || []).filter(e => matchQ(s.name + e.title + e.douban_title));
        es.forEach(e => { out += workCard(e, `${s.name} · ${s.status || "追踪中"}`); });
      });
    }
  } else if (activeTab === "people") {
    out += `<div class="chapter-title">💫 全部羁绊影人</div>`;
    (DATA.people || []).forEach((p, idx) => {
      if (matchQ((p.display_name || p.name) + (p.notes || ""))) out += renderMuseCard(p, idx);
    });
  } else if (activeTab === "series") {
    (DATA.series || []).forEach(s => {
      const es = (s.entries || []).filter(e => matchQ(s.name + e.title + e.douban_title));
      if (es.length) {
        out += `<div class="chapter-title">📖 ${esc(s.name)}（${esc(s.status || "追踪中")}）</div>`;
        es.forEach(e => { out += workCard(e, s.name); });
      }
    });
  } else if (activeTab === "upcoming") {
    const up = [];
    (DATA.people || []).forEach(p => (p.works || []).forEach(w => {
      if (w.production_status || !w.year) up.push({ item: w, src: p.display_name || p.name });
    }));
    (DATA.series || []).forEach(s => (s.entries || []).forEach(e => {
      if (e.production_status || !e.year) up.push({ item: e, src: s.name });
    }));
    const fl = up.filter(x => matchQ(x.item.title + x.item.douban_title + x.src));
    out += `<div class="chapter-title">⏳ 即将上映 / 制作中档期 (${fl.length})</div>`;
    fl.forEach(x => { out += workCard(x.item, x.src); });
  }

  app.innerHTML = out || `<div class="empty">✨ 暂无匹配档案，试试更换关键词或运行一次更新。</div>`;
  app.querySelectorAll(".muse-card").forEach(el => {
    el.addEventListener("click", () => {
      const idx = Number(el.dataset.personIdx);
      if (!Number.isNaN(idx) && DATA.people[idx]) openMuseDrawer(DATA.people[idx]);
    });
  });
}

document.querySelectorAll(".hud-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".hud-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeTab = btn.dataset.tab;
    render();
  });
});

document.getElementById("searchInput").addEventListener("input", e => {
  keyword = e.target.value;
  render();
});

document.getElementById("closeDrawer").addEventListener("click", () => {
  document.getElementById("drawer").classList.remove("open");
});

document.getElementById("themeToggle").addEventListener("click", () => {
  document.body.classList.toggle("day");
});

fetch("data.json?t=" + Date.now())
  .then(r => (r.ok ? r.json() : null))
  .then(d => {
    if (d) DATA = d;
    document.getElementById("updatedAt").textContent = `✦ 最近同步：${DATA.updated_at || "尚未同步"}`;
    render();
  })
  .catch(() => {
    document.getElementById("updatedAt").textContent = "✦ 正在等待首次数据同步";
    render();
  });
