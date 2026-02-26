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

from stock_chart    import create_video as create_single_video
from bar_chart_race import create_race_video, SECTORS, _fmt
from dividend_video import create_dividend_video
from tts_helper     import (
    generate_tts, merge_audio_video,
    build_narration, build_race_narration,
)

# ── Stock universe (single-stock videos) ──────────────────────────────────────
SINGLE_STOCKS = [
    # Mega-cap tech
    "NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA",
    # Chips
    "AMD", "AVGO", "QCOM", "INTC", "MU",
    # Internet
    "NFLX", "SHOP", "UBER", "SPOT", "RBLX",
    # Finance / payments
    "V", "MA", "JPM", "GS", "COIN", "SQ",
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
    "COIN": "Coinbase", "SQ":   "Block",       "QQQ":  "the Nasdaq ETF",
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

# Video type rotation — repeats every 3: single, race, dividend
VIDEO_SCHEDULE = [0, 1, 2]   # indices: 0=single, 1=race, 2=dividend

SECTORS_ORDER = ["tech", "realestate", "healthcare", "finance", "energy", "consumer"]


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
        f"If You Invested ${inv:,.0f} in {ticker} {years} Years Ago... \U0001f631",
        f"{ticker}: ${inv:,.0f} \u2192 {_fmt(end)} in {years} Years \U0001f4c8",
        f"What ${inv:,.0f} in {company} {years} Years Ago Looks Like Today \U0001f92f",
        f"{company} Stock Growth: ${inv:,.0f} Became {_fmt(end)} \U0001f680",
        f"${inv:,.0f} in {ticker} {years} Yrs Ago = {_fmt(end)} Today ({pct:+.0f}%)",
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
        f"#stocks #investing #{ticker} #stockmarket #wealth #finance "
        f"#shorts #investing101 #stockcharts #wallstreet #money"
    )


def _race_title(winner: str, winner_label: str, end: float, inv: float, years: int) -> str:
    opts = [
        f"${inv:,.0f} in Every Stock {years} Years Ago \u2014 Who Won? \U0001f3c6",
        f"The {years}-Year Stock Race: {winner_label} DOMINATES \U0001f4c8",
        f"Which Stock Turned ${inv:,.0f} Into the MOST? ({years} Years) \U0001f92f",
        f"{winner_label} vs Everyone: {years}-Year ${inv:,.0f} Challenge \U0001f680",
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
        f"#stocks #investing #stockrace #barchartrace #stockmarket #finance "
        f"#shorts #wealth #nvda #aapl #tsla #investing101"
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
                            "stockmarket", "wealth", "money"],
            "categoryId":  "25",
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

    MODE_NAMES = {0: "SINGLE STOCK", 1: "BAR CHART RACE", 2: "DIVIDEND"}
    print(f"=== Stock Bot | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")
    print(f"Mode: {MODE_NAMES[video_type]}")

    final_path = None

    if video_type == 1:
        # ── Bar chart race ────────────────────────────────────────
        # Rotate through sectors
        sector_idx = used.get("race_count", 0) % len(SECTORS_ORDER)
        sector     = SECTORS_ORDER[sector_idx]
        print(f"  Sector: {sector}")

        result   = create_race_video(sector=sector, investment=INVESTMENT, years=YEARS)
        raw_path = result["video_path"]

        narration = build_race_narration(result["sector_label"], INVESTMENT, YEARS)
        print(f"  Narration: {narration}")
        mp3 = "race_speech.mp3"
        try:
            generate_tts(narration, mp3)
            final_path = f"race_{sector}_final.mp4"
            final_path = merge_audio_video(raw_path, mp3, final_path)
            if os.path.exists(mp3):
                os.remove(mp3)
        except Exception as e:
            print(f"  TTS skipped: {e}")
            final_path = raw_path

        title = _race_title(result["winner"], result["winner_label"],
                            result["end_val"], INVESTMENT, YEARS)
        desc  = _race_desc(result["winner"], result["winner_label"],
                           result["end_val"], INVESTMENT, YEARS, sector)

        used["race_count"] = used.get("race_count", 0) + 1

    elif video_type == 2:
        # ── Dividend comparison ───────────────────────────────────
        used_pairs  = used.get("dividend_pairs", [])
        # avoid recently used pairs (track by "T1_T2" key)
        avail_pairs = [p for p in DIVIDEND_PAIRS
                       if f"{p[0]}_{p[1]}" not in used_pairs[-6:]]
        if not avail_pairs:
            avail_pairs = DIVIDEND_PAIRS
        t1, t2, category = random.choice(avail_pairs)
        print(f"  Dividend pair: {t1} vs {t2}  [{category}]")

        result   = create_dividend_video(ticker=t1, compare_ticker=t2,
                                         investment=INVESTMENT)
        raw_path = result["video_path"]

        # Short TTS — no spoilers
        narration = (
            f"Ten thousand dollars in {t1} versus {t2}. "
            f"Same start date. Which one pays more?"
        )
        mp3 = "div_speech.mp3"
        try:
            generate_tts(narration, mp3)
            final_path = f"{t1}_vs_{t2}_final.mp4"
            final_path = merge_audio_video(raw_path, mp3, final_path)
            if os.path.exists(mp3):
                os.remove(mp3)
        except Exception as e:
            print(f"  TTS skipped: {e}")
            final_path = raw_path

        s1  = result
        s2  = result["compare"]
        mth = f"${s1['monthly']:,.0f}"
        title_opts = [
            f"{t1} vs {t2}: Which Pays More? ({category}) \U0001f4b0",
            f"${INVESTMENT:,} in {t1} vs {t2} — Dividend Showdown! \U0001f4c8",
            f"{t1} or {t2}? Best Monthly Income on ${INVESTMENT:,} \U0001f4ca",
            f"{category}: {t1} vs {t2} — Which Wins? \U0001f3c6",
        ]
        title = random.choice(title_opts)
        winner = t1 if s1["monthly"] >= s2["monthly"] else t2
        desc  = (
            f"${INVESTMENT:,} invested in {t1} vs {t2} — same start date, fair comparison!\n\n"
            f"{t1}:\n"
            f"  Portfolio : ${s1['portfolio']:,.0f}\n"
            f"  Monthly   : ${s1['monthly']:,.0f}/mo\n"
            f"  DRIP      : ${s1['drip']:,.0f}\n\n"
            f"{t2}:\n"
            f"  Portfolio : ${s2['portfolio']:,.0f}\n"
            f"  Monthly   : ${s2['monthly']:,.0f}/mo\n"
            f"  DRIP      : ${s2['drip']:,.0f}\n\n"
            f"NOT financial advice. Always do your own research.\n\n"
            f"#{t1} #{t2} #dividends #passiveincome #investing #shorts #finance #{category.replace(' ','').replace('—','')}"
        )
        used.setdefault("dividend_pairs", []).append(f"{t1}_{t2}")

    else:
        # ── Single stock ──────────────────────────────────────────
        ticker  = _pick_stock(used.get("single", []))
        company = COMPANY_NAMES.get(ticker, ticker)
        print(f"Ticker: {ticker} ({company})")

        result   = create_single_video(ticker, investment=INVESTMENT, years=YEARS)
        raw_path = result["video_path"]

        # Short TTS — no final value spoiler
        narration = build_narration(ticker, company, INVESTMENT, YEARS)
        print(f"  Narration: {narration}")
        mp3 = "speech.mp3"
        try:
            generate_tts(narration, mp3)
            final_path = f"{ticker}_final.mp4"
            final_path = merge_audio_video(raw_path, mp3, final_path)
            if os.path.exists(mp3):
                os.remove(mp3)
        except Exception as e:
            print(f"  TTS skipped: {e}")
            final_path = raw_path

        title = _single_title(ticker, INVESTMENT, result["end_value"],
                               result["gain_pct"], YEARS)
        desc  = _single_desc(ticker, INVESTMENT, result["end_value"],
                              result["gain_pct"], YEARS)
        used.setdefault("single", []).append(ticker)

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
