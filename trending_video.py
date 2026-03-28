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
from scipy.interpolate import make_interp_spline

WIDTH, HEIGHT = 1080, 1920
FPS    = 30
ANIM_SECS = 14
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

    # Önce bugünün intraday chart'ını dene (5dk aralıklı)
    # Eğer yoksa (piyasa kapalı/weekend) 5 günlük saatlik veri kullan
    chart_label = "Today"
    thirty_day_pct = None
    try:
        hist = yf.download(ticker, period="1d", interval="5m", progress=False, auto_adjust=True)
        prices = hist["Close"].squeeze().dropna().tolist()
        if len(prices) < 10:
            raise ValueError("Not enough intraday data")
        chart_label = "Today (Intraday)"
    except Exception:
        try:
            hist = yf.download(ticker, period="5d", interval="1h", progress=False, auto_adjust=True)
            prices = hist["Close"].squeeze().dropna().tolist()
            if len(prices) < 5:
                raise ValueError("Not enough data")
            chart_label = "5-Day"
        except Exception as e:
            print(f"  Data error: {e}")
            return None

    # 30 günlük değişimi ayrıca hesapla (sadece text için)
    try:
        hist30 = yf.download(ticker, period="1mo", interval="1d", progress=False, auto_adjust=True)
        p30    = hist30["Close"].squeeze().dropna().tolist()
        if len(p30) >= 2:
            thirty_day_pct = (p30[-1] - p30[0]) / p30[0] * 100
    except:
        pass

    n = len(prices)
    lo, hi = min(prices), max(prices)
    rng = hi - lo or 1

    # Smooth the price curve with spline interpolation
    x_raw  = np.linspace(0, 1, n)
    x_fine = np.linspace(0, 1, n * 12)          # 12× more points = smooth
    k      = min(3, n - 1)                       # cubic if enough points
    try:
        spl          = make_interp_spline(x_raw, prices, k=k)
        prices_smooth = spl(x_fine).tolist()
    except Exception:
        prices_smooth = prices
        x_fine        = x_raw

    n_smooth = len(prices_smooth)
    lo_s  = min(prices_smooth)
    hi_s  = max(prices_smooth)
    rng_s = hi_s - lo_s or 1

    def py(p): return int(CHART_B - (p - lo_s) / rng_s * (CHART_B - CHART_T))
    def px(i): return int(CHART_L + i / (n_smooth - 1) * (CHART_R - CHART_L))

    total_f = FPS * (ANIM_SECS + HOLD_SECS)
    anim_f  = FPS * ANIM_SECS

    video_path = f"{ticker}_trending.mp4"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))

    fb = _font("arialbd.ttf", 120)
    fm = _font("arialbd.ttf", 56)
    fs = _font("arialbd.ttf", 48)
    fx = _font("arialbd.ttf", 36)
    fxs= _font("arialbd.ttf", 28)

    banner_text = "TODAY'S TOP GAINER" if direction == "gainer" else "TODAY'S TOP LOSER"
    sign = "+" if pct > 0 else ""
    pct_str = f"{sign}{pct:.1f}%"
    date_str = datetime.now().strftime("%B %d, %Y").upper()   # e.g. MARCH 28, 2026

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

        # Date — sağ alt köşe
        db = draw.textbbox((0, 0), date_str, font=fx)
        draw.text((WIDTH - (db[2]-db[0]) - 30, HEIGHT - 110), date_str, font=fx, fill=GRAY)

        # Ticker
        draw.text((60, 185), ticker, font=fb, fill=color)
        draw.text((60, 335), company, font=fs, fill=GRAY)

        # % change
        pb = draw.textbbox((0,0), pct_str, font=fb)
        draw.text((WIDTH - (pb[2]-pb[0]) - 60, 185), pct_str, font=fb, fill=color)

        # Animated smooth line
        vis = max(2, int(prog * n_smooth))
        pts = [(px(i), py(prices_smooth[i])) for i in range(vis)]
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
            curr_p = prices_smooth[vis - 1]
            draw.text((cx+14, cy-28), _fmt_price(curr_p), font=fx, fill=WHITE)

        # Progress bar
        draw.rectangle([(0, HEIGHT-55), (WIDTH, HEIGHT)], fill=(20,20,20))
        draw.rectangle([(0, HEIGHT-55), (int(WIDTH*prog), HEIGHT)], fill=color)

        # Hold: summary + Subscribe/Like butonları
        if hold:
            hold_prog = (fi - anim_f) / (FPS * HOLD_SECS)   # 0→1 during hold

            # Chart label + today's change
            if thirty_day_pct is not None:
                s = f"{chart_label}  |  30-Day: {thirty_day_pct:+.1f}%  |  Today: {pct_str}"
            else:
                s = f"{chart_label}  |  Today: {pct_str}"
            sb = draw.textbbox((0,0), s, font=fxs)
            draw.text(((WIDTH-(sb[2]-sb[0]))//2, HEIGHT-315), s, font=fxs, fill=GRAY)

            # Slide-in animasyonu (yukarıdan aşağı)
            slide = min(1.0, hold_prog * 3)
            panel_y = int(HEIGHT - 240 + (1 - slide) * 200)

            # SUBSCRIBE butonu (kırmızı)
            sub_x1, sub_y1 = 60, panel_y
            sub_x2, sub_y2 = WIDTH - 60, panel_y + 90
            draw.rounded_rectangle([(sub_x1, sub_y1), (sub_x2, sub_y2)],
                                    radius=18, fill=(255, 30, 30))
            sub_txt = "SUBSCRIBE"
            stb = draw.textbbox((0,0), sub_txt, font=fs)
            draw.text(((WIDTH-(stb[2]-stb[0]))//2, sub_y1+22),
                      sub_txt, font=fs, fill=WHITE)

            # LIKE butonu (koyu gri)
            lk_x1, lk_y1 = 60, panel_y + 105
            lk_x2, lk_y2 = WIDTH - 60, panel_y + 195
            draw.rounded_rectangle([(lk_x1, lk_y1), (lk_x2, lk_y2)],
                                    radius=18, fill=(40, 40, 40))
            like_txt = f"LIKE  ({'+' if pct > 0 else ''}{pct:.1f}% today!)"
            ltb = draw.textbbox((0,0), like_txt, font=fs)
            draw.text(((WIDTH-(ltb[2]-ltb[0]))//2, lk_y1+22),
                      like_txt, font=fs, fill=color)

        out.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

    out.release()
    return {"video_path": video_path, "ticker": ticker, "company": company,
            "pct_change": pct, "direction": direction}
