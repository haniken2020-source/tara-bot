"""Daily flight price monitor — chạy bởi GitHub Actions lúc 9AM Vietnam."""

import httpx
import os
from datetime import date, timedelta

chat_id = os.environ["TELEGRAM_CHAT_ID"]
token   = os.environ["TELEGRAM_TOKEN"]
serpapi = os.environ["SERPAPI_KEY"]

today = date.today()

# Chuyến 1: 26/1/2027 → 16/2/2027
outbound_1 = date(2027, 1, 26)
return_1   = date(2027, 2, 16)

# Chuyến 2: 31/1/2027 → 16/2/2027
outbound_2 = date(2027, 1, 31)
return_2   = date(2027, 2, 16)

ROUTES = [
    ("KHH", "SGN", "Cao Hùng → Hồ Chí Minh"),
    ("KHH", "DLI", "Cao Hùng → Đà Lạt"),
]

messages = [f"🗓 Báo giá vé Tết 2027\n"]

for dep, arr, label in ROUTES:
    for outbound, ret, trip_label in [
        (outbound_1, return_1, "26/1 → 16/2"),
        (outbound_2, return_2, "31/1 → 16/2"),
    ]:
        params = {
            "engine":        "google_flights",
            "departure_id":  dep,
            "arrival_id":    arr,
            "outbound_date": outbound.isoformat(),
            "return_date":   ret.isoformat(),
            "adults":        1,
            "currency":      "VND",
            "api_key":       serpapi,
        }
        try:
            r    = httpx.get("https://serpapi.com/search.json", params=params, timeout=50)
            data = r.json()
            best = data.get("best_flights", [])
            prices = [f.get("price", 0) for f in best if f.get("price")]
            if prices:
                messages.append(f"✈️ {label} ({trip_label}): từ {min(prices):,} VND")
            else:
                messages.append(f"✈️ {label} ({trip_label}): không tìm thấy")
        except Exception as e:
            messages.append(f"⚠️ {label}: lỗi - {e}")

text = "\n".join(messages)
httpx.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
    timeout=10,
)
print(text)
