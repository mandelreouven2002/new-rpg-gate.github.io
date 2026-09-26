#!/usr/bin/env python3
"""
Prerender the data-driven parts of index.html from data.json.

Search engines and link previews read the HTML as it is served. The home page
used to build its lists in the browser, so crawlers saw empty containers. This
script writes the same markup the page's JavaScript produces straight into
index.html, between <!-- prerender:NAME --> markers, and embeds data.json so the
page can render instantly without waiting for a fetch.

Run it after every change to data.json:
    python3 scripts/prerender.py
The GitHub Action in .github/workflows/prerender.yml runs it automatically.
"""
import datetime, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX, DATA, SITEMAP = ROOT / "index.html", ROOT / "data.json", ROOT / "sitemap.xml"
SITE = "https://gate.roleplay.top/"

MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
TYPE = {"organization": "ארגון/עמותה", "event": "אירוע/כנס", "group": "קהילה/קבוצה", "store": "חנות/ציוד",
        "venue": "מתחם משחקים", "activities": "סדנאות והפעלות", "kids": "חוגי ילדים"}
PIN = '<svg viewBox="0 0 14 14" aria-hidden="true"><path d="M7 13s4.5-4.2 4.5-7.3a4.5 4.5 0 0 0-9 0C2.5 8.8 7 13 7 13z" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="7" cy="5.8" r="1.5" fill="currentColor"/></svg>'
CAL = '<svg viewBox="0 0 14 14" aria-hidden="true"><rect x="1.5" y="2.5" width="11" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M1.5 5.5h11M4.5 1v3M9.5 1v3" stroke="currentColor" stroke-width="1.4"/></svg>'
FLASK = "M10 5H18V18.7A12 12 0 1 1 10 18.7Z"
TAPER = '<svg class="taper" viewBox="0 0 400 5" preserveAspectRatio="none" aria-hidden="true"><polygon points="0,2.5 400,0 400,5"/></svg>'


def esc(v):
    return html.escape(str(v if v is not None else ""), quote=True)


def types_of(item):
    t = item.get("type")
    return t if isinstance(t, list) else [t] if t else []


# ---------- directory entries (mirrors entryHTML in index.html) ----------
def entry(it):
    meta = [f"<span>{esc(', '.join(TYPE.get(t, 'כללי') for t in types_of(it)))}</span>"]
    if it.get("location"):
        meta.append(f"<span>{PIN}{esc(it['location'])}</span>")
    m = it.get("month") or 0
    if 1 <= m <= 12:
        meta.append(f"<span>{CAL}מתקיים ב{MONTHS[m - 1]}</span>")
    return (f'<li><a class="entry" href="{esc(it.get("link"))}" target="_blank" rel="noopener noreferrer">'
            f'<span class="entry-name">{esc(it.get("name"))}</span><span class="entry-meta">{"".join(meta)}</span>'
            f'<p class="entry-desc">{esc(it.get("description"))}</p></a></li>')


# ---------- systems: tabs + stat-block panels ----------
POTION_SHAPES = {
    "round": ("M10 5H18V18.7A12 12 0 1 1 10 18.7Z", "M8.4 4H19.6", "M6 28a8 8 0 0 1 4-7"),
    "tall":  ("M11 5H17V12C21 13 23 16 23 20V39C23 41 21 42 19 42H9C7 42 5 41 5 39V20C5 16 7 13 11 12Z", "M9.4 4H18.6", "M8.5 22V34"),
    "cone":  ("M11 5H17V16L25 38C26 40.5 25 42 22 42H6C3 42 2 40.5 3 38L11 16Z", "M9.4 4H18.6", "M8 31L11 24"),
    "jar":   ("M9 7H19V10C24 12 26 17 26 25C26 35 21 42 14 42C7 42 2 35 2 25C2 17 4 12 9 10Z", "M7.5 6H20.5", "M6 27a8 8 0 0 1 3-8"),
}
# every system gets its own potion: a shape and a brew colour (no difficulty meaning)
POTIONS = {"dnd": ("round", "#D02B45"), "sw": ("tall", "#E9B44C"), "spf": ("cone", "#6FD3BE"), "pbta": ("jar", "#9DB7FF")}


def vial(sid, vid, bubbles=False):
    shape, brew = POTIONS.get(sid, ("round", "#D02B45"))
    body, lip, shine = POTION_SHAPES[shape]
    h = 24
    b = ('<circle class="bubble" cx="11" cy="38" r="1.6"/><circle class="bubble" cx="16" cy="39" r="1.1"/>'
         '<circle class="bubble" cx="14" cy="37" r="1.3"/>') if bubbles else ""
    return (f'<svg class="vial" viewBox="0 0 28 44" aria-hidden="true" style="--brew:{brew}"><defs><clipPath id="vc-{vid}"><path d="{body}"/></clipPath></defs>'
            f'<g clip-path="url(#vc-{vid})"><rect class="liquid" x="0" y="{42.4 - h:.2f}" width="28" height="{h + 1:.2f}"/>{b}</g>'
            f'<path class="glass" d="{body}"/><path class="lip" d="{lip}"/><path class="shine" d="{shine}"/></svg>')


def sys_name(s):
    latin = s.get("latin")
    return esc(s["name"]) + (f' <span style="white-space:nowrap">(<bdi dir="ltr">{esc(latin)}</bdi>)</span>' if latin else "")


def systems(data):
    items = data.get("systemsData") or []
    tabs, panels = [], []
    for i, s in enumerate(items):
        sid, n, first = s["id"], int(s.get("complexity", 0)), i == 0
        tabs.append(
            f'<li role="presentation"><button class="sys-tab" type="button" role="tab" id="tab-{sid}" aria-controls="panel-{sid}" '
            f'aria-selected="{"true" if first else "false"}" tabindex="{0 if first else -1}"><span class="sys-name">{sys_name(s)}</span>'
            f'<span class="sys-badge">{esc(s.get("badge"))}</span><span class="gauge">{vial(sid, "tab-" + sid)}</span></button></li>')
        rows = "".join(
            f'<div><dt>{esc(st["label"])}</dt><dd>'
            + ('<span class="est" title="נתון משוער" aria-hidden="true">≈</span>' if st.get("est") else "")
            + f'<span>{esc(st["value"])}' + ('<span class="sr-only"> (משוער)</span>' if st.get("est") else "") + "</span></dd></div>"
            for st in s.get("stats", []))
        guide = f'<a class="guide-link" href="{esc(s["guide"])}">המדריך המלא על השיטה</a>' if s.get("guide") else ""
        panels.append(
            f'<div class="sys-panel" role="tabpanel" id="panel-{sid}" aria-labelledby="tab-{sid}"{"" if first else " hidden"} tabindex="0">'
            f'<div class="statblock"><div class="sb-head"><div><span class="sys-badge-lg">{esc(s.get("badge"))}</span>'
            f'<span class="sys-logo" data-art="logo-{sid}" role="img" aria-label="הלוגו של {esc(s["name"])}" hidden></span>'
            f'<h3 class="display">{sys_name(s)}</h3><p class="sb-type">{esc(s.get("type"))}</p></div>{vial(sid, "panel-" + sid, True)}</div>'
            f'{TAPER}<dl class="sb-stats">{rows}</dl>{TAPER}</div>'
            f'<div class="sys-side"><div class="why"><strong>למה זה טוב למתחילים?</strong><p>{esc(s.get("why"))}</p></div>'
            f'<div class="actions"><a class="btn btn-solid" href="{esc(s.get("link"))}" target="_blank" rel="noopener noreferrer">למעבר לאתר המשחק</a>{guide}</div></div></div>')
    return (f'<ul class="sys-list" role="tablist" aria-label="שיטות משחק" id="sys-list">{"".join(tabs)}</ul>'
            f'<div id="sys-panels">{"".join(panels)}</div>')


# ---------- phoenix-mail sample updates ----------
def updates(data):
    out = []
    for u in data.get("updatesData", []):
        body = "".join(f"<p>{esc(p)}</p>" for p in u.get("body", []))
        link = (f'<p><a class="update-url" href="{esc(u["link"])}" target="_blank" rel="noopener noreferrer">{esc(u["link"])}</a></p>'
                if u.get("link") else "")
        out.append(f'<li class="update"><p class="update-title">{esc(u.get("title"))}</p>{body}{link}</li>')
    return "".join(out)


# ---------- conventions (mirrors renderCons in index.html) ----------
def events_of(data):
    return [e for e in data.get("communityData", []) if "event" in types_of(e) and 1 <= (e.get("month") or 0) <= 12]


def con(data, today):
    ev = events_of(data)
    m, y = today.month, today.year
    key = lambda e: (y + 1 if e["month"] < m else y, e["month"])
    ev_sorted = sorted(ev, key=key)
    if not ev_sorted:
        return '<div id="con-main"><p class="con-when">אין כנסים קרובים זמינים כרגע.</p></div><div class="con-side" id="con-side"></div>'
    nxt = ev_sorted[0]
    same = [e for e in ev_sorted if e is not nxt and e["month"] == nxt["month"]]
    when = "מתקיים בדרך כלל החודש" if nxt["month"] == m else "מתקיים בדרך כלל ב" + MONTHS[nxt["month"] - 1]
    loc = f' מיקום: {esc(nxt["location"])}.' if nxt.get("location") else ""
    same_html = ('<p class="muted">באותו חודש: ' + ", ".join(f'<a href="{esc(e["link"])}" target="_blank" rel="noopener noreferrer">{esc(e["name"])}</a>' for e in same) + ".</p>") if same else ""
    return (f'<div id="con-main"><p class="con-when muted">{when}</p><p class="con-name"><a href="{esc(nxt["link"])}" target="_blank" rel="noopener noreferrer">{esc(nxt["name"])}</a></p></div>'
            f'<div class="con-side" id="con-side"><p>{esc(nxt.get("description"))}{loc}</p>{same_html}'
            f'<div class="actions"><a class="btn btn-solid" href="{esc(nxt["link"])}" target="_blank" rel="noopener noreferrer">לפרטים באתר הרשמי</a></div></div>')


def year(data, today):
    ev, m = events_of(data), today.month
    nxt = sorted(ev, key=lambda e: (today.year + 1 if e["month"] < m else today.year, e["month"]))[:1]
    out = []
    for i in range(12):
        mo = (m - 1 + i) % 12 + 1
        links = "".join(f'<a href="{esc(e["link"])}" target="_blank" rel="noopener noreferrer"{" class=\"next\"" if nxt and e is nxt[0] else ""}>{esc(e["name"])}</a>'
                        for e in ev if e["month"] == mo)
        now = mo == m
        out.append(f'<li{" class=\"now\" aria-current=\"date\"" if now else ""}><span class="m">{MONTHS[mo - 1]}</span>{links}</li>')
    return "".join(out)


# ---------- structured data for the lists ----------
def ld(data, date):
    def lst(lid, name, items):
        return {"@type": "ItemList", "@id": SITE + "#" + lid, "name": name, "numberOfItems": len(items),
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": it} for i, it in enumerate(items)]}

    games = []
    for s in data.get("systemsData", []):
        g = {"@type": "Game", "name": s["name"], "url": s.get("link"), "description": s.get("description"), "genre": s.get("type")}
        if s.get("latin"):
            g["alternateName"] = s["latin"]
        if s.get("players"):
            g["numberOfPlayers"] = {"@type": "QuantitativeValue", "minValue": s["players"][0], "maxValue": s["players"][1]}
        if s.get("age"):
            g["typicalAgeRange"] = s["age"]
        games.append(g)

    def org(it):
        t = types_of(it)
        kind = "EventSeries" if "event" in t else "Organization"
        o = {"@type": kind, "name": it.get("name"), "url": it.get("link"), "description": it.get("description")}
        if kind == "EventSeries" and it.get("location"):
            o["location"] = {"@type": "Place", "name": it["location"]}
        return o

    def biz(it):
        t = types_of(it)
        kind = "Store" if "store" in t else "EntertainmentBusiness" if "venue" in t else "LocalBusiness"
        b = {"@type": kind, "name": it.get("name"), "url": it.get("link"), "description": it.get("description")}
        if it.get("location"):
            b["areaServed"] = {"@type": "Place", "name": it["location"]}
        return b

    graph = [
        {"@type": "WebPage", "@id": SITE + "#webpage", "dateModified": date},
        lst("systems", "שיטות משחק תפקידים מומלצות למתחילים", games),
        lst("community", "ארגונים, כנסים וקהילות משחקי תפקידים בישראל", [org(i) for i in data.get("communityData", [])]),
        lst("resources", "חנויות, מתחמי משחק וחוגי משחקי תפקידים בישראל", [biz(i) for i in data.get("resourcesData", [])]),
    ]
    body = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1)
    return '<script type="application/ld+json">\n' + body.replace("</", "<\\/") + "\n</script>"


def embed(data):
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="gate-data">{body}</script>'


def fill(doc, name, content):
    pat = re.compile(r"(<!-- prerender:%s -->).*?(<!-- /prerender:%s -->)" % (re.escape(name), re.escape(name)), re.S)
    if not pat.search(doc):
        sys.exit(f"marker not found in index.html: {name}")
    return pat.sub(lambda m: m.group(1) + content + m.group(2), doc, count=1)


def render(doc, data, today, date):
    doc = fill(doc, "systems", systems(data))
    doc = fill(doc, "communityData", "".join(entry(i) for i in data.get("communityData", [])))
    doc = fill(doc, "resourcesData", "".join(entry(i) for i in data.get("resourcesData", [])))
    doc = fill(doc, "updates", updates(data))
    doc = fill(doc, "con", con(data, today))
    doc = fill(doc, "year", year(data, today))
    doc = fill(doc, "data", embed(data))
    doc = fill(doc, "ld", ld(data, date))
    return doc


def render_search(doc, data, today, date):
    items = data.get("communityData", []) + data.get("resourcesData", [])
    doc = fill(doc, "allData", "".join(entry(i) for i in items))
    doc = fill(doc, "data", embed(data))
    return doc


SYSTEM_FILES = ["dungeons_and_dragons", "swords-wizardry", "Savage-Pathfinder", "Apocalypse-World", "pathfinder2", "Savage-Worlds",
                "Blades-in-the-Dark", "call-of-cthulhu", "dungeon-world", "exalted", "tiny-wizards", "malastra", "masks",
                "lasers-feelings", "shadowrun", "warhammer"]


def render_articles(doc, data, today, date):
    """System cards on /articles, read from the markdown guides so they are real links in the HTML."""
    folder = ROOT / "static" / "articles" / "files"
    names = SYSTEM_FILES + sorted(p.stem for p in folder.glob("*.md") if p.stem not in SYSTEM_FILES)
    cards = []
    for name in names:
        f = folder / (name + ".md")
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^#\s+(.+)$", text, re.M)
        title = m.group(1).strip() if m else name.replace("-", " ").replace("_", " ")
        ex = re.search(r"##\s*על השיטה בקצרה\s*\n([\s\S]*?)(?=\n#|$)", text)
        excerpt = re.sub(r"[#*`_\[\]>]", "", ex.group(1)).strip() if ex else ""
        excerpt = " ".join(excerpt.split())
        if len(excerpt) > 220:
            excerpt = excerpt[:220].rsplit(" ", 1)[0] + "…"
        cards.append(f'<li><a class="card" href="/articles/system.html#{esc(name)}"><span class="tag">שיטת משחק</span>'
                     f'<span class="card-title">{esc(title)}</span><p class="card-text">{esc(excerpt)}</p>'
                     f'<span class="card-more">לעמוד השיטה</span></a></li>')
    return fill(doc, "systemCards", "".join(cards))


def render_nextcon(doc, data, today, date):
    doc = fill(doc, "con", con(data, today))
    return fill(doc, "year", year(data, today))


# page file, public URL, renderer
PAGES = [
    (INDEX, SITE, render),
    (ROOT / "search.html", SITE + "search", render_search),
    (ROOT / "articles" / "index.html", SITE + "articles/", render_articles),
    (ROOT / "next-con.html", SITE + "next-con", render_nextcon),
]


def touch_sitemap(url, day):
    if not SITEMAP.exists():
        return
    sm = SITEMAP.read_text(encoding="utf-8")
    if "<loc>" + url + "</loc>" in sm:
        sm = re.sub(r"(<loc>%s</loc>)(\s*<lastmod>[^<]*</lastmod>)?" % re.escape(url),
                    lambda m: m.group(1) + "\n    <lastmod>" + day + "</lastmod>", sm, count=1)
        SITEMAP.write_text(sm, encoding="utf-8")


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    today = datetime.date.today()
    for path, url, fn in PAGES:
        if not path.exists():
            continue
        doc = path.read_text(encoding="utf-8")
        old = re.search(r'"dateModified": "([0-9-]+)"', doc)
        old_date = old.group(1) if old else today.isoformat()
        # Keep the old date if nothing else changed, so the script is idempotent.
        if fn(doc, data, today, old_date) == doc:
            print(path.name, "is up to date")
            continue
        path.write_text(fn(doc, data, today, today.isoformat()), encoding="utf-8")
        touch_sitemap(url, today.isoformat())
        print(path.name, "prerendered", today.isoformat())


if __name__ == "__main__":
    main()
