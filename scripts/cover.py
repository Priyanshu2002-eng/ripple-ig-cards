"""Ripple cover slide (v3): see more, read less.

1080 x 1350, dark. From top to bottom:
  * "R." mark + RIPPLE, and a huge bold date (day number + weekday/month/year)
  * hero chart: recent Nifty 50 closes as a smooth line, each session green
    (up) or red (down), regular dashed guide lines at round levels, a dashed
    5-session average, and a bubble with the last close and the day's move
  * five line-art tiles (Sensex, Brent, USD/INR, US 10-yr, Gold) with value and move
  * a mood gauge (average tone of the day's stories, -1 to +1) next to the #1 story
A large outline "R." sits in the background as line art.

Data comes only from the Ripple Feed: `days/<date>.snapshot` ({label, value,
change}, previous session's close); history = those docs with consecutive
duplicates dropped (no new session).
"""
import html as H, math, re

BG, INK, MUT, DIM, LINE, ACC = "#0F1013", "#E9E9EC", "#A3A6AF", "#6B6E78", "#2A2C33", "#9085e9"
UP, DOWN, FLAT = "#2FBF71", "#E5484D", "#A3A6AF"
FONT = ("@import url('https://fonts.googleapis.com/css2?family=Archivo+Black"
        "&family=Newsreader:opsz,wght@6..72,500;6..72,600&family=Hanken+Grotesk:wght@400;500;600;700"
        "&family=JetBrains+Mono:wght@400;500&display=swap');")


def num(s):
    try: return float(re.sub(r"[^\d.\-]", "", str(s).replace("−", "-")))
    except ValueError: return None


def sign(ch):
    v = num(ch)
    return 0 if v is None or v == 0 else (1 if v > 0 else -1)


def col(sg): return UP if sg > 0 else DOWN if sg < 0 else FLAT
def arrow(sg): return "▲" if sg > 0 else "▼" if sg < 0 else "■"
def short_label(s): return re.sub(r"\s*\(.*\)", "", s)


def nifty_series(day_docs, max_points=22):
    """Nifty 50 closes, oldest first, from Feed day docs (consecutive duplicates dropped)."""
    pts, last = [], None
    for d in sorted(day_docs, key=lambda x: x.get("date", "")):
        n = next((s for s in d.get("snapshot", []) if s.get("label", "").startswith("Nifty 50")), None)
        v = num(n["value"]) if n else None
        if v is None or v == last: continue
        pts.append(v); last = v
    return pts[-max_points:]


# ---- hero chart ----------------------------------------------------------------
def _nice_step(span):
    raw = span / 4
    mag = 10 ** math.floor(math.log10(raw))
    return next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)


def chart_svg(vals, day_change, w=912, h=400):
    if len(vals) < 2: return ""
    lo, hi = min(vals), max(vals)
    step = _nice_step(hi - lo or 1)
    g0, g1 = math.floor(lo / step) * step, math.ceil(hi / step) * step
    if g1 == g0: g1 = g0 + step
    L, R, T, B = 0, w - 120, 30, h - 40
    X = lambda i: L + 8 + i * (R - L - 16) / (len(vals) - 1)
    Y = lambda v: T + (g1 - v) / (g1 - g0) * (B - T)
    out = []
    v = g0
    while v <= g1 + 1e-9:                                   # regular dashed guide lines at round levels
        out.append(f"<line x1='{L}' x2='{R}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' stroke='#30333C' stroke-width='2' stroke-dasharray='6 10'/>"
                   f"<text x='{w}' y='{Y(v)+8:.1f}' text-anchor='end' fill='{DIM}' font-family='JetBrains Mono' font-size='22'>{v:,.0f}</text>")
        v += step
    P = [(X(i), Y(v)) for i, v in enumerate(vals)]
    n = len(P)                                              # monotone cubic (Fritsch-Carlson): no overshoot
    d = [(P[i + 1][1] - P[i][1]) / (P[i + 1][0] - P[i][0]) for i in range(n - 1)]
    m = [d[0]] + [0 if d[i - 1] * d[i] <= 0 else (d[i - 1] + d[i]) / 2 for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if d[i] == 0: m[i] = m[i + 1] = 0; continue
        a, b = m[i] / d[i], m[i + 1] / d[i]
        if a * a + b * b > 9:
            t = 3 / math.sqrt(a * a + b * b); m[i], m[i + 1] = t * a * d[i], t * b * d[i]
    def seg(i):
        (x1, y1), (x2, y2) = P[i - 1], P[i]; dx = (x2 - x1) / 3
        return f"C{x1+dx:.1f},{y1+m[i-1]*dx:.1f} {x2-dx:.1f},{y2-m[i]*dx:.1f} {x2:.1f},{y2:.1f}"
    tc = UP if vals[-1] >= vals[0] else DOWN
    area = f"M{P[0][0]:.1f},{B} L{P[0][0]:.1f},{P[0][1]:.1f} " + " ".join(seg(i) for i in range(1, len(P))) + f" L{P[-1][0]:.1f},{B} Z"
    out.append(f"<defs><linearGradient id='a' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{tc}' stop-opacity='.20'/>"
               f"<stop offset='1' stop-color='{tc}' stop-opacity='0'/></linearGradient></defs><path d='{area}' fill='url(#a)'/>")
    k = 5                                                   # dashed 5-session average
    if len(vals) > k:
        ma = [(X(i), Y(sum(vals[i - k + 1:i + 1]) / k)) for i in range(k - 1, len(vals))]
        out.append(f"<polyline points='{' '.join(f'{x:.1f},{y:.1f}' for x, y in ma)}' fill='none' stroke='{ACC}' stroke-width='3' stroke-dasharray='12 10' opacity='.9'/>")
    for i in range(1, len(P)):
        out.append(f"<path d='M{P[i-1][0]:.1f},{P[i-1][1]:.1f} {seg(i)}' fill='none' stroke='{UP if vals[i] >= vals[i-1] else DOWN}' stroke-width='6' stroke-linecap='round'/>")
    lx, ly = P[-1]; dc = col(sign(day_change))
    out.append(f"<line x1='{lx:.1f}' x2='{lx:.1f}' y1='{ly:.1f}' y2='{B}' stroke='{dc}' stroke-width='2' stroke-dasharray='3 6'/>"
               f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='20' fill='{dc}' opacity='.22'/><circle cx='{lx:.1f}' cy='{ly:.1f}' r='9' fill='{dc}'/>")
    out.append(f"<text x='{L}' y='{h-4}' fill='{DIM}' font-family='JetBrains Mono' font-size='21'>{len(vals)} sessions ago</text>"
               f"<line x1='{R-300}' x2='{R-250}' y1='{h-12}' y2='{h-12}' stroke='{ACC}' stroke-width='3' stroke-dasharray='12 10'/>"
               f"<text x='{R-238}' y='{h-4}' fill='{DIM}' font-family='JetBrains Mono' font-size='21'>5-session avg</text>")
    return f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>{''.join(out)}</svg>"


# ---- line-art icons (stroke only, 64 x 64) ---------------------------------------
def icon(label, c):
    s = f"fill='none' stroke='{c}' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'"
    l = label.lower()
    if "brent" in l or "crude" in l or "oil" in l:
        body = f"<path {s} d='M32 8 C32 8 14 30 14 42 a18 18 0 0 0 36 0 C50 30 32 8 32 8Z'/><path {s} d='M24 44 a8 8 0 0 0 8 8'/>"
    elif "inr" in l or "rupee" in l:
        body = f"<circle {s} cx='32' cy='32' r='24'/><path {s} d='M23 21h18M23 29h18M28 21c10 0 10 14 0 14h-4l14 12'/>"
    elif "10-yr" in l or "yield" in l or "treasury" in l:
        body = f"<rect {s} x='12' y='10' width='40' height='46' rx='5'/><path {s} d='M22 44 L42 24'/><circle {s} cx='24' cy='26' r='3'/><circle {s} cx='40' cy='42' r='3'/>"
    elif "gold" in l:
        body = f"<path {s} d='M10 48 L18 30 H46 L54 48 Z'/><path {s} d='M22 30 L27 18 H37 L42 30'/>"
    else:   # index: candles
        body = (f"<path {s} d='M16 12v40M32 8v44M48 16v36'/><rect {s} x='11' y='22' width='10' height='16' rx='2'/>"
                f"<rect {s} x='27' y='16' width='10' height='24' rx='2'/><rect {s} x='43' y='26' width='10' height='14' rx='2'/>")
    return f"<svg width='58' height='58' viewBox='0 0 64 64'>{body}</svg>"


# ---- mood gauge ----------------------------------------------------------------
def gauge_svg(t, w=250):
    """t in [-1, 1]: average tone of the day's stories."""
    t = max(-1.0, min(1.0, t)); cx, cy, r = w / 2, 128, 100
    def pt(a, rr=r): return cx + rr * math.cos(a), cy - rr * math.sin(a)
    arcs = []
    for a0, a1, c in ((math.pi, math.pi * .62, DOWN), (math.pi * .6, math.pi * .4, FLAT), (math.pi * .38, 0, UP)):
        (x0, y0), (x1, y1) = pt(a0), pt(a1)
        arcs.append(f"<path d='M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {x1:.1f},{y1:.1f}' fill='none' stroke='{c}' stroke-width='14' stroke-linecap='round' opacity='.85'/>")
    a = math.pi * (1 - (t + 1) / 2); nx, ny = pt(a, r - 26)
    word = "Upbeat" if t > .25 else "Mildly positive" if t > .05 else "Downbeat" if t < -.25 else "Mildly negative" if t < -.05 else "Mixed"
    return (f"<svg width='{w}' height='190' viewBox='0 0 {w} 190'>{''.join(arcs)}"
            f"<line x1='{cx}' y1='{cy}' x2='{nx:.1f}' y2='{ny:.1f}' stroke='{INK}' stroke-width='6' stroke-linecap='round'/>"
            f"<circle cx='{cx}' cy='{cy}' r='11' fill='{INK}'/>"
            f"<text x='{cx}' y='178' text-anchor='middle' fill='{INK}' font-family='Hanken Grotesk' font-weight='600' font-size='27'>{word}</text></svg>"), word


def cover_html(date, snapshot, series, top_headline, tone_avg, n_stories):
    e = H.escape
    nif = next((s for s in snapshot if s.get("label", "").startswith("Nifty 50")), None)
    others = [s for s in snapshot if not s.get("label", "").startswith("Nifty 50")][:5]
    dch = nif["change"] if nif else ""
    sg = sign(dch)
    span = ""
    if len(series) >= 2:
        pc = (series[-1] / series[0] - 1) * 100
        span = f"{len(series)} sessions <b style='color:{col(1 if pc > 0 else -1 if pc < 0 else 0)}'>{'+' if pc >= 0 else '−'}{abs(pc):.1f}%</b>"
    tiles = "".join(
        f"<div class='t'>{icon(s['label'], col(sign(s['change'])))}<p class='tl'>{e(short_label(s['label']))}</p>"
        f"<p class='tv'>{e(s['value'])}</p><p class='tc' style='color:{col(sign(s['change']))}'>{arrow(sign(s['change']))} {e(s['change'])}</p></div>"
        for s in others)
    g, _ = gauge_svg(tone_avg)
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{FONT}
*{{box-sizing:border-box;margin:0}}
html,body{{width:1080px;height:1350px;background:{BG};color:{INK};overflow:hidden;font-family:'Hanken Grotesk',sans-serif}}
.wm{{position:absolute;right:-30px;top:-70px;font:600px/1 'Archivo Black',sans-serif;color:transparent;-webkit-text-stroke:3px #1E2027;letter-spacing:-.06em}}
.wrap{{position:absolute;inset:0;padding:56px 84px 54px;display:flex;flex-direction:column}}
.top{{display:flex;justify-content:space-between;align-items:center;font:500 24px 'JetBrains Mono',monospace;letter-spacing:.18em;text-transform:uppercase;color:{MUT}}}
.logo{{display:flex;align-items:center;gap:16px;color:{INK}}}
.logo i{{font:normal 46px/1 'Archivo Black',sans-serif;letter-spacing:-.02em;color:{INK}}}.logo i b{{color:{ACC};font-weight:normal}}
.dt{{display:flex;align-items:flex-end;gap:30px;margin-top:22px}}
.dd{{font:250px/.8 'Archivo Black',sans-serif;letter-spacing:-.05em}}
.dm p{{font:62px/.95 'Archivo Black',sans-serif;letter-spacing:-.01em;text-transform:uppercase}}
.dm .wd{{font:500 26px 'JetBrains Mono',monospace;letter-spacing:.22em;color:{ACC};margin-bottom:12px}}
.dm .yr{{color:{DIM}}}
.nf{{display:flex;justify-content:space-between;align-items:flex-end;margin-top:40px}}
.nl{{font:500 23px 'JetBrains Mono',monospace;letter-spacing:.16em;color:{MUT}}}
.nv{{font:700 64px/1 'Hanken Grotesk',sans-serif;letter-spacing:-.02em;margin-top:8px}}
.nc{{text-align:right}}
.pill{{display:inline-block;font:500 32px 'JetBrains Mono',monospace;border:2px solid;border-radius:999px;padding:6px 22px}}
.sp{{font:400 22px 'JetBrains Mono',monospace;color:{DIM};margin-top:10px}}
.chart{{margin-top:8px}}
.tiles{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-top:20px}}
.t{{border:2px solid {LINE};border-radius:22px;padding:16px 10px 14px;display:flex;flex-direction:column;align-items:center;background:#14151A}}
.tl{{font:500 18px 'JetBrains Mono',monospace;color:{DIM};letter-spacing:.06em;text-transform:uppercase;margin-top:8px;white-space:nowrap}}
.tv{{font:600 25px 'Hanken Grotesk',sans-serif;margin-top:4px;white-space:nowrap}}
.tc{{font:400 19px 'JetBrains Mono',monospace;margin-top:2px;white-space:nowrap}}
.low{{margin-top:auto;display:flex;gap:30px;align-items:center;border-top:2px solid {LINE};padding-top:22px}}
.ml{{font:500 19px 'JetBrains Mono',monospace;color:{DIM};letter-spacing:.12em;text-transform:uppercase;text-align:center;margin-bottom:-6px}}
.hl{{flex:1}}
.k{{font:500 22px 'JetBrains Mono',monospace;letter-spacing:.18em;color:{ACC}}}
.h{{font:600 40px/1.15 'Newsreader',serif;margin-top:10px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.s{{margin-top:14px;display:flex;justify-content:space-between;font:400 22px 'JetBrains Mono',monospace;color:{DIM}}}.s b{{font-weight:400;color:{ACC}}}
</style></head><body>
<div class='wm'>R.</div>
<div class='wrap'>
 <div class='top'><span class='logo'><i>R<b>.</b></i>Ripple</span><span>Daily market brief</span></div>
 <div class='dt'><p class='dd'>{date.day:02d}</p><div class='dm'><p class='wd'>{date.strftime('%A').upper()}</p><p>{date.strftime('%B')}</p><p class='yr'>{date.year}</p></div></div>
 <div class='nf'><div><p class='nl'>NIFTY 50</p><p class='nv'>{e(nif['value']) if nif else '—'}</p></div>
  <div class='nc'><span class='pill' style='color:{col(sg)};border-color:{col(sg)}66;background:{col(sg)}18'>{arrow(sg)} {e(dch)}</span><p class='sp'>{span}</p></div></div>
 <div class='chart'>{chart_svg(series, dch)}</div>
 <div class='tiles'>{tiles}</div>
 <div class='low'><div><p class='ml'>Story mood</p>{g}</div>
  <div class='hl'><p class='k'>TODAY'S #1</p><p class='h'>{e(top_headline)}</p><p class='s'><span>{n_stories} stories inside</span><b>Swipe →</b></p></div></div>
</div></body></html>"""
