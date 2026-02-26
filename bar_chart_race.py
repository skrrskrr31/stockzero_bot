"""
bar_chart_race.py
Animated horizontal bar chart race: multiple stocks compete over 10 years.
YouTube Shorts format (1080×1920, 9:16).
Style: dark background, colored bars with company labels, dynamic x-axis.
"""

import math
import os
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont

# ── Video settings ────────────────────────────────────────────────────────────
WIDTH  = 1080
HEIGHT = 1920
FPS    = 30
FRAMES_PER_MONTH = 9   # interpolation frames between monthly snapshots
HOLD_SECS        = 4   # pause on final frame
INVESTMENT       = 10_000
YEARS            = 10

# ── Sector configs ────────────────────────────────────────────────────────────
SECTORS = {
    "tech": {
        "label": "Tech",
        "title": "Top Tech Stocks",
        "stocks": {
            "NVDA":  {"color": (76,  175,   0), "label": "NVIDIA"},
            "AAPL":  {"color": (180, 180, 180), "label": "Apple"},
            "MSFT":  {"color": (0,   130, 220), "label": "Microsoft"},
            "AMZN":  {"color": (255, 153,   0), "label": "Amazon"},
            "META":  {"color": (24,  119, 242), "label": "Meta"},
            "GOOGL": {"color": (66,  133, 244), "label": "Google"},
            "TSLA":  {"color": (210,  30,  20), "label": "Tesla"},
            "AMD":   {"color": (237,  27,  47), "label": "AMD"},
            "NFLX":  {"color": (229,   9,  20), "label": "Netflix"},
            "SPY":   {"color": (0,   160,  80), "label": "S&P 500"},
        },
    },
    "realestate": {
        "label": "Real Estate",
        "title": "Top REIT Stocks",
        "stocks": {
            "PLD":  {"color": (41,  128, 185), "label": "Prologis"},
            "AMT":  {"color": (142,  68, 173), "label": "Amer. Tower"},
            "EQIX": {"color": (231,  76,  60), "label": "Equinix"},
            "O":    {"color": (26,  188, 156), "label": "Realty Inc."},
            "PSA":  {"color": (243, 156,  18), "label": "Pub. Storage"},
            "SPG":  {"color": (39,  174,  96), "label": "Simon Prop."},
            "AVB":  {"color": (52,  152, 219), "label": "AvalonBay"},
            "DLR":  {"color": (230,  40,  40), "label": "Digital Rlty"},
            "VNQ":  {"color": (100, 100, 200), "label": "Vanguard REIT"},
            "EXR":  {"color": (255, 120,   0), "label": "Extra Space"},
        },
    },
    "healthcare": {
        "label": "Healthcare",
        "title": "Top Healthcare Stocks",
        "stocks": {
            "LLY":  {"color": (220,  20,  60), "label": "Eli Lilly"},
            "UNH":  {"color": (0,    74, 135), "label": "UnitedHealth"},
            "ABBV": {"color": (0,   112, 192), "label": "AbbVie"},
            "JNJ":  {"color": (188,  44,  25), "label": "J&J"},
            "MRK":  {"color": (0,   100, 150), "label": "Merck"},
            "AMGN": {"color": (0,   121, 107), "label": "Amgen"},
            "REGN": {"color": (255, 140,   0), "label": "Regeneron"},
            "GILD": {"color": (102,  51, 153), "label": "Gilead"},
            "BMY":  {"color": (204,   0,   0), "label": "BMS"},
            "PFE":  {"color": (0,   100, 200), "label": "Pfizer"},
        },
    },
    "finance": {
        "label": "Finance",
        "title": "Top Finance Stocks",
        "stocks": {
            "V":    {"color": (26,   69, 153), "label": "Visa"},
            "MA":   {"color": (235,   0,  27), "label": "Mastercard"},
            "JPM":  {"color": (0,    45,  98), "label": "JPMorgan"},
            "GS":   {"color": (100, 130, 180), "label": "Goldman"},
            "MS":   {"color": (32,   87, 163), "label": "Morgan S."},
            "BLK":  {"color": (0,    49, 97),  "label": "BlackRock"},
            "BRK-B":{"color": (180,  60,  20), "label": "Berkshire"},
            "BAC":  {"color": (218,  41,  28), "label": "Bank of Am."},
            "AXP":  {"color": (0,   114, 206), "label": "Amex"},
            "COIN": {"color": (0,   130, 250), "label": "Coinbase"},
        },
    },
    "energy": {
        "label": "Energy",
        "title": "Top Energy Stocks",
        "stocks": {
            "XOM":  {"color": (220,   0,   0), "label": "ExxonMobil"},
            "CVX":  {"color": (0,    94, 184), "label": "Chevron"},
            "COP":  {"color": (255, 130,   0), "label": "ConocoPhilps"},
            "SLB":  {"color": (0,   120, 100), "label": "SLB"},
            "OXY":  {"color": (180,  50,  50), "label": "Occidental"},
            "PSX":  {"color": (204, 102,   0), "label": "Phillips 66"},
            "MPC":  {"color": (150,   0,  50), "label": "Marathon"},
            "VLO":  {"color": (0,    80, 160), "label": "Valero"},
            "EOG":  {"color": (60,  140,  60), "label": "EOG Res."},
            "NEE":  {"color": (0,   150, 200), "label": "NextEra"},
        },
    },
    "consumer": {
        "label": "Consumer",
        "title": "Top Consumer Stocks",
        "stocks": {
            "AMZN": {"color": (255, 153,   0), "label": "Amazon"},
            "WMT":  {"color": (0,   113, 206), "label": "Walmart"},
            "HD":   {"color": (241,  89,  42), "label": "Home Depot"},
            "COST": {"color": (0,    68, 127), "label": "Costco"},
            "NKE":  {"color": (0,     0,   0), "label": "Nike"},
            "MCD":  {"color": (255, 188,  13), "label": "McDonald's"},
            "SBUX": {"color": (0,   112,  74), "label": "Starbucks"},
            "TGT":  {"color": (204,   0,   0), "label": "Target"},
            "LOW":  {"color": (0,    94, 184), "label": "Lowe's"},
            "TJX":  {"color": (200,  30,  30), "label": "TJX"},
        },
    },
}

# Default race (for backward compatibility)
RACE_STOCKS = SECTORS["tech"]["stocks"]

# ── Layout ────────────────────────────────────────────────────────────────────
LABEL_W  = 148   # left column: ticker labels
VALUE_W  = 185   # right column: value labels
CHART_L  = LABEL_W
CHART_R  = WIDTH - VALUE_W
CHART_T  = 250
CHART_B  = HEIGHT - 310

N        = len(RACE_STOCKS)
BAR_H    = 80
BAR_GAP  = 24
ROW_H    = BAR_H + BAR_GAP

# ── Colors ────────────────────────────────────────────────────────────────────
BG      = (10,  10,  10)
WHITE   = (255, 255, 255)
GRAY    = (100, 100, 100)
DGRAY   = (45,  45,  45)
LYEAR   = (42,  42,  42)   # year label color

# ── Font dir (patched to Linux in CI) ────────────────────────────────────────
_FONT_DIR = "C:/Windows/Fonts/"

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    p = _FONT_DIR + name
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()

# ── Helpers ───────────────────────────────────────────────────────────────────
def _ease(t: float) -> float:
    """Cubic ease-in-out for smooth rank transitions."""
    t = max(0.0, min(1.0, t))
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2)**3 / 2

def _fmt(v: float) -> str:
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.1f}K"
    return f"${v:.0f}"

def _rank_y(rank: int, n: int) -> float:
    """Y-center of bar at given rank (0 = top winner)."""
    total_h = n * ROW_H
    top_y   = CHART_T + (CHART_B - CHART_T - total_h) / 2
    return top_y + rank * ROW_H + BAR_H / 2

# ── Data ──────────────────────────────────────────────────────────────────────
def _fetch_monthly(tickers: list, investment: float, years: int) -> pd.DataFrame:
    end   = datetime.now()
    start = end.replace(year=end.year - years)
    print(f"Fetching {years}-year data for {len(tickers)} tickers...")

    raw = yf.download(
        tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )

    # Robust extraction: handle both (Price, Ticker) and (Ticker, Price) MultiIndex
    if isinstance(raw.columns, pd.MultiIndex):
        first_col = raw.columns[0]
        if first_col[1] in ("Open", "High", "Low", "Close", "Volume"):
            # (Ticker, Price) structure → yfinance 1.x
            close = raw.xs("Close", axis=1, level=1)
        else:
            # (Price, Ticker) structure → older yfinance
            close = raw["Close"]
    else:
        close = raw[["Close"]]
        close.columns = tickers

    # Ensure all tickers are columns
    for t in tickers:
        if t not in close.columns:
            print(f"  Warning: {t} not found in data, skipping")

    # Save the actual last trading date BEFORE resampling
    actual_last_date = close.dropna(how="all").index[-1].to_pydatetime()

    monthly = close.resample("ME").last()

    # Portfolio values: investment / first_price * price_at_t
    port = pd.DataFrame(index=monthly.index, dtype=float)
    for t in tickers:
        if t not in monthly.columns:
            continue
        s = monthly[t].dropna()
        if len(s) < 6:
            continue
        shares     = investment / float(s.iloc[0])
        port[t]    = s * shares

    # Forward-fill any NaN gaps (handles late IPO stocks)
    port = port.ffill()
    # Fill remaining NaN (before stock existed) with $0
    port = port.fillna(0.0)
    # Attach actual last trading date as metadata
    port.attrs["actual_last_date"] = actual_last_date
    return port

# ── Frame renderer ─────────────────────────────────────────────────────────────
def _render_frame(
    values:        dict,        # {ticker: portfolio_value}
    y_pos:         dict,        # {ticker: y_center (already interpolated)}
    dyn_max:       float,       # x-axis right edge
    date:          datetime,
    progress:      float,       # 0..1 for progress bar
    stock_cfg:     dict = None, # sector stock config
    title_str:     str  = None, # chart title
    data_end_date: datetime = None,  # last data date for "Data as of" label
) -> np.ndarray:

    img  = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    f_title  = _font("arialbd.ttf", 60)
    f_sub    = _font("arial.ttf",   38)
    f_tick   = _font("arialbd.ttf", 36)
    f_lbl    = _font("arialbd.ttf", 34)
    f_val    = _font("arialbd.ttf", 38)
    f_axis   = _font("arial.ttf",   30)
    f_year   = _font("arialbd.ttf", 185)
    f_mon    = _font("arial.ttf",   62)

    if stock_cfg is None:
        stock_cfg = RACE_STOCKS

    # ── Title ─────────────────────────────────────────────────────
    t_main = title_str or "Top Stocks"
    tw    = draw.textlength(t_main, font=f_title)
    draw.text(((WIDTH - tw) / 2, 45), t_main, fill=WHITE, font=f_title)

    sub   = f"${INVESTMENT:,} Invested | {YEARS}-Year Race"
    sw    = draw.textlength(sub, font=f_sub)
    draw.text(((WIDTH - sw) / 2, 125), sub, fill=GRAY, font=f_sub)

    # ── X-axis gridlines & labels ─────────────────────────────────
    cw = CHART_R - CHART_L
    for i in range(5):
        gv  = dyn_max * i / 4
        gx  = int(CHART_L + cw * i / 4)
        draw.line([(gx, CHART_T - 15), (gx, CHART_B + 10)], fill=DGRAY, width=1)
        gl  = _fmt(gv)
        glw = draw.textlength(gl, font=f_axis)
        draw.text((gx - glw / 2, CHART_T - 50), gl, fill=GRAY, font=f_axis)

    # ── Bars ──────────────────────────────────────────────────────
    for ticker, cfg in stock_cfg.items():
        val = values.get(ticker, 0.0)
        yc  = y_pos.get(ticker, _rank_y(0, len(stock_cfg)))
        if yc is None:
            continue

        bar_px  = int(cw * val / dyn_max) if dyn_max > 0 else 0
        bar_px  = max(bar_px, 6)
        y_top   = int(yc - BAR_H / 2)
        y_bot   = int(yc + BAR_H / 2)
        x_left  = CHART_L
        x_right = CHART_L + bar_px
        color   = cfg["color"]

        # Bar body (rounded rectangle)
        draw.rounded_rectangle([x_left, y_top, x_right, y_bot],
                                radius=14, fill=color)

        # Subtle darker right edge for depth
        if bar_px > 30:
            darker = tuple(max(0, c - 50) for c in color)
            draw.rounded_rectangle(
                [x_right - 20, y_top, x_right, y_bot],
                radius=14, fill=darker
            )

        # Company label inside bar
        lbl  = cfg["label"]
        lw   = draw.textlength(lbl, font=f_lbl)
        lx   = x_left + bar_px / 2 - lw / 2
        ly   = y_top + (BAR_H - 34) / 2 - 2
        if lx < x_left + 8:
            lx = x_left + 8
        if lx + lw <= x_right - 8:
            draw.text((lx, ly), lbl, fill=WHITE, font=f_lbl)

        # Ticker name — left column
        tkw = draw.textlength(ticker, font=f_tick)
        draw.text(
            (CHART_L - tkw - 10, y_top + (BAR_H - 36) / 2),
            ticker, fill=GRAY, font=f_tick,
        )

        # Value — right column
        v_str = _fmt(val)
        draw.text(
            (x_right + 10, y_top + (BAR_H - 38) / 2),
            v_str, fill=WHITE, font=f_val,
        )

    # ── Year label (large, bottom-right) ─────────────────────────
    yr_str = date.strftime("%Y")
    yw     = draw.textlength(yr_str, font=f_year)
    draw.text((WIDTH - yw - 25, HEIGHT - 295), yr_str, fill=LYEAR, font=f_year)

    mo_str = date.strftime("%b")
    mw     = draw.textlength(mo_str, font=f_mon)
    draw.text((WIDTH - mw - 30, HEIGHT - 295 - 70), mo_str, fill=(55, 55, 55), font=f_mon)

    # ── "Data as of" label ────────────────────────────────────────
    if data_end_date is not None:
        f_as_of   = _font("arial.ttf", 26)
        as_of_str = f"Data as of {data_end_date.strftime('%b %d, %Y')}"
        aow = draw.textlength(as_of_str, font=f_as_of)
        draw.text((WIDTH - aow - 20, HEIGHT - 70), as_of_str,
                  fill=(50, 50, 50), font=f_as_of)

    # ── Progress bar ─────────────────────────────────────────────
    bx1, bx2, by = 85, WIDTH - 85, HEIGHT - 50
    bar_len = int((bx2 - bx1) * progress)
    draw.rectangle([bx1, by, bx2, by + 8], fill=(40, 40, 40))
    if bar_len > 0:
        draw.rectangle([bx1, by, bx1 + bar_len, by + 8], fill=(210, 0, 0))

    return np.array(img)

# ── Main ──────────────────────────────────────────────────────────────────────
def create_race_video(
    sector:     str   = "tech",
    tickers:    list  = None,
    investment: float = INVESTMENT,
    years:      int   = YEARS,
    out_path:   str   = None,
) -> dict:
    """
    Render the bar chart race video for a given sector.
    sector: one of 'tech', 'realestate', 'healthcare', 'finance', 'energy', 'consumer'
    Returns dict with winner, end_val, video_path, sector_label.
    """
    sector_cfg  = SECTORS.get(sector, SECTORS["tech"])
    stock_cfg   = sector_cfg["stocks"]
    sector_lbl  = sector_cfg["label"]
    sector_title= sector_cfg["title"]

    if tickers is None:
        tickers = list(stock_cfg.keys())
    if out_path is None:
        out_path = f"stock_race_{sector}.mp4"


    # ── Fetch & prepare data ──────────────────────────────────────
    port = _fetch_monthly(tickers, investment, years)
    # keep only tickers we have data for
    valid = [t for t in tickers if t in port.columns]
    port  = port[valid]

    dates         = list(port.index.to_pydatetime())
    n_months      = len(dates)
    # Use the actual last trading day, not the month-end label
    data_end_date = port.attrs.get("actual_last_date", dates[-1])
    print(f"  {n_months} monthly snapshots  |  Data as of {data_end_date.strftime('%b %d, %Y')}")

    # Precompute sorted rank at each month
    def sorted_tickers(t_idx):
        row = port.iloc[t_idx]
        return row.sort_values(ascending=False).index.tolist()

    rank_orders = [sorted_tickers(i) for i in range(n_months)]

    # ── Video writer ──────────────────────────────────────────────
    total_anim = (n_months - 1) * FRAMES_PER_MONTH
    total_hold = int(HOLD_SECS * FPS)
    total_all  = total_anim + total_hold
    print(f"  Rendering {total_all} frames ({total_all / FPS:.0f}s)...")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, FPS, (WIDTH, HEIGHT))

    global_frame = 0

    for t_idx in range(n_months - 1):
        vals_a = port.iloc[t_idx].to_dict()
        vals_b = port.iloc[t_idx + 1].to_dict()
        rank_a = rank_orders[t_idx]
        rank_b = rank_orders[t_idx + 1]
        n_v    = len(valid)

        for f in range(FRAMES_PER_MONTH):
            alpha  = f / FRAMES_PER_MONTH
            ea     = _ease(alpha)
            prog   = global_frame / total_all

            # Interpolate bar widths (linear)
            cur_vals = {
                tk: vals_a.get(tk, 0) + (vals_b.get(tk, 0) - vals_a.get(tk, 0)) * alpha
                for tk in valid
            }

            # Interpolate bar y-positions (eased, by rank)
            cur_y = {}
            for rank_idx, tk in enumerate(rank_b):
                y_target = _rank_y(rank_idx, n_v)
                try:
                    prev_rank = rank_a.index(tk)
                except ValueError:
                    prev_rank = rank_idx
                y_source  = _rank_y(prev_rank, n_v)
                cur_y[tk] = y_source + (y_target - y_source) * ea

            # Dynamic x-axis max: current leader × 1.18
            dyn_max = max(cur_vals.values(), default=1) * 1.18

            frame = _render_frame(cur_vals, cur_y, dyn_max, dates[t_idx], prog,
                                  stock_cfg=stock_cfg, title_str=sector_title,
                                  data_end_date=data_end_date)
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            global_frame += 1

        if t_idx % 12 == 0:
            print(f"    Month {t_idx + 1}/{n_months - 1}  ({dates[t_idx].strftime('%Y-%m')})")

    # ── Hold on final frame ───────────────────────────────────────
    final_vals = port.iloc[-1].to_dict()
    final_rank = rank_orders[-1]
    n_v        = len(valid)
    final_y    = {tk: _rank_y(final_rank.index(tk), n_v) for tk in final_rank}
    dyn_max    = max(final_vals.values(), default=1) * 1.18

    for _ in range(total_hold):
        frame = _render_frame(final_vals, final_y, dyn_max, dates[-1], progress=1.0,
                              stock_cfg=stock_cfg, title_str=sector_title,
                              data_end_date=data_end_date)
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

    writer.release()

    winner  = max(final_vals, key=lambda k: final_vals.get(k, 0))
    end_val = final_vals[winner]
    print(f"  Winner: {winner} — {_fmt(end_val)}")
    print(f"  Saved: {out_path}")

    return {
        "winner":       winner,
        "winner_label": stock_cfg.get(winner, {}).get("label", winner),
        "sector":       sector,
        "sector_label": sector_lbl,
        "end_val":      end_val,
        "investment":   investment,
        "years":        years,
        "video_path":   out_path,
    }


if __name__ == "__main__":
    result = create_race_video()
    print(result)
