"""
loss_video.py - Dramatic crash / loss scenario video
"What happened to $10,000 in [company]?" — shows the peak-to-crash chart.
Covers both delisted companies (hardcoded) and active stocks that crashed badly.
"""

import math, os, random
from datetime import datetime, timedelta

import cv2
import numpy as np
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920
FPS    = 30
ANIM_SECS = 18
HOLD_SECS = 5

CHART_L, CHART_R = 85, 995
CHART_T, CHART_B = 460, 1640

BG     = (8,   8,   8)
RED    = (215, 40,  40)
ORANGE = (255, 140, 0)
WHITE  = (255, 255, 255)
GRAY   = (110, 110, 110)
GRID   = (28,  28,  28)
GOLD   = (255, 200, 50)

_FONT_DIR = "C:/Windows/Fonts/"
def _font(name, size):
    p = _FONT_DIR + name
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()


# ── Crash scenarios ────────────────────────────────────────────────────────────
# Each entry: (ticker, company, period, label, note)
# period: yfinance period string for historical fetch
# label: shown on screen (can differ from ticker for bankrupt companies)
# note: bottom disclaimer note

CRASH_STOCKS_LIVE = [
    # Still-active stocks that crashed dramatically
    ("GME",  "GameStop",           "3y",  "GME",   "Jan 2021 peak → crash"),
    ("AMC",  "AMC Entertainment",  "3y",  "AMC",   "Jun 2021 peak → -98%"),
    ("SPCE", "Virgin Galactic",    "4y",  "SPCE",  "Feb 2021 peak → -99%"),
    ("LCID", "Lucid Motors",       "3y",  "LCID",  "Nov 2021 peak → -95%"),
    ("RIVN", "Rivian",             "3y",  "RIVN",  "Nov 2021 IPO peak → -90%"),
    ("PTON", "Peloton",            "4y",  "PTON",  "Jan 2021 peak → -97%"),
    ("ZOOM", "Zoom Video",         "4y",  "ZM",    "Oct 2020 peak → -90%"),
    ("HOOD", "Robinhood",          "3y",  "HOOD",  "Aug 2021 IPO peak → -85%"),
    ("SNAP", "Snapchat",           "3y",  "SNAP",  "2021 peak → -90%"),
    ("COIN", "Coinbase",           "3y",  "COIN",  "Nov 2021 peak → -85%"),
    ("ARKK", "ARK Innovation ETF", "4y",  "ARKK",  "Feb 2021 peak → -75%"),
]

# Hardcoded data for bankrupt / delisted companies
CRASH_STOCKS_BANKRUPT = [
    {
        "ticker":  "ENRN",
        "company": "Enron Corporation",
        "label":   "ENRON",
        "note":    "Bankrupt Dec 2001 — accounting fraud",
        # Monthly prices: 2000-01 to 2002-01 (approximately)
        "prices":  [
            70, 75, 72, 68, 80, 85, 90, 88, 82, 76, 72, 68,  # 2000
            60, 55, 52, 48, 45, 40, 35, 28, 20, 12, 5, 0.5,  # 2001
        ],
        "invested": 10_000,
    },
    {
        "ticker":  "LEHM",
        "company": "Lehman Brothers",
        "label":   "LEHMAN BROTHERS",
        "note":    "Bankrupt Sep 2008 — financial crisis",
        "prices":  [
            82, 78, 75, 72, 68, 64, 58, 50, 40, 28, 15, 4, 0.2,
        ],
        "invested": 10_000,
    },
    {
        "ticker":  "BBBY",
        "company": "Bed Bath & Beyond",
        "label":   "BBBY",
        "note":    "Bankrupt Apr 2023",
        "period":  "3y",   # Use yfinance — it has data until delisting
        "use_yf":  True,
    },
    {
        "ticker":  "SIVB",
        "company": "Silicon Valley Bank",
        "label":   "SVB",
        "note":    "Collapsed Mar 2023 — bank run",
        "period":  "3y",
        "use_yf":  True,
    },
]


def _load_prices(entry):
    """Load price series from yfinance or hardcoded data."""
    if entry.get("use_yf", False):
        try:
            h = yf.download(entry["ticker"], period=entry.get("period","3y"),
                            interval="1mo", progress=False, auto_adjust=True)
            prices = h["Close"].squeeze().dropna().tolist()
            if len(prices) >= 6:
                return prices, True
        except:
            pass
        return None, False
    else:
        return entry["prices"], False


def _pick_crash(used=None):
    """Pick a crash scenario not recently used."""
    used = set(used or [])
    live    = [s for s in CRASH_STOCKS_LIVE     if s[0] not in used]
    bankrupt= [s for s in CRASH_STOCKS_BANKRUPT if s["ticker"] not in used]

    # Mix: 60% live, 40% bankrupt
    if not live and not bankrupt:
        live = CRASH_STOCKS_LIVE

    pool = live * 3 + ([None] * len(bankrupt))  # weight toward live
    if random.random() < 0.35 and bankrupt:
        choice = random.choice(bankrupt)
        return "bankrupt", choice
    elif live:
        choice = random.choice(live)
        return "live", choice
    else:
        choice = random.choice(bankrupt)
        return "bankrupt", choice


def _fmt(v):
    if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if v >= 1_000:     return f"${v:,.0f}"
    return f"${v:.0f}"


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


def create_loss_video(used_tickers=None):
    mode, choice = _pick_crash(used_tickers)

    if mode == "bankrupt":
        ticker  = choice["ticker"]
        company = choice["company"]
        label   = choice["label"]
        note    = choice["note"]
        prices, from_yf = _load_prices(choice)
        if prices is None:
            prices = [100, 90, 75, 55, 35, 18, 5, 1, 0.1]
        investment = 10_000
    else:
        ticker, company, period, label, note = choice
        if ticker == "ZOOM": ticker = "ZM"
        try:
            h = yf.download(ticker, period=period, interval="1mo",
                            progress=False, auto_adjust=True)
            prices = h["Close"].squeeze().dropna().tolist()
            if len(prices) < 6:
                raise ValueError("Too short")
        except Exception as e:
            print(f"  Data error for {ticker}: {e}")
            return None
        investment = 10_000

    # Calculate portfolio value over time (lump-sum at first price)
    start_price = prices[0]
    shares      = investment / start_price
    portfolio   = [shares * p for p in prices]

    final_val   = portfolio[-1]
    peak_val    = max(portfolio)
    loss_pct    = (final_val - investment) / investment * 100
    peak_loss   = (final_val - peak_val) / peak_val * 100

    print(f"  Loss scenario: {ticker} | start={_fmt(investment)} → end={_fmt(final_val)} ({loss_pct:+.1f}%)")

    n   = len(portfolio)
    lo  = min(0, min(portfolio))
    hi  = max(portfolio)
    rng = hi - lo or 1

    def vy(v): return int(CHART_B - (v - lo) / rng * (CHART_B - CHART_T))
    def ix(i): return int(CHART_L + i / (n-1) * (CHART_R - CHART_L))

    total_f = FPS * (ANIM_SECS + HOLD_SECS)
    anim_f  = FPS * ANIM_SECS
    video_path = f"{ticker}_loss.mp4"
    out = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))

    fb  = _font("arialbd.ttf", 96)
    fm  = _font("arialbd.ttf", 58)
    fs  = _font("arialbd.ttf", 44)
    fx  = _font("arialbd.ttf", 36)
    fxs = _font("arialbd.ttf", 30)

    for fi in range(total_f):
        t    = fi / FPS
        prog = min(1.0, fi / anim_f)
        hold = fi >= anim_f

        img  = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(img)
        _wavy_grid(draw, t * 0.2)

        # Warning banner
        draw.rectangle([(0, 60), (WIDTH, 145)], fill=RED)
        warn = "WHAT HAPPENED TO $10,000 IN..."
        wb   = draw.textbbox((0,0), warn, font=fxs)
        draw.text(((WIDTH-(wb[2]-wb[0]))//2, 82), warn, font=fxs, fill=WHITE)

        # Company + label
        draw.text((60, 175), label,   font=fb, fill=RED)
        draw.text((60, 300), company, font=fx, fill=GRAY)
        draw.text((60, 355), note,    font=fxs, fill=ORANGE)

        # Animated RED line
        vis  = max(2, int(prog * n))
        pts  = [(ix(i), vy(portfolio[i])) for i in range(vis)]
        if len(pts) >= 2:
            draw.line(pts, fill=RED, width=4)

        # Dot
        if pts:
            cx, cy = pts[-1]
            for r2, a in [(18, 35), (12, 70), (7, 140)]:
                glow = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
                ImageDraw.Draw(glow).ellipse((cx-r2, cy-r2, cx+r2, cy+r2), fill=(*RED, a))
                img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
                draw = ImageDraw.Draw(img)
            draw.ellipse((cx-7, cy-7, cx+7, cy+7), fill=WHITE)
            curr = portfolio[vis-1]
            draw.text((cx+12, cy-22), _fmt(curr), font=fxs, fill=WHITE)

        # Hold: summary panel
        if hold:
            py1 = HEIGHT - 460
            draw.rectangle([(60, py1), (WIDTH-60, HEIGHT-80)], fill=(20,10,10))
            draw.rectangle([(60, py1), (WIDTH-60, py1+5)],     fill=RED)

            rows = [
                ("You invested:",    _fmt(investment),      WHITE),
                ("It became:",       _fmt(final_val),       RED),
                ("Loss:",            f"{loss_pct:.1f}%",    RED),
                ("Peak loss:",       f"{peak_loss:.1f}%",   ORANGE),
            ]
            for ri, (lbl, val, col) in enumerate(rows):
                ry = py1 + 30 + ri * 85
                draw.text((80, ry), lbl, font=fx, fill=GRAY)
                vb = draw.textbbox((0,0), val, font=fs)
                draw.text((WIDTH-(vb[2]-vb[0])-80, ry), val, font=fs, fill=col)

        # Progress bar
        draw.rectangle([(0, HEIGHT-55), (WIDTH, HEIGHT)], fill=(20,20,20))
        draw.rectangle([(0, HEIGHT-55), (int(WIDTH*prog), HEIGHT)], fill=RED)

        out.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

    out.release()
    return {
        "video_path": video_path,
        "ticker":     ticker,
        "company":    company,
        "label":      label,
        "final_val":  final_val,
        "loss_pct":   loss_pct,
        "investment": investment,
    }
