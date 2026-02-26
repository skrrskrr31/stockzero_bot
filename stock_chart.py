"""
stock_chart.py - Animated stock chart video generator (YouTube Shorts 9:16)
Style: Dark background, wavy grid, green animated line, white dot, progress bar
"""

import math
import os
from datetime import datetime

import cv2
import numpy as np
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont

# ── Video Settings ────────────────────────────────────────────────────────────
WIDTH  = 1080
HEIGHT = 1920
FPS    = 30
ANIM_SECS  = 20   # chart draws over this duration
HOLD_SECS  = 4    # pause on final frame

# ── Layout ────────────────────────────────────────────────────────────────────
CHART_L = 85
CHART_R = WIDTH - 85
CHART_T = 420
CHART_B = HEIGHT - 270

# ── Colors (RGB) ──────────────────────────────────────────────────────────────
BG    = (8,   8,   8)
GRID  = (28,  28,  28)
GREEN = (0,   215, 55)
WHITE = (255, 255, 255)
GRAY  = (110, 110, 110)
RED   = (215, 0,   0)

# ── Fonts (Windows) ───────────────────────────────────────────────────────────
_FONT_DIR = "C:/Windows/Fonts/"

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = _FONT_DIR + name
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ── Stock data ────────────────────────────────────────────────────────────────
def fetch_prices(ticker: str, years: int = 10):
    end   = datetime.now()
    start = end.replace(year=end.year - years)
    df = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    prices = df["Close"].squeeze().dropna()
    if len(prices) < 100:
        raise ValueError(f"Not enough data for {ticker} ({len(prices)} rows)")
    return prices


def investment_series(prices, amount: float = 10_000):
    """Return portfolio value over time for a lump-sum investment."""
    shares = amount / float(prices.iloc[0])
    return prices * shares


# ── Wavy grid ─────────────────────────────────────────────────────────────────
def _draw_wavy_grid(draw: ImageDraw.ImageDraw, t: float = 0.0):
    """Draw the distorted grid lines (style from reference screenshots)."""
    cols, rows = 6, 7
    cw = CHART_R - CHART_L
    ch = CHART_B - CHART_T

    # vertical lines
    for c in range(cols + 1):
        x0 = CHART_L + cw * c / cols
        pts = []
        for y in range(CHART_T, CHART_B + 2, 10):
            dx = math.sin((y / 130.0 + t + c * 0.6) * 1.9) * 10
            pts.append((int(x0 + dx), y))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=GRID, width=1)

    # horizontal lines
    for r in range(rows + 1):
        y0 = CHART_T + ch * r / rows
        pts = []
        for x in range(CHART_L, CHART_R + 2, 10):
            dy = math.sin((x / 130.0 + t + r * 0.6) * 1.9) * 10
            pts.append((x, int(y0 + dy)))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=GRID, width=1)


# ── Coordinate helpers ────────────────────────────────────────────────────────
def _make_transforms(values: list):
    vmin, vmax = min(values), max(values)
    pad = (vmax - vmin) * 0.13
    y_lo, y_hi = vmin - pad, vmax + pad
    n = len(values)

    def sx(idx):
        return int(CHART_L + (CHART_R - CHART_L) * idx / (n - 1))

    def sy(v):
        return int(CHART_B - (CHART_B - CHART_T) * (v - y_lo) / (y_hi - y_lo))

    return sx, sy


# ── Single frame renderer ─────────────────────────────────────────────────────
def _render_frame(
    frame_idx: int,
    anim_frames: int,
    values: list,
    dates: list,
    ticker: str,
    investment: float,
    years: int,
    hold: bool = False,
    show_summary: bool = False,
) -> np.ndarray:

    img  = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    progress = 1.0 if hold else (frame_idx / max(anim_frames - 1, 1))
    n_pts    = len(values) if hold else max(2, int(len(values) * progress))

    # Wavy grid (subtle time movement)
    t_off = frame_idx * 0.016
    _draw_wavy_grid(draw, t_off)

    sx, sy = _make_transforms(values)

    # ── Draw line ─────────────────────────────────────────────────
    pts = [(sx(i), sy(values[i])) for i in range(n_pts)]
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=GREEN, width=3)

    # ── Current dot ───────────────────────────────────────────────
    cx, cy = pts[-1]
    # glow rings
    for r, alpha in [(14, 20), (10, 50), (7, 100)]:
        overlay = Image.new("RGB", (WIDTH, HEIGHT), BG)
        od = ImageDraw.Draw(overlay)
        od.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
        img = Image.blend(img, overlay, alpha / 255)
        draw = ImageDraw.Draw(img)
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=WHITE)

    # ── Value label next to dot ───────────────────────────────────
    val_now   = values[n_pts - 1]
    val_text  = f"${val_now:,.0f}"
    f_val     = _font("arialbd.ttf", 54)
    lbl_x     = cx + 18
    lbl_y     = cy - 38
    # keep label on screen
    if lbl_x + 220 > WIDTH:
        lbl_x = cx - 230
    draw.text((lbl_x, lbl_y), val_text, fill=WHITE, font=f_val)

    # ── Ticker at top ─────────────────────────────────────────────
    f_tick = _font("arialbd.ttf", 96)
    f_sub  = _font("arial.ttf",   58)
    f_gray = _font("arial.ttf",   44)
    f_date = _font("arial.ttf",   42)

    tw = draw.textlength(ticker, font=f_tick)
    draw.text(((WIDTH - tw) / 2, 55), ticker, fill=GREEN, font=f_tick)

    yrs_str = f"{years} Years"
    yw = draw.textlength(yrs_str, font=f_sub)
    draw.text(((WIDTH - yw) / 2, 178), yrs_str, fill=WHITE, font=f_sub)

    inv_str = f"${investment:,.0f} invested"
    iw = draw.textlength(inv_str, font=f_gray)
    draw.text(((WIDTH - iw) / 2, 272), inv_str, fill=GRAY, font=f_gray)

    # ── Date label at bottom ──────────────────────────────────────
    di = min(n_pts - 1, len(dates) - 1)
    date_str = dates[di].strftime("%m/%d/%Y")
    dw = draw.textlength(date_str, font=f_date)
    draw.text(((WIDTH - dw) / 2, CHART_B + 30), date_str, fill=GRAY, font=f_date)

    # ── Summary overlay (hold phase) ──────────────────────────────
    if show_summary:
        f_big   = _font("arialbd.ttf", 80)
        f_arrow = _font("arialbd.ttf", 70)
        f_res   = _font("arialbd.ttf", 110)
        end_val = values[-1]
        gain    = (end_val - values[0]) / values[0] * 100

        summary_y = CHART_B + 110
        line1 = f"${investment:,.0f}  →"
        line2 = f"${end_val:,.0f}"
        line3 = f"+{gain:.0f}% in {years} yrs"

        l1w = draw.textlength(line1, font=f_big)
        draw.text(((WIDTH - l1w) / 2, summary_y),      line1, fill=GRAY,  font=f_big)
        l2w = draw.textlength(line2, font=f_res)
        draw.text(((WIDTH - l2w) / 2, summary_y + 95), line2, fill=GREEN, font=f_res)
        l3w = draw.textlength(line3, font=f_arrow)
        draw.text(((WIDTH - l3w) / 2, summary_y + 220),line3, fill=WHITE, font=f_arrow)

    # ── "Data as of" label ────────────────────────────────────────
    f_as_of  = _font("arial.ttf", 28)
    as_of_str = f"Data as of {dates[-1].strftime('%b %d, %Y')}"
    aow = draw.textlength(as_of_str, font=f_as_of)
    draw.text((WIDTH - aow - 20, HEIGHT - 80), as_of_str,
              fill=(55, 55, 55), font=f_as_of)

    # ── Progress bar ──────────────────────────────────────────────
    bar_y  = HEIGHT - 55
    bar_x1 = 85
    bar_x2 = WIDTH - 85
    bar_len = int((bar_x2 - bar_x1) * progress)
    draw.rectangle([bar_x1, bar_y, bar_x2,          bar_y + 8], fill=(45, 45, 45))
    if bar_len > 0:
        draw.rectangle([bar_x1, bar_y, bar_x1 + bar_len, bar_y + 8], fill=RED)

    return np.array(img)


# ── Public API ────────────────────────────────────────────────────────────────
def create_video(
    ticker: str,
    investment: float = 10_000,
    years: int = 10,
    out_path: str = None,
) -> dict:
    """
    Fetch stock data and render an animated chart MP4.
    Returns a dict with metadata (end_value, gain_pct, video_path).
    """
    if out_path is None:
        out_path = f"{ticker}_stock.mp4"

    print(f"[{ticker}] Fetching {years}-year price data...")
    prices = fetch_prices(ticker, years)
    port   = investment_series(prices, investment)

    values = port.values.tolist()
    dates  = list(port.index.to_pydatetime())

    end_val  = values[-1]
    gain_pct = (end_val - values[0]) / values[0] * 100
    print(f"  ${investment:,.0f} -> ${end_val:,.0f}  ({gain_pct:+.1f}%)")

    anim_frames = ANIM_SECS * FPS
    hold_frames = HOLD_SECS * FPS

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(out_path, fourcc, FPS, (WIDTH, HEIGHT))

    print(f"  Rendering {anim_frames + hold_frames} frames ({ANIM_SECS + HOLD_SECS}s)...")

    for i in range(anim_frames):
        if i % 90 == 0:
            print(f"    frame {i}/{anim_frames + hold_frames}")
        frame = _render_frame(i, anim_frames, values, dates, ticker, investment, years)
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

    # Hold + summary
    for i in range(hold_frames):
        frame = _render_frame(
            anim_frames - 1, anim_frames, values, dates,
            ticker, investment, years,
            hold=True,
            show_summary=(i >= FPS),  # show summary after 1s of hold
        )
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

    writer.release()
    print(f"  Saved: {out_path}")

    return {
        "ticker":     ticker,
        "investment": investment,
        "years":      years,
        "end_value":  end_val,
        "gain_pct":   gain_pct,
        "video_path": out_path,
    }


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    result = create_video(t, investment=10_000, years=10)
    print(result)
