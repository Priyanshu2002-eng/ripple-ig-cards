#!/usr/bin/env python3
"""Ripple Feed -> Instagram cards.

Renders the real Ripple page headless with its database fed from local JSON
dumps, then crops each of the top-10 Feed cards from the card's top edge down to
the end of its "Who moves" block (exactly like the reference screenshots).
Writes:
  <out>/raw/card_NN.png   exact crop (2x, dark theme)
  <out>/ig/card_NN.jpg    same crop on a 4:5 canvas (Instagram's tallest ratio)
  <out>/manifest.json     rank, title, source, url, file names

usage: python3 capture.py <page.html> <db_dir> <out_dir> [count=10]
db_dir layout: <db_dir>/<collection>/<doc_id>.json  (ArtifactData out_dir format)
"""
import json, os, sys, glob, http.server, threading, functools
from playwright.sync_api import sync_playwright
from PIL import Image

page_html, db_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
COUNT = int(sys.argv[4]) if len(sys.argv) > 4 else 10
BG = (15, 16, 20)  # overwritten with the card's real background below

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

manifest = []
with sync_playwright() as p:
    b = p.chromium.launch()
    # 430 CSS px wide at 2x reproduces the phone-width cards in the reference shots
    ctx = b.new_context(viewport={"width": 430, "height": 2200}, device_scale_factor=2, color_scheme="dark")
    pg = ctx.new_page()
    pg.goto(url, wait_until="networkidle", timeout=90000)
    pg.evaluate("document.fonts.ready")
    # Show the Feed view and its Top 10
    pg.evaluate("""() => { const t=[...document.querySelectorAll('button,a')].find(x=>/^\\s*feed\\s*$/i.test(x.textContent)); if(t) t.click(); }""")
    pg.wait_for_timeout(500)
    btn = pg.query_selector('#topN button[data-n="10"]')
    if btn: btn.click()
    pg.wait_for_selector("article.short", timeout=30000)
    pg.wait_for_timeout(1500)
    day = pg.evaluate("() => (document.querySelector('#fDate')||{}).textContent || ''")
    cards = pg.query_selector_all("article.short")[:COUNT]
    if not cards:
        sys.exit("No Feed cards rendered")
    bg = pg.evaluate("() => getComputedStyle(document.querySelector('article.short')).backgroundColor || getComputedStyle(document.body).backgroundColor")
    for n, c in enumerate(cards, 1):
        c.evaluate("el => el.scrollIntoView({block:'start'})")
        pg.wait_for_timeout(250)
        box = c.evaluate("""el => {
            const inner = el.querySelector('.inner'); const r = inner.getBoundingClientRect();
            const eb = [...inner.querySelectorAll('p.eyebrow')].find(p => /who moves/i.test(p.textContent));
            const end = eb ? eb.parentElement.getBoundingClientRect().bottom : inner.querySelector('.tone').getBoundingClientRect().bottom;
            return {x: r.left, y: r.top, w: r.width, bottom: end, hasWho: !!eb};
        }""")
        pad = 14
        clip = {"x": max(0, box["x"] - pad), "y": max(0, box["y"] - pad),
                "width": box["w"] + 2 * pad, "height": box["bottom"] - box["y"] + 2 * pad}
        raw = os.path.join(out_dir, "raw", f"card_{n:02d}.png")
        pg.screenshot(path=raw, clip=clip)
        meta = c.evaluate("""el => ({title:(el.querySelector('.sh')||{}).textContent||'', meta:(el.querySelector('.mrow')||{}).textContent||'', src:((el.querySelector('.mrow')||{lastElementChild:null}).lastElementChild||{}).textContent||''})""")
        manifest.append({"rank": n, "title": meta["title"].strip(), "meta": meta["meta"].strip(), "sourceLine": meta["src"].strip(),
                         "hasWhoMoves": box["hasWho"], "raw": os.path.basename(raw)})
    b.close()
srv.shutdown()

# ---- Instagram carousel JPEGs: every card on the same 1080x1350 (4:5) canvas --
# (Instagram crops every carousel slide to the first slide's ratio, so all match)
CW, CH, M = 1080, 1350, 40
for m in manifest:
    im = Image.open(os.path.join(out_dir, "raw", m["raw"])).convert("RGB")
    fill = im.getpixel((2, 2))
    w, h = im.size
    k = min((CW - 2 * M) / w, (CH - 2 * M) / h)
    im = im.resize((int(w * k), int(h * k)), Image.LANCZOS)
    canvas = Image.new("RGB", (CW, CH), fill)
    canvas.paste(im, ((CW - im.size[0]) // 2, (CH - im.size[1]) // 2))
    jpg = os.path.join(out_dir, "ig", m["raw"].replace(".png", ".jpg"))
    canvas.save(jpg, "JPEG", quality=92, optimize=True)
    m["ig"] = os.path.basename(jpg)
    m["igSize"] = [CW, CH]

with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
    json.dump({"feedDate": day, "cards": manifest}, fh, indent=2, ensure_ascii=False)
print(json.dumps({"feedDate": day, "n": len(manifest), "missingWhoMoves": [m["rank"] for m in manifest if not m["hasWhoMoves"]]}))
