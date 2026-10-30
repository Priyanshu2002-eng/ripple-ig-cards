#!/usr/bin/env python3
"""Ripple Feed -> Instagram carousel (v2: cover + story slides).

Renders the real Ripple page headless with its database fed from local JSON
dumps (same as capture.py), reads each top Feed card's content from the page
(headline, summary, why it matters, tone, Who moves / Moves this month), then
lays each story out again on a fixed 1080x1350 Instagram template with large
type, so every slide has the same scale. Slide 1 is a cover: date, the day's
mood line and the top headlines. Stories are numbered 1..N with no gaps.

Writes:
  <out>/ig/slide_00.jpg            cover
  <out>/ig/slide_NN.jpg            story N (N = 1..count)
  <out>/manifest.json              feedDate, date, cards[{n, title, short, source, block, file}]
  <out>/caption.txt                Instagram caption (<= 2,200 chars), numbered 1..N like the slides

usage: python3 ig_cards.py <page.html> <db_dir> <out_dir> [stories=9]
db_dir layout: <db_dir>/<collection>/<doc_id>.json  (ArtifactData out_dir format)
"""
import json, os, sys, glob, re, html as H, http.server, threading, functools, datetime
from playwright.sync_api import sync_playwright

page_html, db_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
COUNT = int(sys.argv[4]) if len(sys.argv) > 4 else 9
HANDLE = "@ripple__stories"

# ---- load the db dump -------------------------------------------------------
db = {}
for f in glob.glob(os.path.join(db_dir, "**", "*.json"), recursive=True):
    rel = os.path.relpath(f, db_dir)[:-5]          # e.g. days/2026-10-29
    with open(f) as fh:
        d = json.load(fh)
    d.pop("version", None)
    db[rel.replace(os.sep, "/")] = d

STUB = """
<script>
(function(){
  const DB = %s;
  const snapDoc = p => ({id:p.split('/').pop(), exists: p in DB, data: () => DB[p] ? JSON.parse(JSON.stringify(DB[p])) : undefined});
  function coll(path){
    let ord=null, lim=1e9;
    const q = {
      orderBy(f, dir){ ord=[f, dir||'asc']; return q; },
      limit(n){ lim=n; return q; },
      where(){ return q; },
      doc(id){ return docRef(path+'/'+id); },
      _docs(){
        let ds = Object.keys(DB).filter(k => k.startsWith(path+'/') && k.split('/').length===path.split('/').length+1).map(snapDoc);
        if(ord) ds.sort((a,b)=>{const x=a.data()[ord[0]], y=b.data()[ord[0]]; const c = x<y?-1:x>y?1:0; return ord[1]==='desc'?-c:c;});
        return ds.slice(0, lim);
      },
      onSnapshot(cb){ setTimeout(()=>{const docs=q._docs(); cb({docs, size:docs.length, empty:!docs.length, forEach:f=>docs.forEach(f)});},0); return ()=>{}; },
      async get(){ const docs=q._docs(); return {docs, size:docs.length, empty:!docs.length, forEach:f=>docs.forEach(f)}; },
    };
    return q;
  }
  function docRef(p){ return {id:p.split('/').pop(), onSnapshot(cb){setTimeout(()=>cb(snapDoc(p)),0); return ()=>{};}, async get(){return snapDoc(p);}, async set(){}, async update(){}, async delete(){}, collection(c){return coll(p+'/'+c);} }; }
  const db = { collection: coll, doc: docRef };
  window.claude = { use: async name => name==='db' ? db : null };
  try { localStorage.clear(); } catch(e) {}
  document.documentElement.setAttribute('data-theme','dark');
})();
</script>
""" % json.dumps(db)

html = open(page_html, encoding="utf8").read()
html = html.replace("<head>", "<head>" + STUB, 1)

os.makedirs(os.path.join(out_dir, "raw"), exist_ok=True)
os.makedirs(os.path.join(out_dir, "ig"), exist_ok=True)
serve_dir = os.path.join(out_dir, "_serve")
os.makedirs(serve_dir, exist_ok=True)
with open(os.path.join(serve_dir, "index.html"), "w", encoding="utf8") as fh:
    fh.write(html)

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=serve_dir)
handler.log_message = lambda *a, **k: None
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"

EXTRACT = r"""el => {
  const q = s => el.querySelector(s), txt = n => (n ? n.textContent : '').replace(/\s+/g, ' ').trim();
  const mrow = q('.mrow');
  const tags = [...mrow.querySelectorAll('.tag')].map(txt);
  const src = txt(mrow.lastElementChild);
  const blocks = [...el.querySelectorAll('.inner > div')].filter(d => d.querySelector(':scope > p.eyebrow'));
  const blk = re => blocks.find(d => re.test(txt(d.querySelector('p.eyebrow'))));
  const who = blk(/who moves/i), cal = blk(/moves this month/i);
  const chips = who ? [...who.querySelectorAll('.chip')].map(c => {
      const m = c.querySelector('.mono');
      return m ? {name: txt(c.firstChild), val: txt(m), color: m.style.color} : {more: txt(c)};
  }) : [];
  const cals = cal ? [...cal.querySelectorAll('.chip')].map(c => {
      const m = c.querySelector('.mono'), mu = c.querySelector('.muted');
      let label = txt(c); if (m) label = label.replace(txt(m), ''); if (mu) label = label.replace(txt(mu), '');
      return {arrow: txt(m), color: m ? m.style.color : '', label: label.trim(), note: txt(mu).replace(/^—\s*/, '')};
  }) : [];
  const tone = q('.tone .mono');
  return {tags, src, title: txt(q('.sh')), summary: txt(q('.ss')),
          why: txt(q('.whyit')).replace(/^Why it matters:\s*/i, ''),
          tone: txt(tone), toneColor: tone ? tone.style.color : '', chips, cals};
}"""

stories = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 430, "height": 2200}, color_scheme="dark")
    pg.goto(url, wait_until="networkidle", timeout=90000)
    pg.evaluate("""() => { const t=[...document.querySelectorAll('button,a')].find(x=>/^\\s*feed\\s*$/i.test(x.textContent)); if(t) t.click(); }""")
    pg.wait_for_timeout(500)
    btn = pg.query_selector('#topN button[data-n="10"]')
    if btn: btn.click()
    pg.wait_for_selector("article.short", timeout=30000)
    pg.wait_for_timeout(1500)
    day = pg.evaluate("() => (document.querySelector('#fDate')||{}).textContent || ''").strip()
    for c in pg.query_selector_all("article.short")[:COUNT]:
        stories.append(c.evaluate(EXTRACT))
    b.close()
srv.shutdown()
if not stories:
    sys.exit("No Feed cards rendered")

# ---- the day's doc (date + mood) ---------------------------------------------
days = sorted(k for k in db if k.startswith("days/"))
dd = db[days[-1]]; dd = dd.get("data", dd)
date = datetime.date.fromisoformat(dd["date"])
mood = dd.get("mood", "")

def esc(s): return H.escape(s or "")
def sentences(s): return re.split(r"(?<=[.!?])\s+(?=[A-Z₹$\"'(])", s.strip())
def short(t):
    t = t.split("; ")[0]
    for cut in (" as ", ", but ", " while ", " after ", " even as "):
        if len(t) > 62 and cut in t: t = t.split(cut)[0]
    return t.rstrip(" ,.;")
def source_name(s): return s.split(" · ")[0].strip()

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--bg:#0F1013;--panel:#17181D;--line:#2A2C33;--ink:#E9E9EC;--muted:#A3A6AF;--dim:#6B6E78;--accent:#9085e9;--pos:#3987e5;--neg:#d95926;--k:1}
*{box-sizing:border-box;margin:0}
html,body{width:1080px;height:1350px;background:var(--bg);color:var(--ink);font-family:'Hanken Grotesk',sans-serif;overflow:hidden}
.slide{width:1080px;height:1350px;padding:72px 84px 64px;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:center;font-family:'JetBrains Mono',monospace;font-size:26px;color:var(--dim);letter-spacing:.14em;text-transform:uppercase}
.brand{color:var(--accent);font-weight:500}
main{flex:1;min-height:0;margin:36px 0 28px;display:flex;flex-direction:column;justify-content:center;gap:calc(34px*var(--k));overflow:hidden}
.meta{display:flex;gap:16px;align-items:center}
.rank{font-family:'Newsreader',serif;font-size:64px;color:var(--accent);line-height:1;margin-right:8px}
.tag{font-family:'JetBrains Mono',monospace;font-size:26px;border:2px solid var(--line);border-radius:14px;padding:8px 16px;color:var(--muted)}
h1{font-family:'Newsreader',serif;font-weight:600;font-size:calc(64px*var(--k));line-height:1.1;letter-spacing:-.01em}
.sum{font-size:calc(37px*var(--k));line-height:1.42;color:var(--ink)}
.why{font-size:calc(34px*var(--k));line-height:1.4;color:var(--muted);border-left:6px solid var(--accent);padding-left:26px}
.why b{color:var(--ink)}
.tone{display:flex;align-items:center;gap:22px;font-size:30px;color:var(--muted)}
.bar{flex:0 0 340px;height:16px;border-radius:8px;background:var(--panel);position:relative}
.bar i{position:absolute;top:0;bottom:0;border-radius:8px}
.bar:after{content:'';position:absolute;left:50%;top:-6px;bottom:-6px;width:3px;background:var(--dim)}
.mono{font-family:'JetBrains Mono',monospace}
.eyebrow{font-family:'JetBrains Mono',monospace;font-size:26px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);margin-bottom:16px}
.chips{display:flex;flex-wrap:wrap;gap:14px}
.chip{font-size:calc(33px*var(--k));border:2px solid var(--line);background:var(--panel);border-radius:999px;padding:10px 24px;white-space:nowrap}
.chip .mono{margin-left:12px}
.cal{font-size:calc(31px*var(--k));line-height:1.35;color:var(--ink);display:flex;gap:14px;margin-top:10px}
.cal .note{color:var(--muted)}
footer{display:flex;justify-content:space-between;align-items:flex-end;gap:30px;font-family:'JetBrains Mono',monospace;font-size:24px;color:var(--dim);border-top:2px solid var(--line);padding-top:26px}
footer .src{max-width:780px;line-height:1.35}
footer .go{color:var(--accent);white-space:nowrap}
/* cover */
.date{font-family:'Newsreader',serif;font-weight:600;font-size:118px;line-height:1;letter-spacing:-.02em}
.wd{font-family:'JetBrains Mono',monospace;font-size:30px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);margin-bottom:18px}
.mood{font-size:34px;line-height:1.42;color:var(--muted)}
ol{list-style:none;padding:0;display:flex;flex-direction:column;gap:22px}
ol li{display:flex;gap:26px;font-family:'Newsreader',serif;font-weight:500;font-size:calc(42px*var(--k));line-height:1.18}
ol li span{font-family:'JetBrains Mono',monospace;color:var(--accent);font-size:32px;min-width:44px;padding-top:6px}
.more{font-size:30px;color:var(--muted)}
"""

def page(body): return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
DSTR = f"{date.day} {date.strftime('%b %Y')}"

def story_html(n, N, s, nsent):
    sents, summ = sentences(s["summary"]), ""
    for x in sents[:nsent]:
        if summ and len((summ + " " + x).split()) > 42: break
        summ = (summ + " " + x).strip()
    tone_v = s["tone"].replace("−", "-")
    try: tv = float(tone_v)
    except ValueError: tv = 0.0
    w = min(abs(tv), 1) * 50
    bar = f"<i style='{'left' if tv >= 0 else 'right'}:50%;width:{w:.1f}%;background:{s['toneColor'] or 'var(--pos)'}'></i>"
    named = [c for c in s["chips"] if "name" in c]
    extra = sum(int(re.sub(r"\D", "", c["more"]) or 0) for c in s["chips"] if "more" in c)
    show = named[:4]; extra += len(named) - len(show)
    if show:
        chips = "".join(f"<span class='chip'>{esc(c['name'])}<span class='mono' style='color:{c['color']}'>{esc(c['val'])}</span></span>" for c in show)
        if extra: chips += f"<span class='chip' style='color:var(--muted)'>+{extra} more</span>"
        block = f"<div><p class='eyebrow'>Who moves</p><div class='chips'>{chips}</div></div>"
    elif s["cals"]:
        rows = "".join(f"<div class='cal'><span class='mono' style='color:{c['color']}'>{esc(c['arrow'])}</span><span>{esc(c['label'])}<span class='note'> — {esc(c['note'])}</span></span></div>" for c in s["cals"][:2])
        block = f"<div><p class='eyebrow'>On the calendar</p>{rows}</div>"
    else:
        block = ""
    tags = "".join(f"<span class='tag'>{esc(t)}</span>" for t in s["tags"])
    go = "Swipe →" if n < N else HANDLE
    return page(f"""<div class='slide'>
<div class='top'><span class='brand'>Ripple</span><span>{n} / {N} · {DSTR}</span></div>
<main id='m'>
 <div class='meta'><span class='rank'>#{n}</span>{tags}</div>
 <h1>{esc(s['title'])}</h1>
 <p class='sum'>{esc(summ)}</p>
 <p class='why'><b>Why it matters:</b> {esc(s['why'])}</p>
 <div class='tone'><span>Tone</span><span class='bar'>{bar}</span><span class='mono' style='color:{s['toneColor']}'>{esc(s['tone'])}</span></div>
 {block}
</main>
<footer><span class='src'>Source: {esc(source_name(s['src']))}</span><span class='go'>{go}</span></footer>
</div>"""), ("who" if show else "calendar" if s["cals"] else "none")

def cover_html(N, k_items):
    items = "".join(f"<li><span>{i}</span>{esc(short(s['title']))}</li>" for i, s in enumerate(stories[:k_items], 1))
    more = f"<p class='more'>+ {N - k_items} more stories inside</p>" if N > k_items else ""
    return page(f"""<div class='slide'>
<div class='top'><span class='brand'>Ripple</span><span>Daily market brief</span></div>
<main id='m' style='justify-content:flex-start;padding-top:40px'>
 <div><p class='wd'>{date.strftime('%A')}</p><p class='date'>{DSTR}</p></div>
 <p class='mood'>{esc(mood)}</p>
 <div><p class='eyebrow'>Today's top {N}</p><ol>{items}</ol></div>
 {more}
</main>
<footer><span class='src'>Summaries of published reports · Not advice</span><span class='go'>Swipe →</span></footer>
</div>""")

FIT = "() => { const m=document.getElementById('m'); return m.scrollHeight <= m.clientHeight + 1; }"
os.makedirs(os.path.join(out_dir, "ig"), exist_ok=True)
N = len(stories)
cards = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
    def shot(html, name, ks=(1, .95, .9, .86)):
        for k in ks:
            pg.set_content(html.replace("--k:1", f"--k:{k}"), wait_until="networkidle")
            pg.evaluate("document.fonts.ready")
            if pg.evaluate(FIT): break
        else:
            return False
        pg.screenshot(path=os.path.join(out_dir, "ig", name), type="jpeg", quality=92)
        return True
    for kk in (5, 4, 3):
        if shot(cover_html(N, min(kk, N)), "slide_00.jpg"): break
    else:
        sys.exit("cover does not fit")
    for n, s in enumerate(stories, 1):
        ok = False
        for nsent in (2, 1):
            html, block = story_html(n, N, s, nsent)
            if shot(html, f"slide_{n:02d}.jpg"): ok = True; break
        if not ok:
            sys.exit(f"story {n} does not fit")
        cards.append({"n": n, "title": s["title"], "short": short(s["title"]), "source": source_name(s["src"]),
                      "block": block, "file": f"slide_{n:02d}.jpg"})
    b.close()

with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
    json.dump({"feedDate": day, "date": dd["date"], "cover": "slide_00.jpg", "cards": cards}, fh, indent=2, ensure_ascii=False)
print(json.dumps({"feedDate": day, "n": N, "blocks": {c["n"]: c["block"] for c in cards}}))

# ---- caption: same 1..N numbering as the slides ------------------------------
HEAD = f"Ripple · Today's top {N} market stories · {DSTR}\n\n"
TAIL = ("\n\nSwipe for each story's numbers, tone and who moves. Summaries of published reports; "
        "sources named on each card. Not investment advice.\n\n"
        "#StockMarketIndia #Nifty50 #Sensex #MarketNews #IndianStocks #Investing #Ripple")
cap = HEAD + "\n".join(f"{c['n']}. {c['title']} — {c['source']}" for c in cards) + TAIL
if len(cap) > 2200:
    cap = HEAD + "\n".join(f"{c['n']}. {c['short']} — {c['source']}" for c in cards) + TAIL
if len(cap) > 2200:
    sys.exit("caption too long")
with open(os.path.join(out_dir, "caption.txt"), "w") as fh:
    fh.write(cap)
