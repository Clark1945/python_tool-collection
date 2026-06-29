#!/usr/bin/env python3
"""591 租屋網搜尋 CLI 工具。

透過 591 內部 JSON API (bff-house.591.com.tw) 取得租屋物件資料,
並在終端機以表格呈現。此 API 不需要 CSRF token 或登入 cookie,
但仍用 curl_cffi 偽裝 Chrome 的 TLS 指紋以降低被擋的機率。

特色/設備/裝潢/租金含/須知這幾類篩選的代碼表是從 591 前端 JS bundle
(filter 設定物件) 直接挖出來的完整清單,所有選項皆可用中文名稱輸入。
"""

import argparse
import json
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

# 型態代碼(591 shape)
SHAPE_CODES = {
    "公寓": "1",
    "電梯大樓": "2",
    "透天厝": "3",
    "別墅": "4",
    "店面": "8",
}

# 格局(房數)代碼(591 layout,送出時對應 multiRoom)
ROOM_CODES = {
    "1房": "1",
    "2房": "2",
    "3房": "3",
    "4房以上": "4",
}

# 樓層區間代碼(591 floor,送出時對應 multiFloor)
FLOOR_CODES = {
    "1層": "1_1",
    "2-6層": "2_6",
    "6-12層": "6_12",
    "12層以上": "13_",
}

# 衛浴數量代碼(591 multiToilet)
TOILET_CODES = {
    "1衛": "1",
    "2衛": "2",
    "3衛": "3",
    "4衛及以上": "4_",
}

# 裝潢程度代碼(591 fitment,租屋版選項)
FITMENT_CODES = {
    "新裝潢": "99",
    "中檔裝潢": "3",
    "高檔裝潢": "4",
}

# 租金含項目代碼(591 priceadd)
INCLUDED_FEE_CODES = {
    "管理費": "4",
    "水費": "1",
    "電費": "2",
    "網路費": "6",
    "第四台": "5",
    "瓦斯費": "3",
    "清潔費": "7",
    "車位租金": "199",
}

# 須知代碼(591 notice,送出時對應 multiNotice)
NOTICE_CODES = {
    "男女皆可": "all_sex",
    "限男生": "boy",
    "限女生": "girl",
    "排除頂樓加蓋": "not_cover",
}

# 設備代碼(591 option)
EQUIPMENT_CODES = {
    "有冷氣": "cold",
    "有洗衣機": "washer",
    "有冰箱": "icebox",
    "有熱水器": "hotwater",
    "有天然瓦斯": "naturalgas",
    "有網路": "broadband",
    "床": "bed",
    "有衣櫃": "wardrobe",
}

# 特色代碼(591 other)
FEATURE_CODES = {
    "優選好屋": "best_house",
    "屋主直租": "host",
    "影片賞屋": "video",
    "AI影音講房": "ai_video",
    "新上架": "newPost",
    "可養寵物": "pet",
    "可開伙": "cook",
    "有車位": "cartplace",
    "近捷運": "near_subway",
    "有陽台": "balcony_1",
    "有電梯": "lift",
    "可短期租賃": "lease",
    "免服務費": "no-service-fee",
    "降價物件": "downPrice",
    "免押金": "no-deposit",
    "押一付一": "one-month-deposit",
    "社會住宅": "social-housing",
    "非社會住宅": "non-social-housing",
    "租金補貼": "rental-subsidy",
    "高齡友善": "elderly-friendly",
    "可報稅": "tax-deductible",
    "可入籍": "naturalization",
}

DETAIL_HEADERS = ["標題", "地址", "類型", "坪數", "樓層", "租金", "更新時間", "連結"]


def resolve_multi_codes(value, table, label):
    """將使用者輸入(中文名/代碼/逗號分隔多選)轉成逗號分隔的代碼字串。"""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = value
    else:
        items = [value]
    codes = []
    for raw in items:
        name = str(raw).strip()
        if not name:
            continue
        if name in table:
            codes.append(table[name])
        elif name in table.values():
            codes.append(name)
        else:
            supported = "、".join(table.keys())
            sys.exit(f"不支援的{label}: '{name}'\n支援的選項: {supported}\n(或直接傳入代碼)")
    return ",".join(codes)


def resolve_code(value, table, label):
    """將使用者輸入(中文名或代碼)轉成對應的代碼字串。"""
    if value is None or value == "":
        return ""
    value = str(value).strip()
    if value in table.values() or value.isdigit():
        return value
    if value in table:
        return table[value]
    supported = "、".join(table.keys())
    sys.exit(f"不支援的{label}: '{value}'\n支援的選項: {supported}\n(或直接傳入代碼)")


def as_comma(value):
    """把設定值 (字串或清單) 轉成逗號分隔字串。"""
    if value is None or value == "":
        return ""
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return str(value)


def build_range_param(value_min, value_max):
    """把最小/最大值組成 591 慣用的 'min_max' 區間參數 (任一端可留空)。"""
    if not value_min and not value_max:
        return ""
    return f"{value_min or ''}_{value_max or ''}"


def fetch_page(params, first_row):
    """呼叫 591 API 取得單頁資料,回傳 (items 清單, total 筆數)。"""
    query = dict(params)
    query["timestamp"] = str(int(time.time() * 1000))
    query["firstRow"] = str(first_row)

    resp = requests.get(API_URL, params=query, headers=HEADERS, impersonate="chrome", timeout=30)
    if resp.status_code != 200:
        sys.exit(f"請求失敗,HTTP 狀態碼: {resp.status_code}")

    payload = resp.json()
    if payload.get("status") != 1:
        sys.exit(
            f"591 API 回應沒有資料 (status={payload.get('status')})。\n"
            "可能是篩選條件組合過於嚴格,或某個原始代碼填錯導致條件衝突。"
        )

    data = payload.get("data", {})
    return data.get("items", []), int(data.get("total", 0))


def search(params, max_rows):
    """逐頁抓取,直到達到 max_rows 或抓完全部資料為止。"""
    all_items = []
    first_row = 0
    total = None
    while len(all_items) < max_rows:
        print(f"正在抓取第 {first_row // ITEMS_PER_PAGE + 1} 頁...", file=sys.stderr)
        items, total = fetch_page(params, first_row)
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


def load_config(path):
    """讀取 JSON 設定檔,回傳 dict。最外層須為 JSON 物件 {...}。"""
    try:
        with open(path, encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        sys.exit(f"找不到設定檔: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"設定檔 JSON 格式錯誤 ({path}): {e}")
    if not isinstance(cfg, dict):
        sys.exit("設定檔最外層必須是 JSON 物件 {...}")
    return cfg


def main():
    parser = argparse.ArgumentParser(
        description="搜尋 591 租屋網物件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例:\n"
            "  python search591.py --region 新竹縣 --kind 分租套房 --price-min 5000 --price-max 10000\n"
            "  python search591.py --config search.json   # 從 JSON 設定檔讀取所有條件\n"
            "\n"
            "註: CLI 參數會覆蓋設定檔中的同名欄位。\n"
            "特色/設備/裝潢/租金含/須知這幾類沒有公開代碼文件,請用瀏覽器 F12\n"
            "Network 面板複製實際請求網址取得代碼,詳見 README.md。"
        ),
    )
    parser.add_argument("--config", metavar="檔名", help="從 JSON 設定檔讀取條件 (例: --config search.json)")
    parser.add_argument("--region", default=None, help="縣市名稱或代碼,例如 台北市 或 1")
    parser.add_argument("--section", default=None, help="鄉鎮/區代碼 (數字,例: 54),從網址 sectionid 取得")
    parser.add_argument("--kind", default=None, help="房屋類型: 整層住家、獨立套房、分租套房、雅房 (或代碼)")
    parser.add_argument("--price-min", dest="price_min", default=None, help="最低租金")
    parser.add_argument("--price-max", dest="price_max", default=None, help="最高租金")
    parser.add_argument("--room", default=None, help="格局: 1房、2房、3房、4房以上 (或代碼)")
    parser.add_argument("--area-min", dest="area_min", default=None, help="最小坪數")
    parser.add_argument("--area-max", dest="area_max", default=None, help="最大坪數")
    parser.add_argument("--floor", default=None, help="樓層: 1層、2-6層、6-12層、12層以上 (或代碼)")
    parser.add_argument("--toilet", default=None, help="衛浴: 1衛、2衛、3衛、4衛及以上 (或代碼)")
    parser.add_argument("--shape", default=None, help="型態: 公寓、電梯大樓、透天厝、別墅、店面 (或代碼)")
    parser.add_argument(
        "--features", default=None,
        help="特色,逗號分隔的中文名稱或代碼 (例: 新上架,近捷運,可養寵物,可開伙,有車位,有電梯...)",
    )
    parser.add_argument(
        "--equipment", default=None,
        help="設備,逗號分隔的中文名稱或代碼 (例: 有冷氣,有洗衣機,有冰箱,有熱水器,有天然瓦斯,有網路)",
    )
    parser.add_argument("--fitment", default=None, help="裝潢: 新裝潢、中檔裝潢、高檔裝潢 (或代碼)")
    parser.add_argument(
        "--included-fees", dest="included_fees", default=None,
        help="租金含項目,逗號分隔的中文名稱或代碼 (例: 管理費,水費,電費,網路費,第四台,瓦斯費,清潔費,車位租金)",
    )
    parser.add_argument(
        "--notice", default=None,
        help="須知,逗號分隔的中文名稱或代碼 (例: 男女皆可,限男生,限女生,排除頂樓加蓋)",
    )
    parser.add_argument("--max-rows", dest="max_rows", type=int, default=None, help="最多抓取筆數,預設 60 筆")
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else {}

    def pick(cli_val, key):
        return cli_val if cli_val is not None else cfg.get(key)

    region_code = resolve_code(pick(args.region, "region"), REGION_CODES, "縣市")
    kind_code = resolve_code(pick(args.kind, "kind"), KIND_CODES, "房屋類型")
    shape_code = resolve_multi_codes(pick(args.shape, "shape"), SHAPE_CODES, "型態")
    floor_code = resolve_multi_codes(pick(args.floor, "floor"), FLOOR_CODES, "樓層")
    room_code = resolve_multi_codes(pick(args.room, "room"), ROOM_CODES, "格局")
    toilet_code = resolve_multi_codes(pick(args.toilet, "toilet"), TOILET_CODES, "衛浴")
    fitment_code = resolve_multi_codes(pick(args.fitment, "fitment"), FITMENT_CODES, "裝潢")
    included_fees = resolve_multi_codes(pick(args.included_fees, "included_fees"), INCLUDED_FEE_CODES, "租金含項目")
    notice = resolve_multi_codes(pick(args.notice, "notice"), NOTICE_CODES, "須知")
    equipment = resolve_multi_codes(pick(args.equipment, "equipment"), EQUIPMENT_CODES, "設備")
    features = resolve_multi_codes(pick(args.features, "features"), FEATURE_CODES, "特色")
    section_code = as_comma(pick(args.section, "section"))

    price_range = build_range_param(pick(args.price_min, "price_min"), pick(args.price_max, "price_max"))
    area_range = build_range_param(pick(args.area_min, "area_min"), pick(args.area_max, "area_max"))

    max_rows = pick(args.max_rows, "max_rows") or 60

    params = {
        "order": "posttime",
        "orderType": "desc",
    }
    if region_code:
        params["regionid"] = region_code
    if section_code:
        params["sectionid"] = section_code
    if kind_code:
        params["kind"] = kind_code
    if price_range:
        params["price"] = price_range
    if room_code:
        params["multiRoom"] = room_code
    if area_range:
        params["multiArea"] = area_range
    if floor_code:
        params["multiFloor"] = floor_code
    if toilet_code:
        params["multiToilet"] = toilet_code
    if shape_code:
        params["shape"] = shape_code
    if features:
        params["other"] = features
    if equipment:
        params["option"] = equipment
    if fitment_code:
        params["fitment"] = fitment_code
    if included_fees:
        params["priceadd"] = included_fees
    if notice:
        params["multiNotice"] = notice

    items = search(params, int(max_rows))

    if not items:
        print("沒有找到符合條件的物件。")
        return

    print_flat(items)


if __name__ == "__main__":
    main()
