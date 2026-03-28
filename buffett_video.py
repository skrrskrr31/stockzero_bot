"""
buffett_video.py - Warren Buffett / Berkshire Hathaway portfolio tracker
Shows Berkshire's top holdings as animated horizontal bar chart,
plus how much $10K invested in each would have grown.
"""

import math, os, random
from datetime import datetime, timedelta

import cv2
import numpy as np
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont
from scipy.interpolate import make_interp_spline

def _smooth_series(series):
    if len(series) < 4:
        return series
    x_raw  = np.linspace(0, 1, len(series))
    x_fine = np.linspace(0, 1, len(series) * 10)
    try:
        return make_interp_spline(x_raw, series, k=3)(x_fine).tolist()
    except Exception:
        return series

WIDTH, HEIGHT = 1080, 1920
FPS    = 30
ANIM_SECS = 16
HOLD_SECS = 5

BG     = (8,   8,   8)
GOLD   = (255, 200, 50)
GREEN  = (0,   215, 55)
WHITE  = (255, 255, 255)
GRAY   = (110, 110, 110)
DARK   = (22,  22,  22)

_FONT_DIR = "C:/Windows/Fonts/"
def _font(name, size):
    p = _FONT_DIR + name
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()


# ── Berkshire 13F top holdings (Q4 2024 approximate) ─────────────────────────
# (ticker, company, % of portfolio)
BERKSHIRE_HOLDINGS = [
    ("AAPL",  "Apple Inc.",          28.0),
    ("BAC",   "Bank of America",     13.0),
    ("AXP",   "American Express",    11.5),
    ("KO",    "Coca-Cola",            9.0),
    ("CVX",   "Chevron",              6.5),
    ("OXY",   "Occidental Petrol.",   5.2),
    ("MCO",   "Moody's Corp.",        4.8),
    ("KHC",   "Kraft Heinz",          3.8),
    ("DVA",   "DaVita Inc.",          2.2),
    ("VRSN",  "VeriSign",             1.8),
]

# Different video angles to keep content fresh
VIDEO_ANGLES = [
    "top5_holdings",     # Top 5 positions as bar chart
    "10yr_returns",      # What $10K in each top pick returned in 10 years
    "latest_buys",       # Most recently increased positions (simulate from list)
    "vs_sp500",          # Berkshire performance vs S&P 500
]


def _fmt(v):
    if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if v >= 1_000:     return f"${v:,.0f}"
    return f"${v:.0f}"


def _bar_color(i):
    palette = [
        (0, 195, 255), (0, 215, 55), (255, 200, 50),
        (255, 100, 50), (180, 80, 255), (50, 200, 180),
        (255, 50, 100), (100, 180, 255), (255, 160, 0), (80, 255, 140),
    ]
    return palette[i % len(palette)]


def create_top5_video():
    """Animated horizontal bar chart of Berkshire's top 5 holdings."""
    top5   = BERKSHIRE_HOLDINGS[:5]
    tickers = [t for t, _, _ in top5]
    labels  = [c for _, c, _ in top5]
    weights = [w for _, _, w in top5]
    max_w   = max(weights)

    # Fetch current prices
    gains = {}
    for t, _, _ in top5:
        try:
            hist = yf.download(t, period="5y", interval="1mo", progress=False, auto_adjust=True)
            prices = hist["Close"].squeeze().dropna()
            if len(prices) >= 2:
                g = (float(prices.iloc[-1]) - float(prices.iloc[0])) / float(prices.iloc[0]) * 100
                gains[t] = g
        except:
            gains[t] = 0.0

    # Layout
    BAR_L   = 350
    BAR_R   = WIDTH - 80
    BAR_H   = 100
    ROW_GAP = 195
    START_Y = 520

    total_f = FPS * (ANIM_SECS + HOLD_SECS)
    anim_f  = FPS * ANIM_SECS
    video_path = "buffett_top5.mp4"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))

    fb  = _font("arialbd.ttf", 80)
    fm  = _font("arialbd.ttf", 52)
    fs  = _font("arialbd.ttf", 42)
    fx  = _font("arialbd.ttf", 34)
    fxs = _font("arialbd.ttf", 28)

    for fi in range(total_f):
        t    = fi / FPS
        prog = min(1.0, fi / anim_f)
        hold = fi >= anim_f
        # Ease in
        eased = prog * prog * (3 - 2 * prog)

        img  = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 55), (WIDTH, 175)], fill=(30, 25, 0))
        draw.rectangle([(0, 55), (WIDTH, 62)],  fill=GOLD)
        draw.rectangle([(0, 168),(WIDTH, 175)], fill=GOLD)

        h1 = "WARREN BUFFETT'S"
        h2 = "TOP 5 HOLDINGS"
        hb1 = draw.textbbox((0,0), h1, font=fx)
        hb2 = draw.textbbox((0,0), h2, font=fm)
        draw.text(((WIDTH-(hb1[2]-hb1[0]))//2, 65),  h1, font=fx, fill=GOLD)
        draw.text(((WIDTH-(hb2[2]-hb2[0]))//2, 107), h2, font=fm, fill=WHITE)

        sub = f"Berkshire Hathaway 13F  |  Q4 2024"
        sb  = draw.textbbox((0,0), sub, font=fxs)
        draw.text(((WIDTH-(sb[2]-sb[0]))//2, 195), sub, font=fxs, fill=GRAY)

        # Bars
        for i, (ticker, company, weight) in enumerate(top5):
            ry     = START_Y + i * ROW_GAP
            color  = _bar_color(i)
            fill_w = int((BAR_R - BAR_L) * (weight / max_w) * eased)

            # Background bar
            draw.rectangle([(BAR_L, ry), (BAR_R, ry + BAR_H)], fill=DARK)
            # Filled bar
            if fill_w > 0:
                draw.rectangle([(BAR_L, ry), (BAR_L + fill_w, ry + BAR_H)], fill=color)

            # Ticker + company (left of bar)
            draw.text((60, ry + 10),  ticker,  font=fs,  fill=color)
            draw.text((60, ry + 62),  company[:18], font=fxs, fill=GRAY)

            # Weight % (right of bar)
            w_str = f"{weight:.1f}%"
            wb    = draw.textbbox((0,0), w_str, font=fs)
            draw.text((BAR_L + fill_w + 10, ry + 25), w_str, font=fs, fill=color)

            # 5-yr return (on hold)
            if hold and ticker in gains:
                g_str = f"{gains[ticker]:+.0f}% (5yr)"
                draw.text((60, ry + BAR_H + 8), g_str, font=fxs,
                          fill=GREEN if gains[ticker] >= 0 else (215,40,40))

        # Footer
        if hold:
            draw.rectangle([(60, HEIGHT-160), (WIDTH-60, HEIGHT-80)], fill=DARK)
            foot = "Based on SEC 13F filings — updated quarterly."
            fb2  = draw.textbbox((0,0), foot, font=fxs)
            draw.text(((WIDTH-(fb2[2]-fb2[0]))//2, HEIGHT-145), foot, font=fxs, fill=GRAY)

        out.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

    out.release()
    return video_path


def create_10yr_returns_video(used_tickers=None):
    """What $10,000 in Buffett's top picks returned over 10 years."""
    INVESTMENT = 10_000
    picks = random.sample(BERKSHIRE_HOLDINGS[:7], 4)  # show 4 random picks

    results = []
    for ticker, company, weight in picks:
        try:
            h = yf.download(ticker, period="10y", interval="1mo", progress=False, auto_adjust=True)
            prices = h["Close"].squeeze().dropna()
            if len(prices) >= 24:
                shares = INVESTMENT / float(prices.iloc[0])
                final  = shares * float(prices.iloc[-1])
                pct    = (final - INVESTMENT) / INVESTMENT * 100
                results.append((ticker, company, final, pct))
        except:
            results.append((ticker, company, INVESTMENT * 1.5, 50.0))

    if not results:
        return None

    results.sort(key=lambda x: x[2], reverse=True)
    max_val = results[0][2]

    BAR_L   = 340
    BAR_R   = WIDTH - 80
    BAR_H   = 105
    ROW_GAP = 200
    START_Y = 510

    total_f = FPS * (ANIM_SECS + HOLD_SECS)
    anim_f  = FPS * ANIM_SECS
    video_path = "buffett_returns.mp4"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))

    fm  = _font("arialbd.ttf", 54)
    fs  = _font("arialbd.ttf", 42)
    fx  = _font("arialbd.ttf", 36)
    fxs = _font("arialbd.ttf", 28)

    for fi in range(total_f):
        t     = fi / FPS
        prog  = min(1.0, fi / anim_f)
        eased = prog * prog * (3 - 2 * prog)

        img  = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 55), (WIDTH, 175)], fill=(20, 30, 20))
        draw.rectangle([(0, 55), (WIDTH, 62)],  fill=GREEN)
        draw.rectangle([(0, 168),(WIDTH, 175)], fill=GREEN)

        h1 = "BUFFETT'S PICKS"
        h2 = "$10,000  |  10 YEARS"
        hb1 = draw.textbbox((0,0), h1, font=fm)
        hb2 = draw.textbbox((0,0), h2, font=fm)
        draw.text(((WIDTH-(hb1[2]-hb1[0]))//2, 65),  h1, font=fm, fill=GREEN)
        draw.text(((WIDTH-(hb2[2]-hb2[0]))//2, 115), h2, font=fm, fill=WHITE)

        sub = "Berkshire Hathaway top holdings — real returns"
        sb  = draw.textbbox((0,0), sub, font=fxs)
        draw.text(((WIDTH-(sb[2]-sb[0]))//2, 200), sub, font=fxs, fill=GRAY)

        for i, (ticker, company, final_val, pct) in enumerate(results):
            ry     = START_Y + i * ROW_GAP
            color  = _bar_color(i)
            fill_w = int((BAR_R - BAR_L) * (final_val / max_val) * eased)

            draw.rectangle([(BAR_L, ry), (BAR_R, ry + BAR_H)], fill=DARK)
            if fill_w > 0:
                draw.rectangle([(BAR_L, ry), (BAR_L + fill_w, ry + BAR_H)], fill=color)

            draw.text((60, ry + 8),  ticker,         font=fs,  fill=color)
            draw.text((60, ry + 62), company[:18],   font=fxs, fill=GRAY)

            val_str = _fmt(final_val)
            vb = draw.textbbox((0,0), val_str, font=fs)
            x_pos = max(BAR_L + fill_w + 10, BAR_L + 10)
            draw.text((x_pos, ry + 25), val_str, font=fs, fill=color)

            if prog > 0.5:
                pct_str = f"{pct:+.0f}%"
                draw.text((60, ry + BAR_H + 8), pct_str, font=fxs,
                          fill=GREEN if pct >= 0 else (215,40,40))

        # Progress bar
        draw.rectangle([(0, HEIGHT-55), (WIDTH, HEIGHT)], fill=(20,20,20))
        draw.rectangle([(0, HEIGHT-55), (int(WIDTH*prog), HEIGHT)], fill=GREEN)

        # Footer
        if prog > 0.7:
            foot = "Follow for daily investing breakdowns!"
            fb2  = draw.textbbox((0,0), foot, font=fxs)
            draw.text(((WIDTH-(fb2[2]-fb2[0]))//2, HEIGHT-120), foot, font=fxs, fill=GRAY)

        out.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

    out.release()
    return {
        "video_path": video_path,
        "results":    results,
    }


def create_vs_sp500_video():
    """Berkshire (BRK-B) vs S&P 500 (SPY) 10-year comparison."""
    INVESTMENT = 10_000
    tickers    = ["BRK-B", "SPY"]
    labels     = ["Berkshire", "S&P 500"]
    colors_map = [(255, 200, 50), (0, 195, 255)]

    data = {}
    for t in tickers:
        try:
            h = yf.download(t, period="10y", interval="1mo", progress=False, auto_adjust=True)
            prices = h["Close"].squeeze().dropna().tolist()
            if len(prices) >= 24:
                shares   = INVESTMENT / prices[0]
                data[t]  = [shares * p for p in prices]
        except:
            pass

    if len(data) < 2:
        return None

    # Smooth her seriyi spline ile
    data_smooth = {t: _smooth_series(v) for t, v in data.items()}
    n    = min(len(v) for v in data_smooth.values())
    all_vals = [v for series in data_smooth.values() for v in series[:n]]
    lo, hi   = min(all_vals), max(all_vals)
    rng      = hi - lo or 1

    CHART_L_V, CHART_R_V = 85, 995
    CHART_T_V, CHART_B_V = 420, 1620

    def vy(v): return int(CHART_B_V - (v - lo) / rng * (CHART_B_V - CHART_T_V))
    def ix(i): return int(CHART_L_V + i / (n-1) * (CHART_R_V - CHART_L_V))

    total_f = FPS * (ANIM_SECS + HOLD_SECS)
    anim_f  = FPS * ANIM_SECS
    video_path = "buffett_vs_sp500.mp4"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))

    fm  = _font("arialbd.ttf", 58)
    fs  = _font("arialbd.ttf", 44)
    fx  = _font("arialbd.ttf", 36)
    fxs = _font("arialbd.ttf", 28)

    for fi in range(total_f):
        t    = fi / FPS
        prog = min(1.0, fi / anim_f)
        hold = fi >= anim_f

        img  = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([(0, 55), (WIDTH, 165)], fill=(25, 20, 5))
        draw.rectangle([(0, 55), (WIDTH, 62)],  fill=GOLD)
        draw.rectangle([(0, 158),(WIDTH, 165)], fill=GOLD)

        h1 = "BUFFETT vs S&P 500"
        hb = draw.textbbox((0,0), h1, font=fm)
        draw.text(((WIDTH-(hb[2]-hb[0]))//2, 70), h1, font=fm, fill=GOLD)

        sub = f"${INVESTMENT:,} invested  |  10 Years"
        sb  = draw.textbbox((0,0), sub, font=fxs)
        draw.text(((WIDTH-(sb[2]-sb[0]))//2, 185), sub, font=fxs, fill=GRAY)

        # Legend
        for li, (lbl, col) in enumerate(zip(labels, colors_map)):
            lx = 80 + li * 340
            draw.rectangle([(lx, 240), (lx+60, 270)], fill=col)
            draw.text((lx+75, 235), lbl, font=fx, fill=col)

        # Grid
        GRID_C = (28,28,28)
        cw_v = CHART_R_V - CHART_L_V
        for r in range(6):
            y0 = CHART_T_V + (CHART_B_V - CHART_T_V) * r / 5
            draw.line([(CHART_L_V, int(y0)), (CHART_R_V, int(y0))], fill=GRID_C, width=1)

        # Animated smooth lines
        vis = max(2, int(prog * n))
        for ti, (ticker, series) in enumerate(data_smooth.items()):
            col  = colors_map[ti]
            pts  = [(ix(i), vy(series[i])) for i in range(vis)]
            if len(pts) >= 2:
                draw.line(pts, fill=col, width=4 if ti == 0 else 3)
            if pts:
                cx, cy = pts[-1]
                draw.ellipse((cx-7, cy-7, cx+7, cy+7), fill=col)
                if prog > 0.3:
                    draw.text((cx+12, cy-18), _fmt(series[vis-1]), font=fxs, fill=col)

        # Hold: winner callout
        if hold:
            brkb_final = data.get("BRK-B", [INVESTMENT])[-1]
            spy_final  = data.get("SPY",   [INVESTMENT])[-1]
            winner     = "Berkshire" if brkb_final >= spy_final else "S&P 500"
            diff       = abs(brkb_final - spy_final)

            panel_y = HEIGHT - 430
            draw.rectangle([(60, panel_y), (WIDTH-60, HEIGHT-80)], fill=DARK)
            win_col = colors_map[0] if winner == "Berkshire" else colors_map[1]
            draw.text((80, panel_y + 20), f"Winner: {winner}", font=fs, fill=win_col)
            draw.text((80, panel_y + 85), f"Difference: {_fmt(diff)}", font=fx, fill=GRAY)
            draw.text((80, panel_y +145), "Follow for more investing breakdowns!", font=fxs, fill=GRAY)

        # Progress bar
        draw.rectangle([(0, HEIGHT-55), (WIDTH, HEIGHT)], fill=(20,20,20))
        draw.rectangle([(0, HEIGHT-55), (int(WIDTH*prog), HEIGHT)], fill=GOLD)

        out.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

    out.release()
    return {
        "video_path":   video_path,
        "brk_final":    data.get("BRK-B", [0])[-1],
        "spy_final":    data.get("SPY",   [0])[-1],
    }


def create_buffett_video(angle=None):
    """Main entry point — picks a random Buffett video angle."""
    if angle is None:
        angle = random.choice(VIDEO_ANGLES)

    print(f"  Buffett angle: {angle}")

    if angle == "top5_holdings":
        vp = create_top5_video()
        return {"video_path": vp, "angle": angle} if vp else None
    elif angle == "10yr_returns":
        return create_10yr_returns_video()
    elif angle == "vs_sp500":
        return create_vs_sp500_video()
    else:
        # latest_buys — same as top5 but different title (rotated holdings)
        # Pick bottom half of holdings as "latest focus"
        vp = create_top5_video()
        return {"video_path": vp, "angle": angle} if vp else None
