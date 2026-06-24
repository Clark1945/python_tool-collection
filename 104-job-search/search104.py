#!/usr/bin/env python3
"""104 人力銀行職缺搜尋 CLI 工具。

透過 104 內部 JSON API 取得職缺資料,並在終端機以表格呈現。
www.104.com.tw 受 Cloudflare 機器人防護,因此使用 curl_cffi 偽裝
Chrome 的 TLS/JA3 指紋以通過挑戰。
"""

import argparse
import os
import re
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


API_URL = "https://www.104.com.tw/jobs/search/api/jobs"

HEADERS = {
    "Referer": "https://www.104.com.tw/jobs/search/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

# 常用縣市地區代碼(104 area code)
AREA_CODES = {
    "台北市": "6001001000",
    "新北市": "6001002000",
    "基隆市": "6001003000",
    "宜蘭縣": "6001004000",
    "桃園市": "6001005000",
    "新竹市": "6001006000",
    "新竹縣": "6001007000",
    "台中市": "6001008000",
    "苗栗縣": "6001009000",
    "彰化縣": "6001010000",
    "台南市": "6001011000",
    "南投縣": "6001012000",
    "雲林縣": "6001013000",
    "嘉義市": "6001014000",
    "嘉義縣": "6001015000",
    "高雄市": "6001016000",
    "屏東縣": "6001017000",
    "花蓮縣": "6001018000",
    "台東縣": "6001019000",
    "澎湖縣": "6001020000",
    "金門縣": "6001021000",
    "連江縣": "6001022000",
}

# 排序方式固定為「符合度」(104 的 order=15)
DEFAULT_ORDER = "15"

# 常用職務類別代碼 (104 jobcat,資訊軟體系統類)
JOBCAT_CODES = {
    "軟體工程師": "2007001004",
    "後端工程師": "2007001016",
    "全端工程師": "2007001017",
    "前端工程師": "2007001015",
    "iOS工程師": "2007001013",
    "Android工程師": "2007001014",
    "韌體工程師": "2007001005",
    "遊戲工程師": "2007001008",
    "資料工程師": "2007001022",
    "資料科學家": "2007001021",
    "資料分析師": "2007001018",
    "AI工程師": "2007001020",
    "機器學習工程師": "2007001026",
    "演算法工程師": "2007001012",
    "DevOps工程師": "2007001025",
    "區塊鏈工程師": "2007001023",
    "系統分析師": "2007001007",
    "通訊軟體工程師": "2007001003",
    "軟體助理工程師": "2007001019",
}


def resolve_areas(area_arg):
    """將使用者輸入的地區(城市名或代碼,逗號分隔)轉成 104 area 代碼字串。"""
    if not area_arg:
        return ""
    codes = []
    for raw in area_arg.split(","):
        name = raw.strip()
        if not name:
            continue
        if name.isdigit():
            codes.append(name)
        elif name in AREA_CODES:
            codes.append(AREA_CODES[name])
        else:
            supported = "、".join(AREA_CODES.keys())
            sys.exit(f"不支援的地區: '{name}'\n支援的城市: {supported}\n(或直接傳入數字地區代碼)")
    return ",".join(codes)


def resolve_jobcats(jobcat_arg):
    """將使用者輸入的職務類別(名稱或代碼,逗號分隔)轉成 104 jobcat 代碼字串。"""
    if not jobcat_arg:
        return ""
    codes = []
    for raw in jobcat_arg.split(","):
        name = raw.strip()
        if not name:
            continue
        if name.isdigit():
            codes.append(name)
        elif name in JOBCAT_CODES:
            codes.append(JOBCAT_CODES[name])
        else:
            supported = "、".join(JOBCAT_CODES.keys())
            sys.exit(f"不支援的職務類別: '{name}'\n支援的類別: {supported}\n(或直接傳入數字職類代碼)")
    return ",".join(codes)


def fetch_page(keyword, area_code, jobcat_code, page):
    """呼叫 104 API 取得單頁資料,回傳 (jobs 清單, pagination metadata)。"""
    params = {
        "ro": "0",
        "order": DEFAULT_ORDER,
        "page": str(page),
        "mode": "s",
        "jobsource": "2018indexpoc",
    }
    if keyword:
        params["keyword"] = keyword
    if area_code:
        params["area"] = area_code
    if jobcat_code:
        params["jobcat"] = jobcat_code

    try:
        resp = requests.get(
            API_URL,
            params=params,
            headers=HEADERS,
            impersonate="chrome",
            timeout=30,
        )
    except Exception as e:
        sys.exit(f"網路請求失敗: {e}")

    if resp.status_code == 403:
        sys.exit(
            "被 Cloudflare 擋下 (HTTP 403)。curl_cffi 的 TLS 指紋偽裝未通過。\n"
            "可嘗試: 升級 curl_cffi、更換 impersonate 版本 (如 chrome120),"
            "或改用真實瀏覽器 (Playwright) 後備方案。"
        )
    if resp.status_code != 200:
        sys.exit(f"API 回傳非預期狀態碼: {resp.status_code}")

    try:
        payload = resp.json()
    except Exception:
        snippet = resp.text[:120].replace("\n", " ")
        sys.exit(
            "回應不是 JSON(可能被 Cloudflare 擋下並回傳 HTML 挑戰頁)。\n"
            f"內容開頭: {snippet}"
        )

    jobs = payload.get("data", []) or []
    pagination = payload.get("metadata", {}).get("pagination", {})
    return jobs, pagination


def search(keyword, area_code, jobcat_code):
    """逐頁抓取所有職缺,回傳 (jobs 清單, 總筆數)。

    一律抓到 lastPage (104 API 上限為第 100 頁,約 3000 筆)。
    """
    all_jobs = []
    total_count = 0
    page = 1
    while True:
        jobs, pagination = fetch_page(keyword, area_code, jobcat_code, page)
        total_count = pagination.get("total", total_count)
        if not jobs:
            break
        all_jobs.extend(jobs)
        last_page = pagination.get("lastPage", page)
        print(f"  抓取中... 第 {page}/{last_page} 頁 ({len(all_jobs)}/{total_count})", file=sys.stderr)
        if page >= last_page:
            break
        page += 1
        time.sleep(1)  # 避免觸發風控
    return all_jobs, total_count


def format_salary(job):
    """由 salaryLow / salaryHigh 組出薪資字串 (9999999 代表「以上」)。"""
    low = job.get("salaryLow")
    high = job.get("salaryHigh")
    if not low and not high:
        return "面議"
    if high == 9999999:
        return f"{low:,} 以上"
    if low == high:
        return f"{low:,}"
    return f"{low:,}~{high:,}"


def format_period(job):
    """由 period (年資數字) 組出經歷字串 (0 代表不拘)。"""
    period = job.get("period", 0)
    if not period:
        return "不拘"
    return f"{period}年以上"


def format_employee(job):
    """由 employeeCount 組出員工人數字串 (0/空 代表未提供),供終端機顯示用。"""
    count = job.get("employeeCount")
    if not count:
        return "未提供"
    return f"{count:,} 人"


def employee_count(job):
    """員工人數的數值版 (未提供回 0),供 xlsx 排序用。"""
    return job.get("employeeCount") or 0


def format_link(job):
    """取得職缺連結 (API 已回傳完整 URL)。"""
    link = job.get("link", {}).get("job", "")
    if link.startswith("//"):
        return "https:" + link
    return link


def build_rows(jobs):
    rows = []
    for job in jobs:
        rows.append([
            job.get("jobName", ""),
            job.get("custName", ""),
            format_employee(job),
            job.get("jobAddrNoDesc", ""),
            format_salary(job),
            format_period(job),
            job.get("appearDate", ""),
            format_link(job),
        ])
    return rows


# 明細欄位 (xlsx 各分頁共用,順序固定)
DETAIL_HEADERS = ["公司", "業種", "員工人數", "職稱", "地區", "薪資", "薪資低", "薪資高", "經歷", "更新日期", "連結"]


def job_detail_row(job):
    """組出一筆職缺的明細列 (順序對應 DETAIL_HEADERS)。"""
    return [
        job.get("custName", ""),
        job.get("coIndustryDesc", ""),
        employee_count(job),
        job.get("jobName", ""),
        job.get("jobAddrNoDesc", ""),
        format_salary(job),
        job.get("salaryLow", ""),
        job.get("salaryHigh", ""),
        format_period(job),
        job.get("appearDate", ""),
        format_link(job),
    ]


def new_workbook():
    """建立一個 openpyxl Workbook (套件缺失時給出安裝提示)。"""
    try:
        from openpyxl import Workbook
    except ImportError:
        sys.exit("缺少套件 openpyxl,請先執行: pip install -r requirements.txt")
    return Workbook()


def save_workbook(wb, path):
    """儲存 Workbook,並把常見的「檔案開在 Excel 中」錯誤轉成易懂訊息。"""
    try:
        wb.save(path)
    except OSError as e:
        sys.exit(f"寫入 Excel 失敗 (檔案是否開在 Excel 中?): {e}")


def write_xlsx(jobs, path):
    """將職缺寫入 xlsx。

    含數值薪資欄位 (薪資低/薪資高) 方便做樞紐分析。
    """
    wb = new_workbook()
    ws = wb.active
    ws.title = "職缺明細"
    ws.append(DETAIL_HEADERS)
    for job in jobs:
        ws.append(job_detail_row(job))
    save_workbook(wb, path)
    print(f"已匯出 {len(jobs)} 筆職缺到 {path}")


def print_flat(jobs, total_count):
    """以單一表格輸出所有職缺。"""
    rows = build_rows(jobs)
    headers = ["職稱", "公司", "員工人數", "地區", "薪資", "經歷", "更新", "連結"]
    print(tabulate(rows, headers=headers, tablefmt="grid"))
    print(f"\n共 {total_count} 筆,顯示 {len(jobs)} 筆。")


def group_by_company(jobs):
    """依公司分組,回傳 [(公司, [職缺...]), ...],依職缺數由多到少排序。"""
    groups = {}
    for job in jobs:
        groups.setdefault(job.get("custName", "(未知公司)"), []).append(job)
    # 依職缺數由多到少,同數量時依公司名排序
    return sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def group_xlsx_path(path):
    """由主 xlsx 路徑推導分組摘要 xlsx 路徑 (output.xlsx → output_companies.xlsx)。"""
    root, ext = os.path.splitext(path)
    return f"{root}_companies{ext or '.xlsx'}"


def write_group_xlsx(jobs, path):
    """將「公司職缺數排行」寫入 xlsx。"""
    ordered = group_by_company(jobs)
    wb = new_workbook()
    ws = wb.active
    ws.title = "公司職缺數排行"
    ws.append(["公司", "職缺數", "員工人數"])
    for company, comp_jobs in ordered:
        ws.append([company, len(comp_jobs), employee_count(comp_jobs[0])])
    save_workbook(wb, path)
    print(f"已匯出 {len(ordered)} 家公司的職缺數排行到 {path}")


def print_grouped(jobs, total_count):
    """依公司分組輸出,公司依職缺數由多到少排序。"""
    ordered = group_by_company(jobs)

    headers = ["職稱", "地區", "薪資", "經歷", "更新", "連結"]

    for company, comp_jobs in ordered:
        print(f"\n■ {company} ({len(comp_jobs)} 筆,員工 {format_employee(comp_jobs[0])})")
        rows = []
        for job in comp_jobs:
            rows.append([
                job.get("jobName", ""),
                job.get("jobAddrNoDesc", ""),
                format_salary(job),
                format_period(job),
                job.get("appearDate", ""),
                format_link(job),
            ])
        print(tabulate(rows, headers=headers, tablefmt="grid"))

    print(f"\n共 {total_count} 筆,顯示 {len(jobs)} 筆,分屬 {len(ordered)} 家公司。")
    print("\n公司職缺數排行:")
    summary = [[c, len(j), format_employee(j[0])] for c, j in ordered]
    print(tabulate(summary, headers=["公司", "職缺數", "員工人數"], tablefmt="grid"))


def dedupe_jobs(jobs):
    """以職缺網址去重,保留第一次出現的順序。

    104 會因置頂(促銷)或同一職缺符合多個職類,在結果裡回傳重複的職缺;
    去重後表格/分組/xlsx 的筆數才一致。
    無網址的職缺無法判斷重複,一律保留。
    """
    seen = set()
    unique = []
    for job in jobs:
        url = format_link(job)
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        unique.append(job)
    return unique


def split_terms(value):
    """把設定值正規化成乾淨的關鍵字 list。

    接受逗號分隔字串 (CLI 用) 或字串清單 (JSON 設定檔用),兩者皆可。
    """
    if not value:
        return []
    if isinstance(value, str):
        value = value.split(",")
    return [str(s).strip() for s in value if str(s).strip()]


def as_comma(value):
    """把設定值 (字串或清單) 轉成逗號分隔字串,供 resolve_* 使用。"""
    if value is None:
        return ""
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    return str(value)


def field_title(job):
    return job.get("jobName") or ""


def field_company(job):
    return job.get("custName") or ""


def field_industry(job):
    return job.get("coIndustryDesc") or ""


def field_keyword(job):
    """整則職缺的可搜尋文字 (職稱 + 描述 + 公司 + 業種)。

    供「包含/排除關鍵字」做廣域比對,與只比對職稱的 title 過濾區隔開來。
    """
    return " ".join([
        job.get("jobName") or "",
        job.get("description") or "",
        job.get("custName") or "",
        job.get("coIndustryDesc") or "",
    ])


def apply_filter(jobs, terms, accessor, mode, label):
    """套用一組「包含/排除」過濾並回傳剩餘職缺。

    mode='include' → 只保留含任一 term 者;mode='exclude' → 濾掉含任一 term 者。
    用「包含」(substring) 比對,大小寫敏感。terms 為空時原樣回傳。
    """
    if not terms:
        return jobs
    before = len(jobs)
    if mode == "include":
        kept = [j for j in jobs if any(t in accessor(j) for t in terms)]
        verb = "只保留"
    else:
        kept = [j for j in jobs if not any(t in accessor(j) for t in terms)]
        verb = "排除"
    print(f"已{verb} {label} {'、'.join(terms)}:{before} → {len(kept)} 筆。")
    return kept


def job_id_from_url(url):
    """從 104 職缺網址抽出職缺 ID (網址內 /job/<id> 的部分)。

    抽不出時回傳去頭尾空白的原字串,讓使用者也能直接貼 ID。
    用 ID 比對可同時吃完整網址 (含 ?jobsource=... 等查詢字串) 與裸 ID。
    """
    m = re.search(r"/job/([A-Za-z0-9]+)", url or "")
    return m.group(1) if m else (url or "").strip()


def load_url_lines(path):
    """從文字檔讀取要排除的職缺網址,一行一個;空行與 # 開頭(註解)略過。"""
    try:
        # utf-8-sig 可同時吃帶/不帶 BOM 的檔
        with open(path, encoding="utf-8-sig") as f:
            lines = f.readlines()
    except FileNotFoundError:
        sys.exit(f"找不到排除網址清單檔: {path}")
    urls = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        urls.append(s)
    return urls


def filter_exclude_urls(jobs, exclude_urls):
    """濾掉網址(職缺 ID)落在排除清單內的職缺。exclude_urls 為空時原樣回傳。"""
    if not exclude_urls:
        return jobs
    ids = {job_id_from_url(u) for u in exclude_urls}
    before = len(jobs)
    kept = [j for j in jobs if job_id_from_url(format_link(j)) not in ids]
    print(f"已排除指定網址職缺:{before} → {len(kept)} 筆 (清單 {len(ids)} 筆)。")
    return kept


def load_config(path):
    """讀取 JSON 設定檔,回傳 dict。最外層須為 JSON 物件 {...}。"""
    import json
    try:
        # utf-8-sig 可同時吃帶/不帶 BOM 的檔 (Windows 記事本常存成帶 BOM)
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
        description="搜尋 104 人力銀行職缺",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例:\n"
            "  python search104.py python\n"
            "  python search104.py 後端工程師 --area 台北市,新北市\n"
            "  python search104.py --jobcat 軟體工程師,後端工程師,全端工程師 --area 台北市,新北市 --xlsx jobs.xlsx\n"
            "  python search104.py Java --jobcat 後端工程師,全端工程師 --area 台北市 --group\n"
            "  python search104.py --config search.json   # 從 JSON 設定檔讀取所有條件\n"
            "\n"
            "註: CLI 參數會覆蓋設定檔中的同名欄位。"
        ),
    )
    parser.add_argument("keyword", nargs="?", default=None, help="搜尋關鍵字 (可省略,改用 --jobcat 篩選)")
    parser.add_argument("--config", metavar="檔名", help="從 JSON 設定檔讀取條件 (例: --config search.json)")
    parser.add_argument("--area", default=None, help="地區,逗號分隔城市名或代碼 (例: 台北市,新北市)")
    parser.add_argument(
        "--jobcat",
        default=None,
        help="職務類別,逗號分隔名稱或代碼 (例: 軟體工程師,後端工程師,全端工程師)",
    )
    # 包含/排除過濾 (皆用「包含」substring 比對,大小寫敏感,逗號分隔)
    parser.add_argument(
        "--include-keyword", default=None, dest="include_keyword",
        help="只保留整則職缺文字 (職稱+描述+公司+業種) 含任一關鍵字者",
    )
    parser.add_argument(
        "--exclude-keyword", default=None, dest="exclude_keyword",
        help="排除整則職缺文字含任一關鍵字者",
    )
    parser.add_argument(
        "--include-industry", default=None, dest="include_industry",
        help="只保留業種含任一關鍵字者 (例: 電腦軟體,資訊服務)",
    )
    parser.add_argument(
        "--exclude-industry", default=None, dest="exclude_industry",
        help="排除業種含任一關鍵字者 (例: 人力派遣,銀行)",
    )
    parser.add_argument(
        "--include-company", default=None, dest="include_company",
        help="只保留公司名含任一關鍵字者",
    )
    parser.add_argument(
        "--exclude-company", default=None, dest="exclude_company",
        help="排除公司名含任一關鍵字者 (例: 鴻海,人力銀行)",
    )
    parser.add_argument(
        "--include-title", default=None, dest="include_title",
        help="只保留職稱含任一關鍵字者 (例: 後端,Backend)",
    )
    parser.add_argument(
        "--exclude-title", default=None, dest="exclude_title",
        help="排除職稱含任一關鍵字者 (例: 實習,儲備,工讀)",
    )
    parser.add_argument(
        "--exclude-url", default=None, dest="exclude_url",
        help="排除指定職缺網址 (或職缺ID),逗號分隔;例: https://www.104.com.tw/job/8yto7",
    )
    parser.add_argument(
        "--exclude-url-file", default=None, dest="exclude_url_file",
        help="從文字檔讀取要排除的職缺網址,一行一個 (# 開頭為註解)",
    )
    parser.add_argument("--group", action="store_true", help="依公司分組顯示,並附公司職缺數排行")
    parser.add_argument("--xlsx", metavar="檔名", help="匯出結果到 xlsx 檔 (例: --xlsx java.xlsx)")
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else {}

    def pick(cli_val, key):
        """CLI 值優先,未提供 (None) 時退回設定檔的同名欄位。"""
        return cli_val if cli_val is not None else cfg.get(key)

    keyword = (pick(args.keyword, "keyword") or "").strip()
    area = pick(args.area, "area")
    jobcat = pick(args.jobcat, "jobcat")
    group = args.group or bool(cfg.get("group"))
    xlsx = pick(args.xlsx, "xlsx")

    # 排除網址清單: 合併 CLI/設定檔的直接清單與檔案來源
    exclude_urls = split_terms(pick(args.exclude_url, "exclude_url"))
    url_file = pick(args.exclude_url_file, "exclude_url_file")
    if url_file:
        exclude_urls += load_url_lines(url_file)

    # 八組過濾條件: (terms, 欄位存取器, 模式, 中文標籤),依序套用
    filter_specs = [
        (split_terms(pick(args.include_keyword, "include_keyword")), field_keyword, "include", "關鍵字"),
        (split_terms(pick(args.exclude_keyword, "exclude_keyword")), field_keyword, "exclude", "關鍵字"),
        (split_terms(pick(args.include_industry, "include_industry")), field_industry, "include", "業種"),
        (split_terms(pick(args.exclude_industry, "exclude_industry")), field_industry, "exclude", "業種"),
        (split_terms(pick(args.include_company, "include_company")), field_company, "include", "公司"),
        (split_terms(pick(args.exclude_company, "exclude_company")), field_company, "exclude", "公司"),
        (split_terms(pick(args.include_title, "include_title")), field_title, "include", "職稱"),
        (split_terms(pick(args.exclude_title, "exclude_title")), field_title, "exclude", "職稱"),
    ]

    if not keyword and not jobcat:
        sys.exit("請至少提供關鍵字或 --jobcat 職務類別其一 (可寫在設定檔或 CLI)。")

    area_code = resolve_areas(as_comma(area))
    jobcat_code = resolve_jobcats(as_comma(jobcat))

    jobs, total_count = search(keyword, area_code, jobcat_code)

    if not jobs:
        print("查無職缺,試試其他關鍵字或地區。")
        return

    before_dedupe = len(jobs)
    jobs = dedupe_jobs(jobs)
    if len(jobs) < before_dedupe:
        print(f"已去除 {before_dedupe - len(jobs)} 筆重複職缺 (同一網址),剩 {len(jobs)} 筆。")

    jobs = filter_exclude_urls(jobs, exclude_urls)
    if not jobs:
        print("篩選後已無職缺。")
        return

    for terms, accessor, mode, label in filter_specs:
        jobs = apply_filter(jobs, terms, accessor, mode, label)
        if not jobs:
            print("篩選後已無職缺。")
            return

    if xlsx:
        write_xlsx(jobs, xlsx)
        if group:
            write_group_xlsx(jobs, group_xlsx_path(xlsx))
        return

    if group:
        print_grouped(jobs, total_count)
    else:
        print_flat(jobs, total_count)


if __name__ == "__main__":
    main()
