"""Ripple cover slide: date-led market snapshot.

Layout (1080 x 1350): wordmark with a line-art ripple, the date, the Nifty 50
close with the day's move, a crisp line chart of recent Nifty closes (each
session's segment green when it rose and red when it fell), a strip of other
markets, the top 3 headlines, and a swipe cue.

Data comes only from the Ripple Feed: each `days/<date>` doc has a `snapshot`
list ({label, value, change}) with the previous session's close. History is
rebuilt from those docs (consecutive duplicates = no new session, dropped).
"""
import html as H, re

BG, INK, MUT, DIM, LINE, ACC = "#0F1013", "#E9E9EC", "#A3A6AF", "#6B6E78", "#2A2C33", "#9085e9"
UP, DOWN = "#2FBF71", "#E5484D"
FONT = ("@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600"
        "&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');")


def num(s):
    try: return float(re.sub(r"[^\d.\-]", "", str(s).replace("−", "-")))
    except ValueError: return None


def sign(ch):
    v = num(ch)
    return 0 if v is None or v == 0 else (1 if v > 0 else -1)


def nifty_series(day_docs, max_points=22):
    """day_docs: list of day-doc dicts (any order). Returns [(value, change_str)] oldest first."""
    pts, last = [], None
    for d in sorted(day_docs, key=lambda x: x.get("date", "")):
        n = next((s for s in d.get("snapshot", []) if s.get("label", "").startswith("Nifty 50")), None)
        v = num(n["value"]) if n else None
        if v is None or v == last: continue
        pts.append((v, n.get("change", ""))); last = v
    return pts[-max_points:]


def chart_svg(pts, w=912, h=360):
    if len(pts) < 2: return ""
    vals = [p[0] for p in pts]; lo, hi = min(vals), max(vals); pad = (hi - lo) * .12 or 1
    lo2, hi2 = lo - pad, hi + pad
    X = lambda i: 6 + i * (w - 150) / (len(pts) - 1)
    Yv = lambda v: 14 + (hi2 - v) / (hi2 - lo2) * (h - 52)
    grid = "".join(f"<line x1='0' x2='{w-130}' y1='{Yv(v):.1f}' y2='{Yv(v):.1f}' stroke='{LINE}' stroke-width='2' stroke-dasharray='4 8'/>"
                   f"<text x='{w}' y='{Yv(v)+8:.1f}' text-anchor='end' fill='{DIM}' font-family='JetBrains Mono' font-size='22'>{t} {v:,.0f}</text>"
                   for v, t in ((hi, "H"), (lo, "L")))
    area = f"M{X(0):.1f},{h-38} " + " ".join(f"L{X(i):.1f},{Yv(v):.1f}" for i, v in enumerate(vals)) + f" L{X(len(vals)-1):.1f},{h-38} Z"
    tot = vals[-1] - vals[0]; tc = UP if tot >= 0 else DOWN
    segs = "".join(f"<line x1='{X(i-1):.1f}' y1='{Yv(vals[i-1]):.1f}' x2='{X(i):.1f}' y2='{Yv(vals[i]):.1f}' "
                   f"stroke='{UP if vals[i] >= vals[i-1] else DOWN}' stroke-width='5' stroke-linecap='round'/>"
                   for i in range(1, len(vals)))
    lx, ly = X(len(vals) - 1), Yv(vals[-1])
    return (f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"
            f"<defs><linearGradient id='a' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{tc}' stop-opacity='.22'/>"
            f"<stop offset='1' stop-color='{tc}' stop-opacity='0'/></linearGradient></defs>{grid}"
            f"<path d='{area}' fill='url(#a)'/>{segs}"
            f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='16' fill='{tc}' opacity='.25'/><circle cx='{lx:.1f}' cy='{ly:.1f}' r='8' fill='{tc}'/>"
            f"<text x='0' y='{h-4}' fill='{DIM}' font-family='JetBrains Mono' font-size='22'>{len(vals)} sessions ago</text>"
            f"<text x='{w-130}' y='{h-4}' text-anchor='end' fill='{DIM}' font-family='JetBrains Mono' font-size='22'>last close</text></svg>")


def short_label(s):
    return re.sub(r"\s*\(.*\)", "", s)


def ripple_mark(size=46):
    rings = "".join(f"<circle cx='50' cy='50' r='{r}' fill='none' stroke='{ACC}' stroke-width='5' opacity='{o}'/>" for r, o in ((20, 1), (33, .6), (46, .3)))
    return f"<svg width='{size}' height='{size}' viewBox='0 0 100 100'><circle cx='50' cy='50' r='8' fill='{ACC}'/>{rings}</svg>"


def cover_html(date, snapshot, series, headlines, n_stories):
    e = H.escape
    nif = next((s for s in snapshot if s.get("label", "").startswith("Nifty 50")), None)
    others = [s for s in snapshot if not s.get("label", "").startswith("Nifty 50")][:5]
    big = ""
    if nif:
        sg = sign(nif["change"]); c = UP if sg > 0 else DOWN if sg < 0 else MUT
        arrow = "▲" if sg > 0 else "▼" if sg < 0 else "■"
        span = ""
        if len(series) >= 2:
            pc = (series[-1][0] / series[0][0] - 1) * 100
            span = f"<span class='sp'>{len(series)} sessions <b style='color:{UP if pc >= 0 else DOWN}'>{'+' if pc >= 0 else '−'}{abs(pc):.1f}%</b></span>"
        big = (f"<div class='nf'><div><p class='lab'>{e(nif['label'])}</p><p class='val'>{e(nif['value'])}</p></div>"
               f"<div class='chg'><span class='pill' style='color:{c};border-color:{c}55;background:{c}14'>{arrow} {e(nif['change'])}</span>{span}</div></div>")
    strip = "".join(
        f"<div class='m'><p class='ml'>{e(short_label(s['label']))}</p><p class='mv'>{e(s['value'])}</p>"
        f"<p class='mc' style='color:{UP if sign(s['change']) > 0 else DOWN if sign(s['change']) < 0 else MUT}'>"
        f"{'▲' if sign(s['change']) > 0 else '▼' if sign(s['change']) < 0 else '■'} {e(s['change'])}</p></div>" for s in others)
    hl = "".join(f"<li><span>{i}</span><p>{e(h)}</p></li>" for i, h in enumerate(headlines[:3], 1))
    arcs = "".join(f"<circle cx='1080' cy='0' r='{r}' fill='none' stroke='{ACC}' stroke-width='2' opacity='{o}'/>"
                   for r, o in ((180, .22), (260, .16), (340, .11), (420, .07), (500, .04)))
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{FONT}
*{{box-sizing:border-box;margin:0}}
html,body{{width:1080px;height:1350px;background:{BG};color:{INK};overflow:hidden;font-family:'Hanken Grotesk',sans-serif}}
.bg{{position:absolute;inset:0}}
.wrap{{position:absolute;inset:0;padding:64px 84px 60px;display:flex;flex-direction:column}}
.top{{display:flex;justify-content:space-between;align-items:center;font:500 25px 'JetBrains Mono',monospace;letter-spacing:.16em;text-transform:uppercase;color:{MUT}}}
.brand{{display:flex;align-items:center;gap:16px;color:{INK}}}
.wd{{margin-top:44px;font:500 26px 'JetBrains Mono',monospace;letter-spacing:.2em;text-transform:uppercase;color:{ACC}}}
.date{{font:600 82px/1.02 'Newsreader',serif;letter-spacing:-.01em;margin-top:8px}}
.nf{{margin-top:40px;display:flex;justify-content:space-between;align-items:flex-end}}
.lab{{font:500 24px 'JetBrains Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:{MUT}}}
.val{{font:700 74px/1 'Hanken Grotesk',sans-serif;letter-spacing:-.02em;margin-top:8px}}
.chg{{display:flex;flex-direction:column;align-items:flex-end;gap:10px}}
.pill{{font:500 32px 'JetBrains Mono',monospace;border:2px solid;border-radius:999px;padding:8px 22px}}
.sp{{font:400 22px 'JetBrains Mono',monospace;color:{DIM}}}
.chart{{margin-top:22px}}
.strip{{display:grid;grid-template-columns:repeat(5,1fr);border-top:2px solid {LINE};border-bottom:2px solid {LINE};margin-top:14px}}
.m{{padding:16px 0 16px 14px;border-left:2px solid {LINE}}}.m:first-child{{border-left:0;padding-left:0}}
.ml{{font:500 19px 'JetBrains Mono',monospace;color:{DIM};text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}}
.mv{{font:600 27px 'Hanken Grotesk',sans-serif;margin-top:6px;white-space:nowrap}}
.mc{{font:400 20px 'JetBrains Mono',monospace;margin-top:4px;white-space:nowrap}}
ol{{list-style:none;padding:0;margin-top:14px;display:flex;flex-direction:column;gap:16px}}
li{{display:flex;gap:22px;align-items:baseline}}
li span{{font:500 24px 'JetBrains Mono',monospace;color:{ACC};min-width:30px}}
li p{{font:500 33px/1.2 'Newsreader',serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.eb{{margin-top:30px;font:500 22px 'JetBrains Mono',monospace;letter-spacing:.18em;text-transform:uppercase;color:{ACC}}}
.foot{{margin-top:auto;display:flex;justify-content:space-between;font:400 23px 'JetBrains Mono',monospace;color:{DIM}}}
.foot b{{font-weight:400;color:{ACC}}}
</style></head><body>
<svg class='bg' width='1080' height='1350'>{arcs}</svg>
<div class='wrap'>
 <div class='top'><span class='brand'>{ripple_mark()}Ripple</span><span>Daily market brief</span></div>
 <p class='wd'>{date.strftime('%A')}</p>
 <p class='date'>{date.day} {date.strftime('%B %Y')}</p>
 {big}
 <div class='chart'>{chart_svg(series)}</div>
 <div class='strip'>{strip}</div>
 <p class='eb'>Top stories today</p>
 <ol>{hl}</ol>
 <div class='foot'><span>{n_stories} stories inside · not investment advice</span><b>Swipe →</b></div>
</div></body></html>"""
