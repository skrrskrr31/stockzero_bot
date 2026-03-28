"""
trending_video.py - Daily biggest gainer / loser video
Shows which stock moved the most today and its 1-month price chart.
"""

import math, os, random
from datetime import datetime, timedelta

import cv2
import numpy as np
import yfinance as yf
import requests
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920
FPS    = 30
ANIM_SECS = 15
HOLD_SECS = 4

CHART_L, CHART_R = 85, 995
CHART_T, CHART_B = 460, 1640

BG    = (8,   8,   8)
GREEN = (0,   215, 55)
RED   = (215, 40,  40)
WHITE = (255, 255, 255)
GRAY  = (110, 110, 110)
GRID  = (28,  28,  28)

_FONT_DIR = "C:/Windows/Fonts/"
def _font(name, size):
    p = _FONT_DIR + name
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()

WATCHLIST = [
    "NVDA","AAPL","MSFT","TSLA","AMZN","META","GOOGL","AMD",
    "NFLX","PLTR","COIN","MSTR","ARM","SMCI","INTC","MU",
    "AVGO","QCOM","JPM","BAC","GS","V","MA","PYPL",
    "SHOP","UBER","SOFI","HOOD","RIVN","NIO","CRWD",
    "DDOG","NET","ZS","PANW","SNOW","MDB",
    "ABNB","DASH","RBLX","SPOT","SNAP","PINS",
    "XOM","CVX","OXY","LLY","PFE","MRNA","ABBV",
    "WMT","TGT","COST","HD","NKE","F","GM",
    "SPY","QQQ","IWM","ARKK",
]

COMPANY_NAMES = {
    "NVDA":"NVIDIA","AAPL":"Apple","MSFT":"Microsoft","TSLA":"Tesla",
    "AMZN":"Amazon","META":"Meta","GOOGL":"Alphabet","AMD":"AMD",
    "NFLX":"Netflix","PLTR":"Palantir","COIN":"Coinbase","MSTR":"MicroStrategy",
    "ARM":"ARM Holdings","SMCI":"Super Micro","INTC":"Intel","MU":"Micron",
    "AVGO":"Broadcom","QCOM":"Qualcomm","JPM":"JPMorgan","BAC":"Bank of America",
    "GS":"Goldman Sachs","V":"Visa","MA":"Mastercard","PYPL":"PayPal",
    "SHOP":"Shopify","UBER":"Uber","SOFI":"SoFi","HOOD":"Robinhood",
    "RIVN":"Rivian","NIO":"NIO","CRWD":"CrowdStrike","DDOG":"Datadog",
    "NET":"Cloudflare","ZS":"Zscaler","PANW":"Palo Alto","SNOW":"Snowflake",
    "MDB":"MongoDB","ABNB":"Airbnb","DASH":"DoorDash","RBLX":"Roblox",
    "SPOT":"Spotify","SNAP":"Snapchat","PINS":"Pinterest",
    "XOM":"ExxonMobil","CVX":"Chevron","OXY":"Occidental","LLY":"Eli Lilly",
    "PFE":"Pfizer","MRNA":"Moderna","ABBV":"AbbVie","WMT":"Walmart",
    "TGT":"Target","COST":"Costco","HD":"Home Depot","NKE":"Nike",
    "F":"Ford","GM":"General Motors","SPY":"S&P 500","QQQ":"Nasdaq 100",
    "IWM":"Russell 2000","ARKK":"ARK Innovation",
}


def get_biggest_mover(used_tickers=None):
    used = set(used_tickers or [])
    available = [t for t in WATCHLIST if t not in used] or WATCHLIST

    # Try Yahoo Finance screener
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        mode = random.choice(["day_gainers", "day_losers"])
        r = requests.get(
            f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?count=10&scrIds={mode}",
            headers=headers, timeout=8
        )
        if r.status_code == 200:
            quotes = r.json()["finance"]["result"][0]["quotes"]
            for q in quotes:
                sym = q.get("symbol", "")
                if sym in available:
                    pct = q.get("regularMarketChangePercent", 0)
                    return sym, pct, "gainer" if pct > 0 else "loser"
    except:
        pass

    # Fallback: scan watchlist subset
    changes = {}
    for t in random.sample(available, min(20, len(available))):
        try:
            h = yf.download(t, period="2d", interval="1d", progress=False, auto_adjust=True)
            if len(h) >= 2:
                prev, curr = float(h["Close"].iloc[-2]), float(h["Close"].iloc[-1])
                if prev > 0:
                    changes[t] = (curr - prev) / prev * 100
        except:
            continue

    if not changes:
        t = random.choice(available)
        return t, random.uniform(3, 8), "gainer"

    t = max(changes, key=lambda x: abs(changes[x]))
    return t, changes[t], "gainer" if changes[t] > 0 else "loser"


def _fmt_price(v):
    if v >= 1000: return f"${v:,.0f}"
    elif v >= 10:  return f"${v:.2f}"
    else:           return f"${v:.3f}"


def _wavy_grid(draw, t):
    cw, ch = CHART_R - CHART_L, CHART_B - CHART_T
    for c in range(7):
        x0 = CHART_L + cw * c / 6
        pts = [(int(x0 + math.sin((y/130 + t + c*0.6)*1.9)*8), y) for y in range(CHART_T, CHART_B+2, 10)]
        for i in range(len(pts)-1): draw.line([pts[i], pts[i+1]], fill=GRID, width=1)
    for r in range(8):
        y0 = CHART_T + ch * r / 7
        pts = [(x, int(y0 + math.sin((x/130 + t + r*0.6)*1.9)*8)) for x in range(CHART_L, CHART_R+2, 10)]
        for i in range(len(pts)-1): draw.line([pts[i], pts[i+1]], fill=GRID, width=1)


def create_trending_video(used_tickers=None):
    ticker, pct, direction = get_biggest_mover(used_tickers)
    company = COMPANY_NAMES.get(ticker, ticker)
    color   = GREEN if direction == "gainer" else RED
    print(f"  Trending: {ticker} ({pct:+.1f}%) — {direction}")

    try:
        hist   = yf.download(ticker, period="1mo", interval="1d", progress=False, auto_adjust=True)
        prices = hist["Close"].squeeze().dropna().tolist()
        if len(prices) < 5:
            raise ValueError("Insufficient data")
    except Exception as e:
        print(f"  Data error: {e}")
        return None

    n = len(prices)
    lo, hi = min(prices), max(prices)
    rng = hi - lo or 1

    def py(p): return int(CHART_B - (p - lo) / rng * (CHART_B - CHART_T))
    def px(i): return int(CHART_L + i / (n-1) * (CHART_R - CHART_L))

    total_f = FPS * (ANIM_SECS + HOLD_SECS)
    anim_f  = FPS * ANIM_SECS

    video_path = f"{ticker}_trending.mp4"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))

    fb = _font("arialbd.ttf", 120)
    fm = _font("arialbd.ttf", 56)
    fs = _font("arialbd.ttf", 42)
    fx = _font("arialbd.ttf", 35)

    banner_text = "TODAY'S TOP GAINER" if direction == "gainer" else "TODAY'S TOP LOSER"
    sign = "+" if pct > 0 else ""
    pct_str = f"{sign}{pct:.1f}%"

    for fi in range(total_f):
        t     = fi / FPS
        prog  = min(1.0, fi / anim_f)
        hold  = fi >= anim_f

        img  = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)
        _wavy_grid(draw, t * 0.25)

        # Top banner
        draw.rectangle([(0, 60), (WIDTH, 155)], fill=color)
        bb = draw.textbbox((0, 0), banner_text, font=fm)
        draw.text(((WIDTH - bb[2] + bb[0])//2, 72), banner_text, font=fm, fill=(0,0,0))

        # Ticker
        draw.text((60, 185), ticker, font=fb, fill=color)
        draw.text((60, 335), company, font=fs, fill=GRAY)

        # % change
        pb = draw.textbbox((0,0), pct_str, font=fb)
        draw.text((WIDTH - (pb[2]-pb[0]) - 60, 185), pct_str, font=fb, fill=color)

        # Animated line
        vis = max(2, int(prog * n))
        pts = [(px(i), py(prices[i])) for i in range(vis)]
        if len(pts) >= 2:
            draw.line(pts, fill=color, width=4)

        # Dot + glow
        if pts:
            cx, cy = pts[-1]
            for r2, a in [(20, 35), (13, 75), (7, 160)]:
                glow = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
                ImageDraw.Draw(glow).ellipse((cx-r2, cy-r2, cx+r2, cy+r2), fill=(*color, a))
                img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
                draw = ImageDraw.Draw(img)
            draw.ellipse((cx-7, cy-7, cx+7, cy+7), fill=WHITE)
            curr_p = prices[min(int(prog*(n-1)), n-1)]
            draw.text((cx+14, cy-28), _fmt_price(curr_p), font=fx, fill=WHITE)

        # Progress bar
        draw.rectangle([(0, HEIGHT-55), (WIDTH, HEIGHT)], fill=(20,20,20))
        draw.rectangle([(0, HEIGHT-55), (int(WIDTH*prog), HEIGHT)], fill=color)

        # Hold: 30-day summary
        if hold:
            p30 = (prices[-1] - prices[0]) / prices[0] * 100
            s   = f"30-Day: {p30:+.1f}%   |   Today: {pct_str}"
            sb  = draw.textbbox((0,0), s, font=fx)
            draw.text(((WIDTH-(sb[2]-sb[0]))//2, HEIGHT-120), s, font=fx, fill=GRAY)

        out.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

    out.release()
    return {"video_path": video_path, "ticker": ticker, "company": company,
            "pct_change": pct, "direction": direction}
