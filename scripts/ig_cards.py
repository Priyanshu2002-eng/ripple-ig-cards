#!/usr/bin/env python3
"""Ripple Feed -> Instagram carousel (v2: cover + story slides).

Renders the real Ripple page headless with its database fed from local JSON
dumps (same as capture.py), reads each top Feed card's content from the page
(headline, summary, why it matters, tone, Who moves / Moves this month), then
lays each story out again on a fixed 1080x1350 Instagram template with large
type, so every slide has the same scale. Stories are numbered 1..N with no gaps.

Slide 1 is the cover from cover.py: big date, Nifty 50 close and 3-month chart
(Yahoo Finance ^NSEI daily closes before today; falls back to the Feed's own
snapshots if Yahoo fails or disagrees with the Feed by > 1%), returns row,
market strip, top 3 stories, and one background letter of R-I-P-P-L-E chosen by
how many posts have gone up since 31 Oct 2026 (counted from <posted_dir>).

Writes:
  <out>/ig/slide_00.jpg            cover
  <out>/ig/slide_NN.jpg            story N (N = 1..count)
  <out>/manifest.json              feedDate, date, cards[{n, title, short, source, block, file}]
  <out>/caption.txt                Instagram caption (<= 2,200 chars), numbered 1..N like the slides

usage: python3 ig_cards.py <page.html> <db_dir> <out_dir> [stories=9] [posted_dir]
db_dir layout: <db_dir>/<collection>/<doc_id>.json  (ArtifactData out_dir format)
"""
import json, os, sys, glob, re, html as H, http.server, threading, functools, datetime
from playwright.sync_api import sync_playwright

page_html, db_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
COUNT = int(sys.argv[4]) if len(sys.argv) > 4 else 9
HANDLE = "@ripple__stories"
POSTED_DIR = sys.argv[5] if len(sys.argv) > 5 else None
RIPPLE_START = "2026-10-30"          # first post of the R-I-P-P-L-E letter cycle (the 30 Oct repost, letter E)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cover, subprocess, tempfile

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
      return m ? {name: txt(c.firstChild), val: txt(m), color: m.style.color, node: c.dataset.node || ''} : {more: txt(c)};
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

# ---- trading day or not? ------------------------------------------------------
# NSE is shut on Saturdays, Sundays and exchange holidays. On those days "today" makes no
# sense on a watchlist, so labels name the next session instead ("Monday's watchlist").
# Holidays: add dates here (or pass RIPPLE_CLOSED="YYYY-MM-DD,..."); weekends are automatic.
NSE_HOLIDAYS = set(x.strip() for x in os.environ.get("RIPPLE_CLOSED", "").split(",") if x.strip())
def is_session(d): return d.weekday() < 5 and d.isoformat() not in NSE_HOLIDAYS
MARKET_OPEN = is_session(date)
nxt = date
while not is_session(nxt): nxt += datetime.timedelta(days=1)
WHEN = "today" if MARKET_OPEN else nxt.strftime("%A")
cover.WHEN = WHEN
cover.STORIES_EB = "Top stories today" if MARKET_OPEN else ("This weekend's top stories" if date.weekday() >= 5 else "Top stories · market closed today")

def esc(s): return H.escape(s or "")
def sentences(s): return re.split(r"(?<=[.!?])\s+(?=[A-Z₹$\"'(])", s.strip())
def short(t):
    t = t.split("; ")[0]
    for cut in (" as ", ", but ", " while ", " after ", " even as ", ", on "):
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
.chip{display:inline-flex;align-items:center}
.chip i{display:inline-block;width:20px;height:20px;border-radius:50%;margin-right:16px;flex:0 0 20px}
.chip.up{border-color:#22AB94;background:rgba(34,171,148,.16)}.chip.up i{background:#22AB94}
.chip.down{border-color:#F23645;background:rgba(242,54,69,.15)}.chip.down i{background:#F23645}
.chip.wait{border-color:#3A3D46;color:#C9CBD1}.chip.wait i{border:3px solid #8A8D97}
.eyerow{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:16px}.eyerow .eyebrow{margin-bottom:0}
.legend{font-family:'JetBrains Mono',monospace;font-size:22px;color:var(--dim);display:flex;gap:22px;align-items:center}
.legend span{display:inline-flex;align-items:center;gap:9px}.legend i{display:inline-block;width:14px;height:14px;border-radius:50%}
.cal{font-size:calc(31px*var(--k));line-height:1.35;color:var(--ink);display:flex;gap:14px;margin-top:10px}
.cal .note{color:var(--muted)}
.fx{display:flex;align-items:center;justify-content:space-between;gap:24px;border:2px solid var(--line);background:var(--panel);border-radius:24px;padding:18px 24px}
.fn{font-size:34px;font-weight:700}.ft{font-family:'JetBrains Mono',monospace;font-size:20px;color:var(--dim);margin-top:2px}
.fp{font-size:32px;font-weight:600;margin-top:10px}.fc{font-family:'JetBrains Mono',monospace;font-size:24px}
.fd{font-family:'JetBrains Mono',monospace;font-size:19px;color:var(--dim);margin-top:6px}
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

CUT = float(os.environ.get("RIPPLE_CUT", "10"))
def colour_code(v):
    # Instagram colour cut: score >= +10 green, <= -10 red, otherwise grey (Watch). Chosen 30 Oct 2026 from a 19-session backtest: ±20 was no more accurate than ±10 and greyed out most chips.
    x = cover.num(v) or 0
    return "up" if x >= CUT else "down" if x <= -CUT else "wait"
LEGEND = ("<div class='legend'><span><i style='background:#22AB94'></i>Up</span>"
          "<span><i style='background:#F23645'></i>Down</span>"
          "<span><i style='border:3px solid #8A8D97'></i>Watch</span></div>")

def trim_words(t, maxw):
    # Last-resort shortening for slides that still overflow: cut at a clause boundary
    # (never mid-number), end with a full stop; hard word cut with an ellipsis only if no clause fits.
    t = (t or "").strip()
    if len(t.split()) <= maxw: return t
    best = ""
    for m in re.finditer(r"(?:, | as | while | after | but | even as |; | — )", t):
        head = t[:m.start()].rstrip(" ,;—")
        if len(head.split()) > maxw: break
        if len(head.split()) >= 8: best = head
    if best: return best.rstrip(".") + "."
    return " ".join(t.split()[:maxw]).rstrip(" ,;:—") + "…"

def story_html(n, N, s, nsent, with_cal=True, tight=False):
    sents, summ = sentences(s["summary"]), ""
    for x in sents[:nsent]:
        if summ and len((summ + " " + x).split()) > 42: break
        summ = (summ + " " + x).strip()
    why = s["why"]
    if tight:
        summ = trim_words(summ, 32)
        why = trim_words(sentences(why)[0] if why else why, 28)
    tone_v = s["tone"].replace("−", "-")
    try: tv = float(tone_v)
    except ValueError: tv = 0.0
    w = min(abs(tv), 1) * 50
    bar = f"<i style='{'left' if tv >= 0 else 'right'}:50%;width:{w:.1f}%;background:{s['toneColor'] or 'var(--pos)'}'></i>"
    named = [c for c in s["chips"] if "name" in c]
    extra = sum(int(re.sub(r"\D", "", c["more"]) or 0) for c in s["chips"] if "more" in c)
    show = named[:4]; extra += len(named) - len(show)
    if show:
        chips = "".join(f"<span class='chip {colour_code(c['val'])}'><i></i>{esc(c['name'])}</span>" for c in show)
        if extra: chips += f"<span class='chip' style='color:var(--muted)'>+{extra} more</span>"
        block = f"<div><div class='eyerow'><p class='eyebrow'>Who moves {WHEN if MARKET_OPEN else 'on ' + WHEN}</p>{LEGEND}</div><div class='chips'>{chips}</div></div>"
    elif FOCUS.get(n):
        f = FOCUS[n]; h = f["hist"]; last = h[-1][1]; d1 = cover.pct(last, h[-2][1]); sg = 0 if not d1 else (1 if d1 > 0 else -1)
        cd = h[-1][0]
        cal = ""
        if s["cals"] and with_cal:
            c = s["cals"][0]
            cal = f"<div class='cal'><span class='mono' style='color:{c['color']}'>{esc(c['arrow'])}</span><span>{esc(c['label'])}<span class='note'> — {esc(c['note'])}</span></span></div>"
        block = (f"<div><p class='eyebrow'>In focus</p><div class='fx'><div class='fl'><p class='fn'>{esc(f['name'])}</p>"
                 f"<p class='ft'>{esc(f['tag'])}</p><p class='fp'>{esc(f['fmt'].format(last))}</p>"
                 f"<p class='fc' style='color:{cover.col(sg)}'>{cover.arrow(sg)} {'' if d1 is None else f'{abs(d1):.2f}%'}</p>"
                 f"<p class='fd'>{cd.strftime('%a')} {cd.day} {cd.strftime('%b')} close ┄○</p></div>"
                 f"{cover.spark_svg(h, w=500, h=150)}</div>{cal}</div>")
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
 <p class='why'><b>Why it matters:</b> {esc(why)}</p>
 <div class='tone'><span>Tone</span><span class='bar'>{bar}</span><span class='mono' style='color:{s['toneColor']}'>{esc(s['tone'])}</span></div>
 {block}
</main>
<footer><span class='src'>Source: {esc(source_name(s['src']))}</span><span class='go'>{go}</span></footer>
</div>"""), ("who" if show else "chart" if FOCUS.get(n) else "calendar" if s["cals"] else "none")

# ---- cover data -------------------------------------------------------------------
WARN = []
YNAME = {}
def yahoo_history(before, symbol="%5ENSEI", rng="2y"):
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "y.json")
        r = subprocess.run(["curl", "-s", "-m", "25", "-A", "Mozilla/5.0", "-o", f,
                            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"])
        if r.returncode: raise RuntimeError("curl failed")
        y = json.load(open(f))["chart"]["result"][0]
    YNAME[symbol] = (y.get("meta", {}).get("shortName") or y.get("meta", {}).get("longName") or "").strip()
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return [(datetime.datetime.fromtimestamp(t, ist).date(), c)
            for t, c in zip(y["timestamp"], y["indicators"]["quote"][0]["close"]) if c and datetime.datetime.fromtimestamp(t, ist).date() < before]

day_docs = [v.get("data", v) for k, v in db.items() if k.startswith("days/")]
snap = dd.get("snapshot", [])
feed_nifty = cover.num(next((x["value"] for x in snap if x.get("label", "").startswith("Nifty 50")), None))
try:
    hist = yahoo_history(date)
    if len(hist) < 60 or (date - hist[-1][0]).days > 6: raise RuntimeError("Yahoo history too short or stale")
    if feed_nifty and abs(hist[-1][1] / feed_nifty - 1) > .01: raise RuntimeError(f"Yahoo {hist[-1][1]:.2f} vs Feed {feed_nifty:.2f}")
    hist_src = "yahoo"
except Exception as ex:
    WARN.append(f"Nifty history from Feed snapshots ({ex})")
    hist, hist_src = cover.feed_history([d for d in day_docs if d.get("date", "") <= dd["date"]]), "feed"
post_index = 0
if POSTED_DIR and os.path.isdir(POSTED_DIR):
    post_index = sum(1 for f in os.listdir(POSTED_DIR) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f)
                     and RIPPLE_START <= f[:10] < dd["date"])
else:
    WARN.append("no posted_dir: letter cycle assumed to start today")
LETTER = cover.letter_for(post_index)

# ---- today's watchlist: Indian listed stocks from the stories' "Who moves" ------------
cat = db.get("config/catalog", {}); cat = cat.get("data", cat)
LISTED = {c["id"]: c for c in cat.get("companies", [])
          if c.get("country") == "India" and c.get("ticker") and c["ticker"] != "Unlisted"}
cands = []
for n, s_ in enumerate(stories, 1):
    for ch in s_["chips"]:
        v = cover.num(ch.get("val")) if "name" in ch else None
        if v and ch.get("node") in LISTED:
            c = LISTED[ch["node"]]
            cands.append({"id": c["id"], "name": re.sub(r"\s*\(.*\)", "", c["name"]), "ticker": c["ticker"], "push": int(v), "story": n})
cands.sort(key=lambda c: -abs(c["push"]))
picked, seen_ids, seen_stories = [], set(), set()
for rnd in (0, 1):                                     # one per story first, then fill
    for c in cands:
        if len(picked) >= 4: break
        if c["id"] in seen_ids or (rnd == 0 and c["story"] in seen_stories): continue
        try:
            h = yahoo_history(date, c["ticker"] + ".NS", "3mo")
        except Exception as ex:
            WARN.append(f"no prices for {c['ticker']} ({ex})"); seen_ids.add(c["id"]); continue
        if len(h) < 10 or (date - h[-1][0]).days > 6:
            WARN.append(f"stale prices for {c['ticker']}"); seen_ids.add(c["id"]); continue
        c["hist"] = h; picked.append(c); seen_ids.add(c["id"]); seen_stories.add(c["story"])
picked.sort(key=lambda c: c["story"])
close_date = max((c["hist"][-1][0] for c in picked), default=hist[-1][0] if hist else None)
# ---- "In focus" chart for stories with no Who moves ------------------------------------
# (yahoo symbol, display name, tag, value format, Feed snapshot label prefix)
MACRO = {"T_INR": ("INR=X", "USD/INR", "Rupee per dollar", "₹{:.2f}", "USD/INR"),
         "T_OIL": ("BZ=F", "Brent crude", "Futures · Brent", "${:,.2f}", "Brent"),
         "T_RATES": ("%5ETNX", "US 10-yr yield", "Bond yield · US 10Y", "{:.3f}%", "US 10-yr")}
NIFTY = ("%5ENSEI", "Nifty 50", "Index · NSE", "{:,.2f}", "Nifty 50")
REF_CLOSE = hist[-1][0] if hist else date - datetime.timedelta(days=1)   # date of the previous session's close

def feed_series(prefix):
    """Ripple's own previous-session values for a snapshot label, oldest first (consecutive repeats dropped)."""
    vals, last = [], None
    for d in sorted(day_docs, key=lambda x: x.get("date", "")):
        if d.get("date", "") > dd["date"]: continue
        x = next((s for s in d.get("snapshot", []) if s.get("label", "").startswith(prefix)), None)
        v = cover.num(x["value"]) if x else None
        if v is None or v == last: continue
        vals.append(v); last = v
    return [(REF_CLOSE - datetime.timedelta(days=len(vals) - 1 - i), v) for i, v in enumerate(vals)]

def tidy(name):
    name = re.sub(r"\s+(LTD|LIMITED|Ltd\.?|Limited)$", "", name.strip())
    return " ".join(w if (len(w) <= 4 and w.isupper() and w not in ("BANK", "LIFE", "INDIA")) else w.capitalize() for w in name.split()) if name.isupper() else name
items_by_title = {i.get("title", "").strip(): i for i in dd.get("items", [])}
FOCUS = {}
for n, s_ in enumerate(stories, 1):
    if any("name" in c for c in s_["chips"]): continue
    it = items_by_title.get(s_["title"].strip(), {})
    syms = [x.get("symbol") for x in it.get("nse", []) if x.get("symbol")]
    macro = next((MACRO[t["id"]] for t in it.get("themes", []) if t.get("id") in MACRO), None)
    macro_story = it.get("category") in ("Macro", "Commodities", "Policy") or any(k in (it.get("type") or "") for k in ("Currency", "Oil", "Macro"))
    order = ([macro] if macro and macro_story else []) + [(sym + ".NS", None, "NSE · " + sym, "₹{:,.2f}", None) for sym in syms[:2]] + ([macro] if macro else []) + [NIFTY]
    for sym, name, tag, fmt, feed_label in order:
        h = feed_series(feed_label) if feed_label else []
        src = "feed"
        if len(h) < 8:
            try:
                h, src = yahoo_history(date, sym, "3mo"), "yahoo"
            except Exception as ex:
                WARN.append(f"story {n}: no prices for {sym} ({ex})"); continue
            if len(h) < 10 or (date - h[-1][0]).days > 6: continue
        FOCUS[n] = {"name": name or tidy(YNAME.get(sym, "")) or tag.split(" · ")[-1], "tag": tag, "fmt": fmt, "hist": h, "symbol": sym, "src": src}
        break

COVER_STYLE = os.environ.get("RIPPLE_COVER", "watchlist")   # approved 30 Oct 2026; "nifty" = old chart cover
COVER_KIND = "watchlist" if COVER_STYLE == "watchlist" and len(picked) >= 2 else "nifty"
if COVER_STYLE == "watchlist" and COVER_KIND == "nifty":
    WARN.append(f"only {len(picked)} watchlist stocks with prices: used the Nifty chart cover")
COVER_FIT = "() => document.documentElement.scrollHeight <= 1350"

FIT = "() => { const m=document.getElementById('m'); return m.scrollHeight <= m.clientHeight + 1; }"
os.makedirs(os.path.join(out_dir, "ig"), exist_ok=True)
N = len(stories)
cards = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
    BANNED = ("not in the graph", "not in the catalog", "undefined", "nan%", ">null<", "[object")
    def shot(html, name, ks=(1, .95, .9, .86, .82, .78)):
        low = html.lower()
        bad = next((b for b in BANNED if b in low), None)
        if bad: sys.exit(f"{name}: internal text '{bad}' would appear on the slide")
        for k in ks:
            pg.set_content(html.replace("--k:1", f"--k:{k}"), wait_until="networkidle")
            pg.evaluate("document.fonts.ready")
            if pg.evaluate(FIT): break
        else:
            return False
        pg.screenshot(path=os.path.join(out_dir, "ig", name), type="jpeg", quality=92)
        return True
    heads = [short(x["title"]) for x in stories[:3]]
    if COVER_KIND == "watchlist":
        chtml = cover.watch_cover_html(date, picked, close_date, snap, heads, N, LETTER)
    else:
        chtml = cover.cover_html(date, hist, snap, heads, N, LETTER)
    bad = next((b for b in BANNED if b in chtml.lower()), None)
    if bad: sys.exit(f"cover: internal text '{bad}' would appear on the slide")
    pg.set_content(chtml, wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    if not pg.evaluate(COVER_FIT):
        sys.exit("cover does not fit")
    pg.screenshot(path=os.path.join(out_dir, "ig", "slide_00.jpg"), type="jpeg", quality=92)
    for n, s in enumerate(stories, 1):
        ok = False
        # Long stories: shrink type (down to 78%), then drop the second sentence / calendar line,
        # then as a last resort trim the summary and Why-it-matters at a clause boundary.
        for nsent, wc, tight in ((2, True, False), (1, True, False), (2, False, False), (1, False, False), (1, False, True)):
            html, block = story_html(n, N, s, nsent, wc, tight)
            if shot(html, f"slide_{n:02d}.jpg"):
                ok = True
                if tight: WARN.append(f"story {n}: summary trimmed to fit")
                break
        if not ok:
            sys.exit(f"story {n} does not fit")
        cards.append({"n": n, "title": s["title"], "short": short(s["title"]), "source": source_name(s["src"]),
                      "block": block, "file": f"slide_{n:02d}.jpg"})
    b.close()

with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
    json.dump({"feedDate": day, "date": dd["date"], "cover": "slide_00.jpg", "letter": LETTER, "postIndex": post_index, "coverKind": COVER_KIND,
               "watchlist": [{k: c[k] for k in ("name", "ticker", "push", "story")} | {"lastClose": c["hist"][-1][1], "closeDate": str(c["hist"][-1][0])} for c in picked],
               "niftyHistory": hist_src, "niftyLast": hist[-1][1] if hist else None, "warnings": WARN, "cards": cards},
              fh, indent=2, ensure_ascii=False)
print(json.dumps({"feedDate": day, "n": N, "letter": LETTER, "cover": COVER_KIND, "watchlist": [c["ticker"] for c in picked], "niftyHistory": hist_src, "warnings": WARN,
                  "blocks": {c["n"]: c["block"] for c in cards}}))

# ---- caption: same 1..N numbering as the slides ------------------------------
HEAD = f"Ripple · Today's top {N} market stories · {DSTR}\n\n"
TAIL = ("\n\nSwipe for each story's numbers, tone and who moves " + ("today" if MARKET_OPEN else f"on {WHEN}") + ": green = the news points up, red = the news points down, grey = watch. Summaries of published reports; "
        "sources named on each card. Not investment advice.\n\n"
        "#StockMarketIndia #Nifty50 #Sensex #MarketNews #IndianStocks #Investing #Ripple")
cap = HEAD + "\n".join(f"{c['n']}. {c['title']} — {c['source']}" for c in cards) + TAIL
if len(cap) > 2200:
    cap = HEAD + "\n".join(f"{c['n']}. {c['short']} — {c['source']}" for c in cards) + TAIL
if len(cap) > 2200:
    sys.exit("caption too long")
with open(os.path.join(out_dir, "caption.txt"), "w") as fh:
    fh.write(cap)
