#!/usr/bin/env python3
"""104 人力銀行職缺搜尋 CLI 工具。

透過 104 內部 JSON API 取得職缺資料,並在終端機以表格呈現。
www.104.com.tw 受 Cloudflare 機器人防護,因此使用 curl_cffi 偽裝
Chrome 的 TLS/JA3 指紋以通過挑戰。
"""

import argparse
import os
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


def main():
    parser = argparse.ArgumentParser(
        description="搜尋 104 人力銀行職缺",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "範例:\n"
            "  python search104.py python\n"
            "  python search104.py 後端工程師 --area 台北市,新北市\n"
            "  python search104.py --jobcat 軟體工程師,後端工程師,全端工程師 --area 台北市,新北市 --xlsx jobs.xlsx\n"
            "  python search104.py Java --jobcat 後端工程師,全端工程師 --area 台北市 --group"
        ),
    )
    parser.add_argument("keyword", nargs="?", default="", help="搜尋關鍵字 (可省略,改用 --jobcat 篩選)")
    parser.add_argument("--area", default="", help="地區,逗號分隔城市名或代碼 (例: 台北市,新北市)")
    parser.add_argument(
        "--jobcat",
        default="",
        help="職務類別,逗號分隔名稱或代碼 (例: 軟體工程師,後端工程師,全端工程師)",
    )
    parser.add_argument(
        "--exclude-industry",
        default="",
        dest="exclude_industry",
        help="排除業種,逗號分隔關鍵字 (例: 人力派遣,銀行);用「包含」比對",
    )
    parser.add_argument(
        "--exclude-company",
        default="",
        dest="exclude_company",
        help="排除公司,逗號分隔關鍵字 (例: 鴻海,人力銀行);用「包含」比對公司名",
    )
    parser.add_argument(
        "--exclude-title",
        default="",
        dest="exclude_title",
        help="排除職稱,逗號分隔關鍵字 (例: 實習,儲備,工讀);用「包含」比對職缺名稱",
    )
    parser.add_argument("--group", action="store_true", help="依公司分組顯示,並附公司職缺數排行")
    parser.add_argument("--xlsx", metavar="檔名", help="匯出結果到 xlsx 檔 (例: --xlsx java.xlsx)")
    args = parser.parse_args()

    if not args.keyword and not args.jobcat:
        sys.exit("請至少提供關鍵字或 --jobcat 職務類別其一。")

    area_code = resolve_areas(args.area)
    jobcat_code = resolve_jobcats(args.jobcat)

    jobs, total_count = search(args.keyword, area_code, jobcat_code)

    if not jobs:
        print("查無職缺,試試其他關鍵字或地區。")
        return

    before_dedupe = len(jobs)
    jobs = dedupe_jobs(jobs)
    if len(jobs) < before_dedupe:
        print(f"已去除 {before_dedupe - len(jobs)} 筆重複職缺 (同一網址),剩 {len(jobs)} 筆。")

    if args.exclude_industry:
        excludes = [s.strip() for s in args.exclude_industry.split(",") if s.strip()]
        before = len(jobs)
        jobs = [
            j for j in jobs
            if not any(ex in (j.get("coIndustryDesc") or "") for ex in excludes)
        ]
        print(f"已排除業種 {'、'.join(excludes)}:濾掉 {before - len(jobs)} 筆,剩 {len(jobs)} 筆。")
        if not jobs:
            print("排除後已無職缺。")
            return

    if args.exclude_company:
        excludes = [s.strip() for s in args.exclude_company.split(",") if s.strip()]
        before = len(jobs)
        jobs = [
            j for j in jobs
            if not any(ex in (j.get("custName") or "") for ex in excludes)
        ]
        print(f"已排除公司 {'、'.join(excludes)}:濾掉 {before - len(jobs)} 筆,剩 {len(jobs)} 筆。")
        if not jobs:
            print("排除後已無職缺。")
            return

    if args.exclude_title:
        excludes = [s.strip() for s in args.exclude_title.split(",") if s.strip()]
        before = len(jobs)
        jobs = [
            j for j in jobs
            if not any(ex in (j.get("jobName") or "") for ex in excludes)
        ]
        print(f"已排除職稱 {'、'.join(excludes)}:濾掉 {before - len(jobs)} 筆,剩 {len(jobs)} 筆。")
        if not jobs:
            print("排除後已無職缺。")
            return

    if args.xlsx:
        write_xlsx(jobs, args.xlsx)
        if args.group:
            write_group_xlsx(jobs, group_xlsx_path(args.xlsx))
        return

    if args.group:
        print_grouped(jobs, total_count)
    else:
        print_flat(jobs, total_count)


if __name__ == "__main__":
    main()
