"""
dividend_video.py  —  Dividend ETF comparison video (YouTube Shorts 9:16)
Layout:
  ┌─────────────────────────────────┐
  │  JEPQ header                    │
  │  [Portfolio] [Cash Divs]        │  ← 4 full cards
  │  [Monthly  ] [With DRIP ]       │
  │  [+$12,399 more with DRIP ────] │
  │──────── JEPQ  vs  JEPI ─────────│  ← VS bars
  │  ████████████░░░░  Portfolio    │
  │  ████████░░░░░░░░  Monthly      │
  │  ████████████░░░░  DRIP         │
  │  JEPI header                    │
  │  [Portfolio] [Cash Divs]        │  ← 4 full cards
  │  [Monthly  ] [With DRIP ]       │
  └─────────────────────────────────┘
"""

import os
from datetime import datetime

import cv2
import numpy as np
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont

# ── Settings ───────────────────────────────────────────────────────────────────
WIDTH      = 1080
HEIGHT     = 1920
FPS        = 30
INVESTMENT = 10_000

DIVIDEND_PAIRS = [
    ("JEPQ", "JEPI"),
    ("QYLD", "XYLD"),
    ("SCHD", "VYM"),
    ("O",    "STAG"),
]

# ── Colors ─────────────────────────────────────────────────────────────────────
BG     = (8,   8,   8)
WHITE  = (255, 255, 255)
GREEN  = (0,   215,  55)   # JEPQ color
CYAN   = (0,   200, 220)   # JEPI color
YELLOW = (255, 200,   0)
BLUE   = (80,  160, 255)
ORANGE = (255, 140,   0)
LGRAY  = (130, 130, 130)
DGRAY  = (36,  36,  36)
MGRAY  = (55,  55,  55)

# ── Layout constants ───────────────────────────────────────────────────────────
M   = 34   # horizontal margin
GAP = 14   # gap between cards
CW  = (WIDTH - 2*M - GAP) // 2   # card width (2-col)
CH  = 188  # card height

# ── Font helper ────────────────────────────────────────────────────────────────
_FONT_DIR = "C:/Windows/Fonts/"

def _f(name: str, size: int) -> ImageFont.FreeTypeFont:
    p = _FONT_DIR + name
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()

def _fmt(v: float) -> str:
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v:,.0f}"
    return f"${v:.0f}"

def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * _ease(t)

# ── Draw helpers ───────────────────────────────────────────────────────────────
def _card(draw, x, y, title, val_str, sub, bar_pct, color):
    """Full-size stat card."""
    draw.rounded_rectangle([x, y, x+CW, y+CH], radius=16, fill=DGRAY)
    # progress bar at bottom
    bm, bh = 12, 6
    by = y + CH - bh - bm
    draw.rounded_rectangle([x+bm, by, x+CW-bm, by+bh], radius=3, fill=MGRAY)
    bw = max(0, int((CW - 2*bm) * min(bar_pct, 1.0)))
    if bw > 0:
        draw.rounded_rectangle([x+bm, by, x+bm+bw, by+bh], radius=3, fill=color)
    draw.text((x+16, y+12),  title,   fill=LGRAY, font=_f("arial.ttf",   30))
    draw.text((x+16, y+52),  val_str, fill=color, font=_f("arialbd.ttf", 64))
    draw.text((x+16, y+130), sub,     fill=LGRAY, font=_f("arial.ttf",   26))


def _drip_diff_card(draw, x, y, w, val_str):
    """Single wide card: DRIP difference."""
    h = 88
    draw.rounded_rectangle([x, y, x+w, y+h], radius=16, fill=DGRAY)
    draw.text((x+16, y+10), "DRIP vs No-DRIP",
              fill=LGRAY, font=_f("arial.ttf", 28))
    vw = draw.textlength(val_str, font=_f("arialbd.ttf", 46))
    draw.text(((WIDTH - vw) / 2, y+44), val_str,
              fill=ORANGE, font=_f("arialbd.ttf", 46))


def _vs_bar(draw, x, y, w, lbl_a, val_a, col_a, lbl_b, val_b, col_b, p):
    """Animated proportional bar: A (left) vs B (right)."""
    total = val_a + val_b
    if total == 0:
        return
    ratio_a = val_a / total
    h       = 44
    w_a     = int(w * ratio_a * _ease(p))
    w_b     = int(w * (1 - ratio_a) * _ease(p))

    # background
    draw.rounded_rectangle([x, y, x+w, y+h], radius=10, fill=MGRAY)
    if w_a > 0:
        draw.rounded_rectangle([x,       y, x+w_a,   y+h], radius=10, fill=col_a)
    if w_b > 0:
        draw.rounded_rectangle([x+w-w_b, y, x+w,     y+h], radius=10, fill=col_b)

    fb = _f("arialbd.ttf", 28)
    draw.text((x+10,               y+8), lbl_a, fill=WHITE, font=fb)
    rbw = draw.textlength(lbl_b, font=fb)
    draw.text((x + w - rbw - 10,   y+8), lbl_b, fill=WHITE, font=fb)


def _section_header(draw, y, ticker, color, sub1, sub2):
    """Draw ticker name + subtitle lines. Returns bottom y."""
    tw = draw.textlength(ticker, font=_f("arialbd.ttf", 76))
    draw.text(((WIDTH - tw) / 2, y),      ticker, fill=color, font=_f("arialbd.ttf", 76))
    s1w = draw.textlength(sub1, font=_f("arial.ttf", 36))
    draw.text(((WIDTH - s1w) / 2, y+84),  sub1,   fill=LGRAY, font=_f("arial.ttf", 36))
    s2w = draw.textlength(sub2, font=_f("arial.ttf", 26))
    draw.text(((WIDTH - s2w) / 2, y+130), sub2,   fill=(62, 62, 62), font=_f("arial.ttf", 26))

# ── Data fetcher ───────────────────────────────────────────────────────────────
def _fetch(ticker: str, inv: float, start_date=None) -> dict:
    """
    start_date: if provided, only use data from this date onward.
    This ensures both ETFs in a comparison cover the same time window.
    """
    t    = yf.Ticker(ticker)
    hist = t.history(period="max", auto_adjust=True)
    divs = t.dividends
    if hist.empty:
        raise ValueError(f"No data for {ticker}")

    # Trim to common start date if given
    if start_date is not None:
        hist = hist[hist.index.date >= start_date]
        divs = divs[divs.index.date >= start_date]

    fp   = float(hist["Close"].iloc[0])
    cp   = float(hist["Close"].iloc[-1])
    fd   = hist.index[0].date()
    ld   = hist.index[-1].date()
    sh   = inv / fp

    total_divs    = float(divs.sum()) * sh
    portfolio_val = sh * cp
    monthly_inc   = float(divs.tail(3).mean()) * sh if len(divs) >= 3 else 0.0
    annual_yield  = (monthly_inc * 12) / max(portfolio_val, 1) * 100
    yrs           = (ld - fd).days / 365.25

    # DRIP
    mhist = hist["Close"].resample("ME").last()
    mdivs = divs.resample("ME").sum()
    all_m = mhist.index.union(mdivs.index)
    pr    = mhist.reindex(all_m).ffill().dropna()
    ds    = mdivs.reindex(all_m).fillna(0)

    dsh = inv / float(pr.iloc[0])
    for date in pr.index:
        p2  = float(pr[date])
        div = float(ds.get(date, 0))
        if p2 > 0 and div > 0:
            dsh += (dsh * div) / p2
    drip_val = dsh * cp

    return {
        "ticker": ticker, "inv": inv,
        "first_date": fd, "last_date": ld, "years": yrs,
        "portfolio": portfolio_val, "total_divs": total_divs,
        "monthly": monthly_inc, "annual_yield": annual_yield,
        "drip": drip_val,
    }

# ── Frame renderer ─────────────────────────────────────────────────────────────
def _render(s1: dict, s2: dict, progress: float) -> np.ndarray:
    img  = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # Animation phases — each section reveals sequentially
    p_j  = min(progress * 4,          1.0)   # JEPQ cards
    p_vs = min(max(progress*4-1, 0),  1.0)   # VS bars
    p_i  = min(max(progress*4-2, 0),  1.0)   # JEPI cards

    drip1 = max(s1["drip"], 1)

    # ── JEPQ HEADER ───────────────────────────────────────────────
    note1 = (f"${s1['inv']:,.0f} since {s1['first_date'].strftime('%b %Y')}"
             f"  |  Data as of {s1['last_date'].strftime('%b %d, %Y')}")
    _section_header(draw, 22, s1["ticker"], GREEN, "Monthly Dividend ETF", note1)

    # ── JEPQ CARDS ────────────────────────────────────────────────
    R1 = 178
    R2 = R1 + CH + GAP

    v1 = _lerp(s1["inv"],       s1["portfolio"], p_j)
    v2 = _lerp(0,               s1["total_divs"],p_j)
    v3 = _lerp(0,               s1["monthly"],   p_j)
    v4 = _lerp(s1["inv"],       s1["drip"],      p_j)

    _card(draw, M,        R1, "Portfolio Value", _fmt(v1),
          "Price gain only",             v1/drip1, GREEN)
    _card(draw, M+CW+GAP, R1, "Cash Dividends",  _fmt(v2),
          f"Paid out ({s1['years']:.1f} yrs)",   v2/drip1, YELLOW)
    _card(draw, M,        R2, "Monthly Income",  f"{_fmt(v3)}/mo",
          f"~{s1['annual_yield']:.1f}% yield",    v3/max(s1['monthly']*2,1), BLUE)
    _card(draw, M+CW+GAP, R2, "With DRIP",       _fmt(v4),
          "All divs reinvested",         v4/drip1, ORANGE)

    # DRIP diff card
    diff_y = R2 + CH + GAP
    diff_v = _lerp(0, s1["drip"] - s1["portfolio"], p_j)
    _drip_diff_card(draw, M, diff_y, WIDTH-2*M, f"+{_fmt(diff_v)} more with DRIP")

    # ── VS BARS ───────────────────────────────────────────────────
    vs_y = diff_y + 88 + 22

    # Divider line + "JEPQ vs JEPI"
    draw.line([(M, vs_y+18), (WIDTH-M, vs_y+18)], fill=MGRAY, width=1)
    vs_txt = f"{s1['ticker']}  vs  {s2['ticker']}"
    vtw    = draw.textlength(vs_txt, font=_f("arialbd.ttf", 38))
    draw.rectangle([(WIDTH-vtw)//2 - 14, vs_y+2,
                    (WIDTH+vtw)//2 + 14, vs_y+38], fill=BG)
    draw.text(((WIDTH-vtw)/2, vs_y+2), vs_txt,
              fill=LGRAY, font=_f("arialbd.ttf", 38))

    bars_y = vs_y + 52
    bar_w  = WIDTH - 2*M
    bar_row_h = 76   # label(24) + bar(44) + spacing(8)

    comparisons = [
        ("Portfolio",  s1["portfolio"], s2["portfolio"]),
        ("Monthly/mo", s1["monthly"],   s2["monthly"]),
        ("With DRIP",  s1["drip"],      s2["drip"]),
    ]
    bar_colors = [(GREEN, CYAN), (BLUE, CYAN), (ORANGE, CYAN)]

    for i, ((lbl, va, vb), (ca, cb)) in enumerate(zip(comparisons, bar_colors)):
        by = bars_y + i * bar_row_h
        draw.text((M, by), lbl, fill=LGRAY, font=_f("arial.ttf", 24))
        _vs_bar(draw, M, by+28, bar_w,
                s1["ticker"], va, ca,
                s2["ticker"], vb, cb,
                p_vs)

    # ── JEPI HEADER ───────────────────────────────────────────────
    jepi_hdr_y = bars_y + 3 * bar_row_h + 22
    note2 = (f"${s2['inv']:,.0f} since {s2['first_date'].strftime('%b %Y')}"
             f"  |  Data as of {s2['last_date'].strftime('%b %d, %Y')}")
    _section_header(draw, jepi_hdr_y, s2["ticker"], CYAN, "Monthly Dividend ETF", note2)

    # ── JEPI CARDS ────────────────────────────────────────────────
    drip2 = max(s2["drip"], 1)
    J1 = jepi_hdr_y + 158
    J2 = J1 + CH + GAP

    w1 = _lerp(s2["inv"],  s2["portfolio"], p_i)
    w2 = _lerp(0,          s2["total_divs"],p_i)
    w3 = _lerp(0,          s2["monthly"],   p_i)
    w4 = _lerp(s2["inv"],  s2["drip"],      p_i)

    _card(draw, M,        J1, "Portfolio Value", _fmt(w1),
          "Price gain only",             w1/drip2, GREEN)
    _card(draw, M+CW+GAP, J1, "Cash Dividends",  _fmt(w2),
          f"Paid out ({s2['years']:.1f} yrs)",   w2/drip2, YELLOW)
    _card(draw, M,        J2, "Monthly Income",  f"{_fmt(w3)}/mo",
          f"~{s2['annual_yield']:.1f}% yield",    w3/max(s2['monthly']*2,1), BLUE)
    _card(draw, M+CW+GAP, J2, "With DRIP",       _fmt(w4),
          "All divs reinvested",         w4/drip2, ORANGE)

    # ── DISCLAIMER ────────────────────────────────────────────────
    disc = "Past performance does not guarantee future results. Not financial advice."
    dw   = draw.textlength(disc, font=_f("arial.ttf", 22))
    draw.text(((WIDTH-dw)/2, HEIGHT-38), disc, fill=(44,44,44), font=_f("arial.ttf", 22))

    return np.array(img)

# ── Main ───────────────────────────────────────────────────────────────────────
def create_dividend_video(
    ticker:         str   = "JEPQ",
    compare_ticker: str   = "JEPI",
    investment:     float = INVESTMENT,
    out_path:       str   = None,
) -> dict:
    if out_path is None:
        out_path = f"{ticker}_dividend.mp4"

    print(f"[{ticker} vs {compare_ticker}] Fetching data...")

    # Find the later launch date so both ETFs cover the same period
    def _first_date(tk):
        h = yf.Ticker(tk).history(period="max")
        return h.index[0].date() if not h.empty else None

    d1 = _first_date(ticker)
    d2 = _first_date(compare_ticker)
    common_start = max(d1, d2)   # whichever launched later = fair window
    print(f"  Common start: {common_start}  ({ticker}: {d1}, {compare_ticker}: {d2})")

    s1 = _fetch(ticker,         investment, start_date=common_start)
    s2 = _fetch(compare_ticker, investment, start_date=common_start)

    print(f"  {ticker:<5}  port=${s1['portfolio']:,.0f}  mo=${s1['monthly']:,.0f}  drip=${s1['drip']:,.0f}")
    print(f"  {compare_ticker:<5}  port=${s2['portfolio']:,.0f}  mo=${s2['monthly']:,.0f}  drip=${s2['drip']:,.0f}")

    anim_f = 4 * FPS
    hold_f = 3 * FPS
    total  = anim_f + hold_f
    print(f"  Rendering {total} frames ({total//FPS}s)...")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, FPS, (WIDTH, HEIGHT))

    for i in range(anim_f):
        frame = _render(s1, s2, i / anim_f)
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    for _ in range(hold_f):
        frame = _render(s1, s2, 1.0)
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

    writer.release()
    s1["video_path"]     = out_path
    s1["compare_ticker"] = compare_ticker
    s1["compare"]        = s2
    print(f"  Saved: {out_path}")
    return s1


if __name__ == "__main__":
    import sys
    t1 = sys.argv[1] if len(sys.argv) > 1 else "JEPQ"
    t2 = sys.argv[2] if len(sys.argv) > 2 else "JEPI"
    create_dividend_video(t1, t2)
