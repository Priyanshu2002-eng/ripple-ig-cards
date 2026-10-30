"""Ripple cover slide (v4): date + TradingView-style Nifty chart + returns + top stories.

1080 x 1350, dark. Top to bottom:
  * "R." mark + RIPPLE, huge bold date
  * Nifty 50 last close with the day's move
  * full-bleed 3-month daily line chart (one colour: green if the 3 months are
    up, red if down), soft gradient fill, price tag at the last close, month
    labels, and dashed level lines every 500 points running edge to edge
  * period returns row: 1D, 5D, 1M, 3M, YTD, 1Y (green / red)
  * compact strip of other markets from the Feed snapshot
  * the top 3 stories
"Connection" across posts: the price scale is snapped to whole 1,000s of the
3-month range, so neighbouring days share it; the dashed level lines sit at the
same height and run to both edges, and the line fades in from the left edge, so
three covers side by side on the profile grid read as one strip.

History: list of (date, close) oldest first, previous sessions only (from Yahoo
Finance ^NSEI daily; the caller falls back to the Feed's snapshots).
"""
import datetime as dt, html as H, math, re, os

BG, INK, MUT, DIM, LINE, ACC = "#0F1013", "#E9E9EC", "#A3A6AF", "#6B6E78", "#2A2C33", "#9085e9"
UP, DOWN, FLAT = "#22AB94", "#F23645", "#A3A6AF"          # TradingView-like green / red
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
def pct(a, b): return (a / b - 1) * 100 if a and b else None


def feed_history(day_docs):
    """Fallback history from Feed snapshots: [(feed date, close)], consecutive duplicates dropped."""
    out, last = [], None
    for d in sorted(day_docs, key=lambda x: x.get("date", "")):
        n = next((s for s in d.get("snapshot", []) if s.get("label", "").startswith("Nifty 50")), None)
        v = num(n["value"]) if n else None
        if v is None or v == last: continue
        out.append((dt.date.fromisoformat(d["date"]), v)); last = v
    return out


def returns(hist):
    """[(label, pct or None)] for 1D, 5D, 1M, 3M, YTD, 1Y."""
    if len(hist) < 2: return []
    d_last, c_last = hist[-1]
    def on_or_before(day):
        c = [v for d, v in hist if d <= day]
        return c[-1] if c else None
    def months_back(n):
        y, m = d_last.year, d_last.month - n
        while m <= 0: y, m = y - 1, m + 12
        return on_or_before(dt.date(y, m, min(d_last.day, 28)))
    return [("1D", pct(c_last, hist[-2][1])),
            ("5D", pct(c_last, hist[-6][1]) if len(hist) > 5 else None),
            ("1M", pct(c_last, months_back(1))),
            ("3M", pct(c_last, months_back(3))),
            ("YTD", pct(c_last, on_or_before(dt.date(d_last.year - 1, 12, 31)))),
            ("1Y", pct(c_last, on_or_before(d_last.replace(year=d_last.year - 1))))]


def chart_svg(hist, w=1080, h=400, months=3):
    if len(hist) < 2: return ""
    d_last = hist[-1][0]
    y, m = d_last.year, d_last.month - months
    while m <= 0: y, m = y - 1, m + 12
    win = [(d, v) for d, v in hist if d > dt.date(y, m, min(d_last.day, 28))] or hist
    vals = [v for _, v in win]
    lo, hi = math.floor(min(vals) / 1000) * 1000, math.ceil(max(vals) / 1000) * 1000   # sticky scale
    if hi - lo < 1000: hi = lo + 1000
    T, B, R = 44, h - 44, w - 210                       # plot box; right gutter for the axis + price tag
    X = lambda i: i * R / (len(vals) - 1)
    Y = lambda v: T + (hi - v) / (hi - lo) * (B - T)
    c = UP if vals[-1] >= vals[0] else DOWN
    o = [f"<defs><linearGradient id='f' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{c}' stop-opacity='.32'/>"
         f"<stop offset='1' stop-color='{c}' stop-opacity='0'/></linearGradient>"
         f"<linearGradient id='e' x1='0' y1='0' x2='1' y2='0'><stop offset='0' stop-color='#fff' stop-opacity='0'/>"
         f"<stop offset='.07' stop-color='#fff' stop-opacity='1'/></linearGradient><mask id='m'><rect width='{w}' height='{h}' fill='url(#e)'/></mask></defs>"]
    v = lo
    while v <= hi + 1e-6:                                # dashed level lines, edge to edge
        o.append(f"<line x1='0' x2='{w}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' stroke='#2C2F38' stroke-width='2' stroke-dasharray='8 10'/>")
        if v % 1000 == 0 or (hi - lo) <= 2000:
            o.append(f"<text x='{w-84}' y='{Y(v)-10:.1f}' text-anchor='end' opacity='{0 if abs(Y(v) - Y(vals[-1])) < 46 else 1}' fill='{DIM}' font-family='JetBrains Mono' font-size='21'>{v:,.0f}</text>")
        v += 500
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    o.append(f"<g mask='url(#m)'><polygon points='0,{B} {pts} {R:.1f},{B}' fill='url(#f)'/>"
             f"<polyline points='{pts}' fill='none' stroke='{c}' stroke-width='4' stroke-linejoin='round'/></g>")
    seen = set()                                         # month labels at each month's first session
    for i, (d, _) in enumerate(win):
        if d.month not in seen and i > 2:
            o.append(f"<text x='{X(i):.1f}' y='{h-8}' text-anchor='middle' fill='{DIM}' font-family='JetBrains Mono' font-size='21'>{d.strftime('%b')}</text>")
        seen.add(d.month)
    lx, ly = R, Y(vals[-1])
    o.append(f"<line x1='{lx}' x2='{R+16}' y1='{ly:.1f}' y2='{ly:.1f}' stroke='{c}' stroke-width='2' stroke-dasharray='3 5'/>"
             f"<circle cx='{lx}' cy='{ly:.1f}' r='14' fill='{c}' opacity='.25'/><circle cx='{lx}' cy='{ly:.1f}' r='7' fill='{c}'/>"
             f"<rect x='{R+16}' y='{ly-22:.1f}' width='150' height='44' rx='8' fill='{c}'/>"
             f"<text x='{R+91}' y='{ly+8:.1f}' text-anchor='middle' fill='#fff' font-family='JetBrains Mono' font-weight='500' font-size='23'>{vals[-1]:,.2f}</text>")
    return f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>{''.join(o)}</svg>"


WORD = "RIPPLE"
POST_ORDER = WORD[::-1]          # posts go up oldest-first, so E, L, P, P, I, R puts R top-left on the grid


def letter_for(post_index):
    """Letter for the post_index-th post (0-based) of the RIPPLE cycle."""
    return POST_ORDER[post_index % len(POST_ORDER)]


def cover_html(date, hist, snapshot, headlines, n_stories, letter="R"):
    e = H.escape
    last = hist[-1][1] if hist else None
    rets = returns(hist)
    d1 = rets[0][1] if rets else None
    sg = 0 if d1 is None else (1 if d1 > 0 else -1 if d1 < 0 else 0)
    d1s = "" if d1 is None else f"{'+' if d1 >= 0 else '−'}{abs(d1):.2f}%"
    rrow = "".join(f"<div><p class='rl'>{k}</p><p class='rv' style='color:{col(0 if v is None else (1 if v > 0 else -1))}'>"
                   f"{'—' if v is None else ('+' if v >= 0 else '−') + f'{abs(v):.2f}%'}</p></div>" for k, v in rets)
    others = [s for s in snapshot if not s.get("label", "").startswith("Nifty")][:5]
    strip = "".join(f"<div><p class='sl'>{e(short_label(s['label']))}</p><p class='sv'>{e(s['value'])} "
                    f"<b style='color:{col(sign(s['change']))}'>{arrow(sign(s['change']))}{e(s['change'].lstrip('+−-'))}</b></p></div>" for s in others)
    hl = "".join(f"<li><span>{i}</span><p>{e(h)}</p></li>" for i, h in enumerate(headlines[:3], 1))
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{FONT}
*{{box-sizing:border-box;margin:0}}
html,body{{width:1080px;height:1350px;background:{BG};color:{INK};overflow:hidden;font-family:'Hanken Grotesk',sans-serif}}
.wm{{position:absolute;right:70px;top:100px;width:320px;text-align:right;font:360px/1 'Archivo Black',sans-serif;color:transparent;-webkit-text-stroke:4px #3A3558}}
.pad{{padding:0 84px}}
.top{{padding-top:56px;display:flex;justify-content:space-between;align-items:center;font:500 24px 'JetBrains Mono',monospace;letter-spacing:.18em;text-transform:uppercase;color:{MUT}}}
.logo{{display:flex;align-items:center;gap:16px;color:{INK}}}
.logo i{{font:normal 46px/1 'Archivo Black',sans-serif;color:{INK}}}.logo i b{{color:{ACC};font-weight:normal}}
.dt{{display:flex;align-items:flex-end;gap:28px;margin-top:20px}}
.dd{{font:230px/.8 'Archivo Black',sans-serif;letter-spacing:-.05em}}
.dm p{{font:58px/.95 'Archivo Black',sans-serif;text-transform:uppercase}}
.dm .wd{{font:500 25px 'JetBrains Mono',monospace;letter-spacing:.22em;color:{ACC};margin-bottom:12px}}
.dm .yr{{color:{DIM}}}
.nf{{display:flex;align-items:baseline;gap:22px;margin-top:34px}}
.nl{{font:500 23px 'JetBrains Mono',monospace;letter-spacing:.16em;color:{MUT}}}
.nv{{font:700 58px/1 'Hanken Grotesk',sans-serif;letter-spacing:-.02em}}
.pill{{font:500 28px 'JetBrains Mono',monospace;border:2px solid;border-radius:999px;padding:4px 18px}}
.chart{{margin-top:8px}}
.rets{{display:grid;grid-template-columns:repeat(6,1fr);text-align:center;border-top:2px solid {LINE};border-bottom:2px solid {LINE};padding:14px 0}}
.rl{{font:500 20px 'JetBrains Mono',monospace;color:{MUT}}}.rv{{font:500 25px 'JetBrains Mono',monospace;margin-top:4px}}
.strip{{display:grid;grid-template-columns:repeat(5,1fr);margin-top:20px;gap:10px}}
.sl{{font:500 18px 'JetBrains Mono',monospace;color:{DIM};text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}}
.sv{{font:600 23px 'Hanken Grotesk',sans-serif;margin-top:4px;white-space:nowrap}}.sv b{{font:400 18px 'JetBrains Mono',monospace;margin-left:4px}}
.eb{{margin-top:30px;font:500 22px 'JetBrains Mono',monospace;letter-spacing:.18em;text-transform:uppercase;color:{ACC}}}
ol{{list-style:none;padding:0;margin-top:12px;display:flex;flex-direction:column;gap:12px}}
li{{display:flex;gap:22px;align-items:baseline}}li span{{font:500 23px 'JetBrains Mono',monospace;color:{ACC};min-width:28px}}
li p{{font:500 34px/1.2 'Newsreader',serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.foot{{position:absolute;left:84px;right:84px;bottom:50px;display:flex;justify-content:space-between;font:400 22px 'JetBrains Mono',monospace;color:{DIM}}}.foot b{{font-weight:400;color:{ACC}}}
</style></head><body>
<div class='wm'>{e(letter)}</div>
<div class='pad'>
 <div class='top'><span class='logo'><i>R<b>.</b></i>Ripple</span><span>Daily market brief</span></div>
 <div class='dt'><p class='dd'>{date.day:02d}</p><div class='dm'><p class='wd'>{date.strftime('%A').upper()}</p><p>{date.strftime('%B')}</p><p class='yr'>{date.year}</p></div></div>
 <div class='nf'><span class='nl'>NIFTY 50</span><span class='nv'>{'—' if last is None else f'{last:,.2f}'}</span>
  <span class='pill' style='color:{col(sg)};border-color:{col(sg)}66;background:{col(sg)}18'>{arrow(sg)} {d1s}</span></div>
</div>
<div class='chart'>{chart_svg(hist)}</div>
<div class='pad'>
 <div class='rets'>{rrow}</div>
 <div class='strip'>{strip}</div>
 <p class='eb'>Top stories today</p><ol>{hl}</ol>
</div>
<div class='foot'><span>{n_stories} stories inside · not investment advice</span><b>Swipe →</b></div>
</body></html>"""


# =================================================================================
# v5 cover: TODAY'S WATCHLIST (replaces the Nifty chart; v4 cover_html above is the fallback)
# =================================================================================
# The date on the cover is today, but every price is the previous session's close.
# So prices are always labelled with their close date, and the hero is a
# watchlist: the Indian stocks that today's stories are expected to move (Ripple's
# "Who moves" estimate), each with its recent closes as a solid line, a dotted line
# at the last close running on to the tile's edge ("where it ended"), and the size
# and direction of the news pressure. It's Ripple's estimate, not a forecast or advice.

def spark_svg(hist, w=388, h=112, n=22):
    pts = [c for _, c in hist][-n:]
    if len(pts) < 2: return ""
    lo, hi = min(pts), max(pts); pad = (hi - lo) * .12 or 1; lo -= pad; hi += pad
    R = w - 64
    X = lambda i: 4 + i * (R - 4) / (len(pts) - 1)
    Y = lambda v: 8 + (hi - v) / (hi - lo) * (h - 16)
    c = UP if pts[-1] >= pts[0] else DOWN
    line = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(pts))
    lx, ly = X(len(pts) - 1), Y(pts[-1])
    gid = f"g{abs(hash(line)) % 99999}"
    return (f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"
            f"<defs><linearGradient id='{gid}' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{c}' stop-opacity='.28'/>"
            f"<stop offset='1' stop-color='{c}' stop-opacity='0'/></linearGradient></defs>"
            f"<polygon points='4,{h} {line} {lx:.1f},{h}' fill='url(#{gid})'/>"
            f"<polyline points='{line}' fill='none' stroke='{c}' stroke-width='3.5' stroke-linejoin='round'/>"
            f"<line x1='{lx:.1f}' x2='{w-8}' y1='{ly:.1f}' y2='{ly:.1f}' stroke='{INK}' stroke-width='3' stroke-dasharray='2 9' stroke-linecap='round'/>"
            f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='6' fill='{c}'/>"
            f"<circle cx='{w-9}' cy='{ly:.1f}' r='7' fill='{BG}' stroke='{INK}' stroke-width='3'/></svg>")


def watch_tile(t):
    """t: {name, ticker, hist[(date, close)], push (int, signed), story}"""
    e = H.escape
    c_last = t["hist"][-1][1]; c_prev = t["hist"][-2][1] if len(t["hist"]) > 1 else None
    d1 = pct(c_last, c_prev); s1 = 0 if d1 is None else (1 if d1 > 0 else -1 if d1 < 0 else 0)
    p = t["push"]; ps = 1 if p > 0 else -1 if p < 0 else 0
    lvl = "Strong" if abs(p) >= 15 else "Moderate" if abs(p) >= 6 else "Mild"
    cut = float(os.environ.get("RIPPLE_CUT", "10"))
    cc, lab = (UP, "● Up today") if p >= cut else (DOWN, "● Down today") if p <= -cut else (FLAT, "○ Watch")
    return (f"<div class='w'><div class='wh'><p class='wn'>{e(t['name'])}</p><p class='wt'>NSE · {e(t['ticker'])}</p></div>"
            f"<p class='wp'>₹{c_last:,.2f} <span style='color:{col(s1)}'>{arrow(s1)} {'' if d1 is None else f'{abs(d1):.2f}%'}</span></p>"
            f"{spark_svg(t['hist'])}"
            f"<p class='ws'><b style='color:{cc}'>{lab}</b>"
            f"<span>Story #{t['story']}</span></p></div>")


def watch_cover_html(date, watch, close_date, snapshot, headlines, n_stories, letter="R"):
    e = H.escape
    cd = f"{close_date.strftime('%a')} {close_date.day} {close_date.strftime('%b')}" if close_date else "previous session"
    order = ["Nifty 50", "Sensex", "Brent", "USD/INR", "US 10-yr", "Gold"]
    snap = sorted(snapshot, key=lambda s: next((i for i, k in enumerate(order) if s.get("label", "").startswith(k)), 9))[:6]
    strip = "".join(f"<div><p class='sl'>{e(short_label(s['label']))}</p><p class='sv'>{e(s['value'])}</p>"
                    f"<p class='sc' style='color:{col(sign(s['change']))}'>{arrow(sign(s['change']))} {e(s['change'].lstrip('+−-'))}</p></div>" for s in snap)
    tiles = "".join(watch_tile(t) for t in watch[:4])
    hl = "".join(f"<li><span>{i}</span><p>{e(h)}</p></li>" for i, h in enumerate(headlines[:3], 1))
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>{FONT}
*{{box-sizing:border-box;margin:0}}
html,body{{width:1080px;height:1350px;background:{BG};color:{INK};overflow:hidden;font-family:'Hanken Grotesk',sans-serif}}
.wm{{position:absolute;right:76px;top:92px;width:300px;text-align:right;font:270px/1 'Archivo Black',sans-serif;color:transparent;-webkit-text-stroke:4px #3A3558}}
.pad{{position:relative;padding:0 84px}}
.top{{padding-top:56px;display:flex;justify-content:space-between;align-items:center;font:500 24px 'JetBrains Mono',monospace;letter-spacing:.18em;text-transform:uppercase;color:{MUT}}}
.logo{{display:flex;align-items:center;gap:16px;color:{INK}}}
.logo i{{font:normal 46px/1 'Archivo Black',sans-serif;color:{INK}}}.logo i b{{color:{ACC};font-weight:normal}}
.dt{{display:flex;align-items:flex-end;gap:28px;margin-top:20px}}
.dd{{font:210px/.8 'Archivo Black',sans-serif;letter-spacing:-.05em}}
.dm p{{font:54px/.95 'Archivo Black',sans-serif;text-transform:uppercase}}
.dm .wd{{font:500 25px 'JetBrains Mono',monospace;letter-spacing:.22em;color:{ACC};margin-bottom:12px}}
.dm .yr{{color:{DIM}}}
.eh{{margin-top:44px;display:flex;justify-content:space-between;align-items:baseline}}
.eh b{{font:28px 'Archivo Black',sans-serif;letter-spacing:.04em;text-transform:uppercase;font-weight:normal}}
.eh span{{font:400 20px 'JetBrains Mono',monospace;color:{DIM}}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:16px}}
.w{{border:2px solid {LINE};border-radius:24px;padding:18px 20px 16px;background:#14151A}}
.wh{{display:flex;justify-content:space-between;align-items:baseline;gap:10px}}
.wn{{font:700 30px 'Hanken Grotesk',sans-serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.wt{{font:500 17px 'JetBrains Mono',monospace;color:{DIM};white-space:nowrap}}
.wp{{font:600 25px 'Hanken Grotesk',sans-serif;margin:4px 0 6px}}.wp span{{font:500 20px 'JetBrains Mono',monospace;margin-left:6px}}
.ws{{display:flex;justify-content:space-between;margin-top:8px;font:500 19px 'JetBrains Mono',monospace;color:{DIM}}}
.ws b{{font-weight:500}}
.strip{{display:grid;grid-template-columns:repeat(6,1fr);margin-top:22px;border-top:2px solid {LINE};border-bottom:2px solid {LINE};padding:12px 0}}
.sl{{font:500 16px 'JetBrains Mono',monospace;color:{DIM};text-transform:uppercase;white-space:nowrap}}
.sv{{font:600 21px 'Hanken Grotesk',sans-serif;margin-top:2px;white-space:nowrap}}.sc{{font:400 17px 'JetBrains Mono',monospace;white-space:nowrap}}
.eb{{margin-top:22px;font:500 21px 'JetBrains Mono',monospace;letter-spacing:.18em;text-transform:uppercase;color:{ACC}}}
ol{{list-style:none;padding:0;margin-top:8px;display:flex;flex-direction:column;gap:6px}}
li{{display:flex;gap:20px;align-items:baseline}}li span{{font:500 22px 'JetBrains Mono',monospace;color:{ACC};min-width:26px}}
li p{{font:500 31px/1.2 'Newsreader',serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.foot{{position:absolute;left:84px;right:84px;bottom:44px;display:flex;justify-content:space-between;font:400 20px 'JetBrains Mono',monospace;color:{DIM}}}.foot b{{font-weight:400;color:{ACC}}}
</style></head><body>
<div class='wm'>{e(letter)}</div>
<div class='pad'>
 <div class='top'><span class='logo'><i>R<b>.</b></i>Ripple</span><span>Daily market brief</span></div>
 <div class='dt'><p class='dd'>{date.day:02d}</p><div class='dm'><p class='wd'>{date.strftime('%A').upper()}</p><p>{date.strftime('%B')}</p><p class='yr'>{date.year}</p></div></div>
 <div class='eh'><b>Today's watchlist</b><span>prices at {e(cd)} close ┄○</span></div>
 <div class='grid'>{tiles}</div>
 <div class='strip'>{strip}</div>
 <p class='eb'>Top stories today</p><ol>{hl}</ol>
</div>
<div class='foot'><span><b style='color:{UP}'>●</b> Up <b style='color:{DOWN}'>●</b> Down <b style='color:{FLAT}'>○</b> Watch = Ripple's read of today's news, not advice</span><b>Swipe →</b></div>
</body></html>"""
