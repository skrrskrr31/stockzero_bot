"""
dca_video.py - Dollar Cost Averaging animation
"What if you invested $100/month in X for 10 years?"
Shows two animated lines: total invested (gray) vs portfolio value (green/red).
"""

import math, os, random
from datetime import datetime

import cv2
import numpy as np
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont
from scipy.interpolate import make_interp_spline

WIDTH, HEIGHT = 1080, 1920
FPS    = 30
ANIM_SECS = 18
HOLD_SECS = 5

CHART_L, CHART_R = 85, 995
CHART_T, CHART_B = 480, 1640

BG    = (8,   8,   8)
GREEN = (0,   215, 55)
RED   = (215, 40,  40)
BLUE  = (80,  140, 255)
WHITE = (255, 255, 255)
GRAY  = (110, 110, 110)
GRID  = (28,  28,  28)
GOLD  = (255, 200, 50)

_FONT_DIR = "C:/Windows/Fonts/"
def _font(name, size):
    p = _FONT_DIR + name
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()

DCA_STOCKS = [
    "NVDA","AAPL","MSFT","TSLA","AMZN","META","GOOGL","AMD",
    "NFLX","V","MA","JPM","COST","HD","NKE","DIS",
    "AVGO","QCOM","SHOP","UBER","PLTR","CRWD","DDOG",
    "XOM","LLY","ABBV","PFE","WMT","QQQ","SPY",
]

COMPANY_NAMES = {
    "NVDA":"NVIDIA","AAPL":"Apple","MSFT":"Microsoft","TSLA":"Tesla",
    "AMZN":"Amazon","META":"Meta","GOOGL":"Alphabet","AMD":"AMD",
    "NFLX":"Netflix","V":"Visa","MA":"Mastercard","JPM":"JPMorgan",
    "COST":"Costco","HD":"Home Depot","NKE":"Nike","DIS":"Disney",
    "AVGO":"Broadcom","QCOM":"Qualcomm","SHOP":"Shopify","UBER":"Uber",
    "PLTR":"Palantir","CRWD":"CrowdStrike","DDOG":"Datadog",
    "XOM":"ExxonMobil","LLY":"Eli Lilly","ABBV":"AbbVie","PFE":"Pfizer",
    "WMT":"Walmart","QQQ":"Nasdaq 100","SPY":"S&P 500",
}


def _fmt(v):
    if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if v >= 1_000:     return f"${v:,.0f}"
    return f"${v:.2f}"


def calc_dca(prices, monthly=100):
    """Calculate DCA portfolio: invest `monthly` at each period's close."""
    shares      = 0.0
    total_inv   = 0.0
    invested    = []   # cumulative invested at each point
    portfolio   = []   # portfolio value at each point

    for p in prices:
        shares    += monthly / float(p)
        total_inv += monthly
        invested.append(total_inv)
        portfolio.append(shares * float(p))

    return invested, portfolio


def _wavy_grid(draw, t):
    cw, ch = CHART_R - CHART_L, CHART_B - CHART_T
    for c in range(7):
        x0  = CHART_L + cw * c / 6
        pts = [(int(x0 + math.sin((y/130+t+c*0.6)*1.9)*8), y) for y in range(CHART_T, CHART_B+2, 10)]
        for i in range(len(pts)-1): draw.line([pts[i], pts[i+1]], fill=GRID, width=1)
    for r in range(8):
        y0  = CHART_T + ch * r / 7
        pts = [(x, int(y0 + math.sin((x/130+t+r*0.6)*1.9)*8)) for x in range(CHART_L, CHART_R+2, 10)]
        for i in range(len(pts)-1): draw.line([pts[i], pts[i+1]], fill=GRID, width=1)


def create_dca_video(ticker=None, monthly=100, years=10, used_tickers=None):
    used = set(used_tickers or [])
    if ticker is None:
        avail  = [t for t in DCA_STOCKS if t not in used] or DCA_STOCKS
        ticker = random.choice(avail)
    company = COMPANY_NAMES.get(ticker, ticker)
    print(f"  DCA: ${monthly}/mo in {ticker} for {years}yr")

    try:
        hist   = yf.download(ticker, period=f"{years+1}y", interval="1mo",
                             progress=False, auto_adjust=True)
        prices = hist["Close"].squeeze().dropna()
        # Keep exactly `years * 12` months
        prices = prices.tail(years * 12)
        if len(prices) < years * 6:
            raise ValueError(f"Not enough monthly data ({len(prices)} rows)")
        prices = prices.tolist()
    except Exception as e:
        print(f"  Data error: {e}")
        return None

    invested, portfolio = calc_dca(prices, monthly)
    n = len(prices)

    total_invested = invested[-1]
    final_value    = portfolio[-1]
    gain_pct       = (final_value - total_invested) / total_invested * 100
    profit         = final_value - total_invested
    port_color     = GREEN if final_value >= total_invested else RED

    # Spline interpolation — her iki seriyi yumuşat
    def _smooth(series):
        x_raw  = np.linspace(0, 1, len(series))
        x_fine = np.linspace(0, 1, len(series) * 10)
        k      = min(3, len(series) - 1)
        try:
            return make_interp_spline(x_raw, series, k=k)(x_fine).tolist()
        except Exception:
            return series

    inv_smooth  = _smooth(invested)
    port_smooth = _smooth(portfolio)
    n_s = len(inv_smooth)

    # Scale both series together
    all_vals  = inv_smooth + port_smooth
    lo, hi    = min(all_vals), max(all_vals)
    rng       = hi - lo or 1

    def vy(v): return int(CHART_B - (v - lo) / rng * (CHART_B - CHART_T))
    def ix(i): return int(CHART_L + i / (n_s - 1) * (CHART_R - CHART_L))

    total_f = FPS * (ANIM_SECS + HOLD_SECS)
    anim_f  = FPS * ANIM_SECS
    video_path = f"{ticker}_dca.mp4"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))

    fb = _font("arialbd.ttf", 96)
    fm = _font("arialbd.ttf", 56)
    fs = _font("arialbd.ttf", 44)
    fx = _font("arialbd.ttf", 36)
    fxs= _font("arialbd.ttf", 30)

    for fi in range(total_f):
        t    = fi / FPS
        prog = min(1.0, fi / anim_f)
        hold = fi >= anim_f

        img  = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)
        _wavy_grid(draw, t * 0.2)

        # Title banner
        draw.rectangle([(0, 60), (WIDTH, 145)], fill=(20, 60, 120))
        title_str = f"${monthly}/MONTH IN {ticker} — {years} YEARS"
        tb = draw.textbbox((0,0), title_str, font=fx)
        draw.text(((WIDTH-(tb[2]-tb[0]))//2, 75), title_str, font=fx, fill=WHITE)

        # Company
        draw.text((60, 170), company, font=fm, fill=GRAY)
        draw.text((60, 245), f"Dollar Cost Averaging  |  {years} Years", font=fxs, fill=GRAY)

        # Legend
        draw.rectangle([(60, 310), (100, 340)], fill=GRAY)
        draw.text((115, 305), "Total Invested", font=fxs, fill=GRAY)
        draw.rectangle([(350, 310), (390, 340)], fill=port_color)
        draw.text((405, 305), "Portfolio Value", font=fxs, fill=port_color)

        # Animated smooth lines
        vis = max(2, int(prog * n_s))
        inv_pts  = [(ix(i), vy(inv_smooth[i]))  for i in range(vis)]
        port_pts = [(ix(i), vy(port_smooth[i])) for i in range(vis)]

        if len(inv_pts) >= 2:
            draw.line(inv_pts,  fill=GRAY,       width=3)
        if len(port_pts) >= 2:
            draw.line(port_pts, fill=port_color, width=4)

        # Live labels
        if port_pts:
            # Current portfolio dot
            cx, cy = port_pts[-1]
            draw.ellipse((cx-8, cy-8, cx+8, cy+8), fill=port_color)
            curr_v = port_smooth[vis-1]
            draw.text((cx+12, cy-20), _fmt(curr_v), font=fxs, fill=port_color)

        # Hold: final comparison panel
        if hold:
            py1 = HEIGHT - 480
            draw.rectangle([(60, py1), (WIDTH-60, HEIGHT-80)], fill=(18,18,18))
            draw.rectangle([(60, py1), (WIDTH-60, py1+5)], fill=port_color)

            row1_y = py1 + 30
            draw.text((80, row1_y),      "Total Invested:",  font=fx,  fill=GRAY)
            draw.text((80, row1_y + 60), "Portfolio Value:", font=fx,  fill=port_color)
            draw.text((80, row1_y +120), "Total Profit:",    font=fx,  fill=GOLD)
            draw.text((80, row1_y +180), "Return:",          font=fx,  fill=GOLD)

            inv_str  = _fmt(total_invested)
            port_str = _fmt(final_value)
            prof_str = _fmt(profit)
            ret_str  = f"{gain_pct:+.1f}%"

            for label, val, col, dy in [
                (inv_str,  inv_str,  GRAY,       0),
                (port_str, port_str, port_color, 60),
                (prof_str, prof_str, GOLD,       120),
                (ret_str,  ret_str,  GOLD,       180),
            ]:
                vb  = draw.textbbox((0,0), val, font=fs)
                draw.text((WIDTH - (vb[2]-vb[0]) - 80, row1_y + dy), val, font=fs, fill=col)

        # Progress bar
        draw.rectangle([(0, HEIGHT-55), (WIDTH, HEIGHT)], fill=(20,20,20))
        draw.rectangle([(0, HEIGHT-55), (int(WIDTH*prog), HEIGHT)], fill=port_color)

        out.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

    out.release()
    return {
        "video_path":      video_path,
        "ticker":          ticker,
        "company":         company,
        "monthly":         monthly,
        "years":           years,
        "total_invested":  total_invested,
        "final_value":     final_value,
        "gain_pct":        gain_pct,
    }
