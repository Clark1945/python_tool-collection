#!/usr/bin/env python3
"""591 租屋網搜尋 CLI 工具。

透過 591 內部 JSON API (bff-house.591.com.tw) 取得租屋物件資料,
並在終端機以表格呈現。此 API 不需要 CSRF token 或登入 cookie,
但仍用 curl_cffi 偽裝 Chrome 的 TLS 指紋以降低被擋的機率。
"""

import argparse
import sys
import time

try:
    from curl_cffi import requests
except ImportError:
    sys.exit("缺少套件 curl_cffi,請先執行: pip install -r requirements.txt")

try:
    from tabulate import tabulate
except ImportError:
    sys.exit("缺少套件 tabulate,請先執行: pip install -r requirements.txt")


API_URL = "https://bff-house.591.com.tw/v3/web/rent/list"

HEADERS = {
    "Referer": "https://rent.591.com.tw/list",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

ITEMS_PER_PAGE = 30

# 縣市代碼(591 regionid,實測取得,跳過的數字回傳台北市代表無效代碼)
REGION_CODES = {
    "台北市": "1",
    "基隆市": "2",
    "新北市": "3",
    "新竹市": "4",
    "新竹縣": "5",
    "桃園市": "6",
    "苗栗縣": "7",
    "台中市": "8",
    "彰化縣": "10",
    "南投縣": "11",
    "嘉義市": "12",
    "嘉義縣": "13",
    "雲林縣": "14",
    "台南市": "15",
    "高雄市": "17",
    "屏東縣": "19",
    "宜蘭縣": "21",
    "台東縣": "22",
}

# 房屋類型代碼(591 kind)
KIND_CODES = {
    "整層住家": "1",
    "獨立套房": "2",
    "分租套房": "3",
    "雅房": "4",
}

DETAIL_HEADERS = ["標題", "地址", "類型", "坪數", "樓層", "租金", "更新時間", "連結"]


def resolve_code(name, table, label):
    """將使用者輸入(中文名或代碼)轉成對應的數字代碼。"""
    if not name:
        return ""
    name = name.strip()
    if name.isdigit():
        return name
    if name in table:
        return table[name]
    supported = "、".join(table.keys())
    sys.exit(f"不支援的{label}: '{name}'\n支援的選項: {supported}\n(或直接傳入數字代碼)")


def fetch_page(region_code, kind_code, price_min, price_max, first_row):
    """呼叫 591 API 取得單頁資料,回傳 (items 清單, total 筆數)。"""
    params = {
        "timestamp": str(int(time.time() * 1000)),
        "order": "posttime",
        "orderType": "desc",
        "firstRow": str(first_row),
    }
    if region_code:
        params["regionid"] = region_code
    if kind_code:
        params["kind"] = kind_code
    if price_min or price_max:
        params["price"] = f"{price_min or ''}_{price_max or ''}"

    resp = requests.get(API_URL, params=params, headers=HEADERS, impersonate="chrome", timeout=30)
    if resp.status_code != 200:
        sys.exit(f"請求失敗,HTTP 狀態碼: {resp.status_code}")

    payload = resp.json()
    if payload.get("status") != 1:
        sys.exit(f"591 API 回應異常: {payload.get('msg')}")

    data = payload.get("data", {})
    return data.get("items", []), int(data.get("total", 0))


def search(region_code, kind_code, price_min, price_max, max_rows):
    """逐頁抓取,直到達到 max_rows 或抓完全部資料為止。"""
    all_items = []
    first_row = 0
    total = None
    while len(all_items) < max_rows:
        print(f"正在抓取第 {first_row // ITEMS_PER_PAGE + 1} 頁...", file=sys.stderr)
        items, total = fetch_page(region_code, kind_code, price_min, price_max, first_row)
        if not items:
            break
        all_items.extend(items)
        first_row += ITEMS_PER_PAGE
        if first_row >= total:
            break
        if len(all_items) < max_rows:
            time.sleep(1)
    if total is not None:
        print(f"符合條件共 {total} 筆,本次抓取 {min(len(all_items), max_rows)} 筆。", file=sys.stderr)
    return all_items[:max_rows]


def build_rows(items):
    rows = []
    for item in items:
        rows.append(
            [
                item.get("title", ""),
                item.get("address", ""),
                item.get("kind_name", ""),
                item.get("area_name", ""),
                item.get("floor_name", ""),
                f"{item.get('price', '')} {item.get('price_unit', '')}".strip(),
                item.get("refresh_time", ""),
                item.get("url", ""),
            ]
        )
    return rows


def print_flat(items):
    rows = build_rows(items)
    print(tabulate(rows, headers=DETAIL_HEADERS, tablefmt="grid"))
    print(f"共 {len(items)} 筆。")


def main():
    parser = argparse.ArgumentParser(description="591 租屋網搜尋 CLI 工具")
    parser.add_argument("--region", default="", help="縣市名稱或代碼,例如 台北市 或 1")
    parser.add_argument("--kind", default="", help="房屋類型: 整層住家、獨立套房、分租套房、雅房 (或代碼)")
    parser.add_argument("--price-min", default="", help="最低租金")
    parser.add_argument("--price-max", default="", help="最高租金")
    parser.add_argument("--max-rows", type=int, default=60, help="最多抓取筆數,預設 60 筆")
    args = parser.parse_args()

    region_code = resolve_code(args.region, REGION_CODES, "縣市")
    kind_code = resolve_code(args.kind, KIND_CODES, "房屋類型")

    items = search(region_code, kind_code, args.price_min, args.price_max, args.max_rows)

    if not items:
        print("沒有找到符合條件的物件。")
        return

    print_flat(items)


if __name__ == "__main__":
    main()
