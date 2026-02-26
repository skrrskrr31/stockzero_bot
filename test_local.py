"""
Lokal test: sadece video render eder, YouTube'a yüklemez.
Kullanım: python test_local.py [TICKER] [INVESTMENT] [YEARS]
Örnek:    python test_local.py NVDA 10000 10
"""
import sys
from stock_chart import create_video

ticker     = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
investment = float(sys.argv[2]) if len(sys.argv) > 2 else 10_000
years      = int(sys.argv[3])   if len(sys.argv) > 3 else 10

result = create_video(ticker, investment=investment, years=years)

print("\n=== Sonuc ===========================")
print(f"  Ticker    : {result['ticker']}")
print(f"  Baslangic : ${result['investment']:,.0f}")
print(f"  Bitis     : ${result['end_value']:,.0f}")
print(f"  Getiri    : {result['gain_pct']:+.1f}%")
print(f"  Video     : {result['video_path']}")
print("======================================")
