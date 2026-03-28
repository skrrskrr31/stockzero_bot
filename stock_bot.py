"""
stock_bot.py - Main orchestrator
Picks video type (single-stock OR bar chart race), renders, adds TTS narration,
uploads to YouTube.

GitHub Secrets:
  TOKEN_JSON   — base64-encoded OAuth token JSON
"""

import base64
import json
import os
import random
import subprocess
import sys
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from trending_video import create_trending_video
from dca_video      import create_dca_video
from loss_video     import create_loss_video
from buffett_video  import create_buffett_video
from tts_helper     import (
    generate_tts, merge_audio_video,
    build_narration, build_race_narration,
)

def _fmt(v):
    if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if v >= 1_000:     return f"${v:,.0f}"
    return f"${v:.0f}"

# ── Stock universe (single-stock videos) ──────────────────────────────────────
SINGLE_STOCKS = [
    # Mega-cap tech
    "NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA",
    # Chips
    "AMD", "AVGO", "QCOM", "INTC", "MU",
    # Internet
    "NFLX", "SHOP", "UBER", "SPOT", "RBLX",
    # Finance / payments
    "V", "MA", "JPM", "GS", "COIN", "PYPL",
    # ETFs
    "QQQ", "SPY", "VTI",
    # Growth
    "PLTR", "CRWD", "DDOG", "SNOW",
    # Energy / pharma
    "XOM", "NEE", "LLY", "ABBV",
]

# Company long names for TTS (falls back to ticker if missing)
COMPANY_NAMES = {
    "NVDA": "NVIDIA",   "AAPL": "Apple",     "MSFT": "Microsoft",
    "GOOGL": "Google",  "META": "Meta",       "AMZN": "Amazon",
    "TSLA": "Tesla",    "AMD": "AMD",         "NFLX": "Netflix",
    "AVGO": "Broadcom", "QCOM": "Qualcomm",   "INTC": "Intel",
    "MU":   "Micron",   "SHOP": "Shopify",    "UBER": "Uber",
    "SPOT": "Spotify",  "RBLX": "Roblox",     "V":    "Visa",
    "MA":   "Mastercard","JPM": "JPMorgan",   "GS":   "Goldman Sachs",
    "COIN": "Coinbase", "PYPL": "PayPal",       "QQQ":  "the Nasdaq ETF",
    "SPY":  "the S&P 500 ETF",                 "VTI":  "Vanguard Total Market ETF",
    "PLTR": "Palantir", "CRWD": "CrowdStrike","DDOG": "Datadog",
    "SNOW": "Snowflake","XOM":  "Exxon Mobil","NEE":  "NextEra Energy",
    "LLY":  "Eli Lilly","ABBV": "AbbVie",
}

USED_FILE  = "kullanilan_hisseler.json"
INVESTMENT = 10_000
YEARS      = 10

# ── Dividend ETF pairs (both must pay dividends, same category) ───────────────
# Format: (ticker1, ticker2, "Category Label")
# Both ETFs in each pair pay monthly/quarterly dividends.
# Code automatically aligns to the newer ETF's launch date for fair comparison.
DIVIDEND_PAIRS = [
    # Covered Call ETFs (monthly, Nasdaq-based)
    ("JEPQ",  "QYLD",  "Covered Call — Nasdaq"),
    # Covered Call ETFs (monthly, S&P 500-based)
    ("JEPI",  "XYLD",  "Covered Call — S&P 500"),
    # JEPQ vs JEPI (most popular comparison)
    ("JEPQ",  "JEPI",  "Covered Call — JEPQ vs JEPI"),
    # Dividend Growth ETFs
    ("SCHD",  "VYM",   "Dividend Growth ETF"),
    ("DGRO",  "VIG",   "Dividend Growth ETF"),
    ("DVY",   "HDV",   "High Dividend ETF"),
    ("SPHD",  "SPYD",  "S&P High Dividend ETF"),
    # High Yield Income ETFs
    ("RYLD",  "DIVO",  "High Yield Income ETF"),
    # REIT ETFs (monthly distributions)
    ("O",     "STAG",  "Monthly REIT"),
    ("VNQ",   "IYR",   "REIT ETF"),
    # Preferred Stock (monthly)
    ("PFF",   "PFFD",  "Preferred Stock ETF"),
    # International Dividend
    ("VYMI",  "IDV",   "International Dividend ETF"),
    # Bond Income
    ("HYG",   "LQD",   "Bond Income ETF"),
]

# Video type rotation — 4 types: trending, DCA, loss, buffett
VIDEO_SCHEDULE = [0, 1, 2, 3]   # 0=trending, 1=dca, 2=loss, 3=buffett


# ── Used-stock tracker ────────────────────────────────────────────────────────
def _load_used() -> dict:
    if os.path.exists(USED_FILE):
        with open(USED_FILE) as f:
            return json.load(f)
    return {"single": [], "race_count": 0, "total": 0}


def _save_used(data: dict):
    data["single"] = data["single"][-50:]
    with open(USED_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _pick_stock(used_single: list) -> str:
    recent    = set(used_single[-25:])
    available = [s for s in SINGLE_STOCKS if s not in recent]
    return random.choice(available or SINGLE_STOCKS)


# ── Title / description ────────────────────────────────────────────────────────
def _single_title(ticker: str, inv: float, end: float, pct: float, years: int) -> str:
    company = COMPANY_NAMES.get(ticker, ticker)
    opts = [
        f"If You Invested ${inv:,.0f} in {ticker} {years} Years Ago... \U0001f631 #Shorts",
        f"{ticker}: ${inv:,.0f} \u2192 {_fmt(end)} in {years} Years \U0001f4c8 #Shorts",
        f"What ${inv:,.0f} in {company} {years} Years Ago Looks Like Today \U0001f92f #Shorts",
        f"{company} Stock Growth: ${inv:,.0f} Became {_fmt(end)} \U0001f680 #Shorts",
        f"${inv:,.0f} in {ticker} {years} Yrs Ago = {_fmt(end)} Today ({pct:+.0f}%) #Shorts",
    ]
    return random.choice(opts)


def _single_desc(ticker: str, inv: float, end: float, pct: float, years: int) -> str:
    company = COMPANY_NAMES.get(ticker, ticker)
    return (
        f"${inv:,.0f} invested in {company} ({ticker}) {years} years ago would now be "
        f"worth {_fmt(end)} \u2014 a {pct:+.1f}% return!\n\n"
        f"This animation shows the year-by-year growth of a ${inv:,.0f} lump-sum "
        f"investment in {ticker} stock over the past {years} years.\n\n"
        f"\u26a0\ufe0f NOT financial advice. Past performance \u2260 future results. "
        f"Always do your own research.\n\n"
        f"\U0001f514 Follow for daily stock breakdowns!\n\n"
        f"#Shorts #stocks #investing #{ticker} #stockmarket #wealth #finance "
        f"#investing101 #stockcharts #wallstreet #money #stockanalysis #personalfinance"
    )


def _race_title(winner: str, winner_label: str, end: float, inv: float, years: int) -> str:
    opts = [
        f"${inv:,.0f} in Every Stock {years} Years Ago \u2014 Who Won? \U0001f3c6 #Shorts",
        f"The {years}-Year Stock Race: {winner_label} DOMINATES \U0001f4c8 #Shorts",
        f"Which Stock Turned ${inv:,.0f} Into the MOST? ({years} Years) \U0001f92f #Shorts",
        f"{winner_label} vs Everyone: {years}-Year ${inv:,.0f} Challenge \U0001f680 #Shorts",
    ]
    return random.choice(opts)


def _race_desc(winner: str, winner_label: str, end: float, inv: float, years: int,
               sector: str = "tech") -> str:
    tickers = list(SECTORS.get(sector, {}).get("stocks", {}).keys())
    featured = ", ".join(tickers) if tickers else ""
    featured_line = f"Stocks featured: {featured}\n\n" if featured else ""
    return (
        f"We invested ${inv:,.0f} in {len(tickers) or 'top'} top stocks {years} years ago. "
        f"The winner? {winner_label} ({winner}) with {_fmt(end)}!\n\n"
        f"Watch the animated bar chart race to see how rankings changed over the years.\n\n"
        f"\u26a0\ufe0f NOT financial advice. Past performance \u2260 future results.\n\n"
        f"{featured_line}"
        f"\U0001f514 Follow for daily stock breakdowns!\n\n"
        f"#Shorts #stocks #investing #stockrace #barchartrace #stockmarket #finance "
        f"#wealth #nvda #aapl #tsla #investing101 #stockanalysis #personalfinance"
    )


# ── YouTube upload ─────────────────────────────────────────────────────────────
def _upload(video_path: str, title: str, description: str, token_str: str) -> str:
    data  = json.loads(token_str)
    creds = Credentials(
        token=data["token"], refresh_token=data["refresh_token"],
        token_uri=data["token_uri"], client_id=data["client_id"],
        client_secret=data["client_secret"],
    )
    yt   = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title":       title,
            "description": description,
            "tags":        ["stocks", "investing", "finance", "shorts",
                            "stockmarket", "wealth", "money", "stock market",
                            "investing for beginners", "financial education",
                            "passive income", "stock analysis", "personal finance",
                            "how to invest", "stock chart"],
            "categoryId":  "26",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media    = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request  = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    print("  Uploading to YouTube...")
    response = None
    while response is None:
        _, response = request.next_chunk()
    vid_id = response["id"]
    print(f"  https://youtube.com/shorts/{vid_id}")
    return vid_id


# ── ffmpeg compress ───────────────────────────────────────────────────────────
def _compress(src: str) -> str:
    dst = src.replace(".mp4", "_enc.mp4")
    r   = subprocess.run(
        ["ffmpeg", "-y", "-i", src,
         "-vcodec", "libx264", "-crf", "22", "-preset", "fast",
         "-acodec", "aac", "-b:a", "128k", dst],
        capture_output=True,
    )
    if r.returncode == 0 and os.path.exists(dst):
        os.remove(src)
        return dst
    return src


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    token_b64 = os.environ.get("TOKEN_JSON", "")
    if not token_b64:
        print("ERROR: TOKEN_JSON not set.")
        sys.exit(1)

    try:
        token_str = base64.b64decode(token_b64).decode()
    except Exception:
        token_str = token_b64

    used       = _load_used()
    total      = used.get("total", 0)
    video_type = VIDEO_SCHEDULE[total % len(VIDEO_SCHEDULE)]

    MODE_NAMES = {0: "TRENDING", 1: "DCA", 2: "LOSS SCENARIO", 3: "BUFFETT"}
    print(f"=== Stock Bot | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")
    print(f"Mode: {MODE_NAMES[video_type]}")

    final_path = raw_path = None
    title = desc = ""

    if video_type == 0:
        # ── Trending stock ────────────────────────────────────────
        used_t = used.get("trending", [])
        result = create_trending_video(used_tickers=used_t)
        if result is None:
            print("ERROR: trending video failed"); sys.exit(1)
        raw_path = result["video_path"]
        ticker   = result["ticker"]
        company  = result["company"]
        pct      = result["pct_change"]
        dir_     = result["direction"]
        sign     = "+" if pct > 0 else ""
        arrow    = "📈" if dir_ == "gainer" else "📉"

        title_opts = [
            f"{ticker} IS {dir_.upper()}ING {sign}{pct:.1f}% TODAY! {arrow} #Shorts",
            f"Why Is {company} Stock Moving? {sign}{pct:.1f}% {arrow} #Shorts",
            f"TODAY'S TOP STOCK MOVER: {ticker} {sign}{pct:.1f}% {arrow} #Shorts",
            f"{ticker} {sign}{pct:.1f}% — What's Happening? {arrow} #Shorts",
        ]
        title = random.choice(title_opts)
        desc  = (
            f"{company} ({ticker}) moved {sign}{pct:.1f}% today!\n\n"
            f"Watch the animated chart to see today's price action and 30-day trend.\n\n"
            f"⚠️ NOT financial advice. Always do your own research.\n\n"
            f"🔔 Follow for daily stock movers!\n\n"
            f"#Shorts #stocks #{ticker} #{company.replace(' ','')} #stockmarket "
            f"#investing #finance #daytrading #stocknews #wallstreet #trading"
        )
        used.setdefault("trending", []).append(ticker)
        used["trending"] = used["trending"][-30:]
        final_path = raw_path

    elif video_type == 1:
        # ── DCA ───────────────────────────────────────────────────
        used_t   = used.get("dca", [])
        MONTHLY  = random.choice([50, 100, 100, 200])   # vary amount
        YEARS_D  = random.choice([5, 10, 10, 15])
        result   = create_dca_video(monthly=MONTHLY, years=YEARS_D, used_tickers=used_t)
        if result is None:
            print("ERROR: DCA video failed"); sys.exit(1)
        raw_path = result["video_path"]
        ticker   = result["ticker"]
        company  = result["company"]
        total_in = result["total_invested"]
        final_v  = result["final_value"]
        gain     = result["gain_pct"]
        color_e  = "📈" if final_v >= total_in else "📉"

        title_opts = [
            f"${MONTHLY}/Month in {ticker} for {YEARS_D} Years... {color_e} #Shorts",
            f"What ${MONTHLY}/Month in {company} Did in {YEARS_D} Years {color_e} #Shorts",
            f"DCA Strategy: ${MONTHLY}/Month in {ticker} = {_fmt(final_v)}? {color_e} #Shorts",
            f"${MONTHLY} Every Month in {ticker} for {YEARS_D} Years 🤯 #Shorts",
        ]
        title = random.choice(title_opts)
        desc  = (
            f"Investing ${MONTHLY} every month in {company} ({ticker}) for {YEARS_D} years:\n\n"
            f"  Total invested: {_fmt(total_in)}\n"
            f"  Portfolio today: {_fmt(final_v)}\n"
            f"  Return: {gain:+.1f}%\n\n"
            f"This is Dollar Cost Averaging (DCA) — investing a fixed amount regularly "
            f"regardless of the price.\n\n"
            f"⚠️ NOT financial advice. Past performance ≠ future results.\n\n"
            f"🔔 Follow for daily investing breakdowns!\n\n"
            f"#Shorts #DCA #investing #{ticker} #stockmarket #finance #wealth "
            f"#dollarcostaveraging #personalfinance #investing101 #money"
        )
        used.setdefault("dca", []).append(ticker)
        used["dca"] = used["dca"][-30:]
        final_path = raw_path

    elif video_type == 2:
        # ── Loss scenario ─────────────────────────────────────────
        used_t = used.get("loss", [])
        result = create_loss_video(used_tickers=used_t)
        if result is None:
            print("ERROR: loss video failed"); sys.exit(1)
        raw_path = result["video_path"]
        label    = result["label"]
        company  = result["company"]
        loss_pct = result["loss_pct"]
        final_v  = result["final_val"]
        invested = result["investment"]

        title_opts = [
            f"What Happened to $10,000 in {label}? 💀 #Shorts",
            f"{label} Stock Crash: $10,000 → {_fmt(final_v)} 📉 #Shorts",
            f"This Is Why People LOST Everything in {label} 😱 #Shorts",
            f"$10,000 in {label}... Here's What Happened 📉 #Shorts",
        ]
        title = random.choice(title_opts)
        desc  = (
            f"$10,000 invested in {company} ({label}):\n\n"
            f"  Starting value: ${invested:,}\n"
            f"  Ending value: {_fmt(final_v)}\n"
            f"  Total loss: {loss_pct:.1f}%\n\n"
            f"This is why diversification matters. Never put all your eggs in one basket.\n\n"
            f"⚠️ NOT financial advice. Always do your own research.\n\n"
            f"🔔 Follow to learn from market history!\n\n"
            f"#Shorts #stocks #stockcrash #{label} #investing #finance #stockmarket "
            f"#wallstreet #crash #loss #investing101 #money #personalfinance"
        )
        used.setdefault("loss", []).append(result["ticker"])
        used["loss"] = used["loss"][-20:]
        final_path = raw_path

    else:
        # ── Buffett ───────────────────────────────────────────────
        result = create_buffett_video()
        if result is None:
            print("ERROR: buffett video failed"); sys.exit(1)
        raw_path = result["video_path"]
        angle    = result.get("angle", "top5_holdings")

        if angle == "top5_holdings":
            title_opts = [
                "Warren Buffett's Top 5 Stock Holdings RIGHT NOW 💰 #Shorts",
                "What Buffett Is Holding in 2025 — Top 5 Picks 📈 #Shorts",
                "Berkshire Hathaway Portfolio: Top 5 Positions 🏆 #Shorts",
                "This Is What Warren Buffett Actually Owns 🤯 #Shorts",
            ]
        elif angle == "vs_sp500":
            brk = _fmt(result.get("brk_final", 0))
            spy = _fmt(result.get("spy_final", 0))
            title_opts = [
                f"Buffett vs S&P 500: 10 Years — Who Won? 🏆 #Shorts",
                f"Berkshire vs S&P 500: $10,000 10 Years Ago 📈 #Shorts",
                f"Did Warren Buffett Beat the Market? 🤔 #Shorts",
                f"BRK vs SPY 10 Years — Shocking Result 😱 #Shorts",
            ]
        else:
            title_opts = [
                "Buffett's $10,000 Picks: 10-Year Returns Revealed 📈 #Shorts",
                "Warren Buffett Stock Picks — Real 10-Year Returns 🚀 #Shorts",
                "$10,000 in Buffett's Top Picks 10 Years Ago 🤯 #Shorts",
                "Did Buffett's Stocks Beat the Market? 📊 #Shorts",
            ]
        title = random.choice(title_opts)
        desc  = (
            f"Warren Buffett / Berkshire Hathaway portfolio breakdown!\n\n"
            f"Based on SEC 13F filings — updated quarterly.\n\n"
            f"⚠️ NOT financial advice. Past performance ≠ future results.\n\n"
            f"🔔 Follow for daily investing breakdowns!\n\n"
            f"#Shorts #WarrenBuffett #Berkshire #investing #stocks #finance "
            f"#stockmarket #wealth #value #investing101 #money #personalfinance"
        )
        final_path = raw_path

    print(f"Title: {title}")

    # Compress + upload
    if final_path is None:
        final_path = raw_path
    final_path = _compress(final_path)
    _upload(final_path, title, desc, token_str)

    # Cleanup
    for f in [final_path, raw_path]:
        if f and os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

    used["total"] = total + 1
    _save_used(used)
    print("Done.")


if __name__ == "__main__":
    main()
