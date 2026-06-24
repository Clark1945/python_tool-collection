# 104 職缺搜尋 CLI（search104.py）

一個命令列工具,用**關鍵字、地區、職務類別**搜尋 [104 人力銀行](https://www.104.com.tw/) 職缺,可在終端機以表格呈現、依公司分組,或匯出 xlsx 供 Excel 分析。

支援**包含/排除**四種維度的後過濾(關鍵字、業種、公司、職稱),且因條件常常很長,可改用 **JSON 設定檔**一次帶入所有條件。

---

## 目錄
- [運作原理](#運作原理)
- [安裝](#安裝)
- [快速開始](#快速開始)
- [參數總覽](#參數總覽)
- [包含/排除過濾](#包含排除過濾)
- [JSON 設定檔](#json-設定檔)
- [輸出方式](#輸出方式)
- [xlsx 欄位與樞紐分析](#xlsx-欄位與樞紐分析)
- [支援地區](#支援地區)
- [支援職務類別](#支援職務類別)
- [資料欄位的呈現規則](#資料欄位的呈現規則)
- [常見問題與限制](#常見問題與限制)

---

## 運作原理

104 的搜尋頁面是透過內部 JSON API (`https://www.104.com.tw/jobs/search/api/jobs`) 取得資料,本工具直接呼叫此 API,免去解析 HTML。

由於 `www.104.com.tw` 受 **Cloudflare 機器人防護**,本工具使用 [`curl_cffi`](https://github.com/lexiforest/curl_cffi) 偽裝 Chrome 的 TLS/JA3 指紋以通過挑戰(`impersonate="chrome"`)。

處理流程:
1. (選用)讀取 JSON 設定檔當作預設條件,CLI 參數可覆蓋之
2. 將地區/職類名稱轉成 104 的數字代碼
3. 逐頁呼叫 API,**一律抓取全部頁**(每頁間隔 1 秒避免觸發風控,上限為第 100 頁約 3000 筆)
4. (選用)依關鍵字／業種／公司／職稱做**包含或排除**過濾
5. 以表格 / 分組 / xlsx 輸出(表格一律顯示完整欄位)

---

## 安裝

需要 Python 3.8+。

```bash
pip install -r requirements.txt
```

> 若系統限制全域安裝(PEP 668),建議用虛擬環境:
> ```bash
> python3 -m venv .venv
> .venv/bin/pip install -r requirements.txt
> .venv/bin/python search104.py ...   # 或先 source .venv/bin/activate
> ```

依賴套件:`curl_cffi`(過 Cloudflare)、`tabulate`(終端機表格)、`openpyxl`(xlsx 匯出)。

---

## 快速開始

```bash
# 1. 用關鍵字搜尋(一次抓全部頁)
python search104.py python

# 2. 指定地區
python search104.py 後端工程師 --area 台北市,新北市

# 3. 用職務類別篩選(可不帶關鍵字),並匯出 xlsx
python search104.py --jobcat 軟體工程師,後端工程師,全端工程師 --area 台北市,新北市 --xlsx swe.xlsx

# 4. 關鍵字 + 職類 + 排除業種,依公司分組並輸出雙 xlsx
python search104.py Java --jobcat 軟體工程師,後端工程師,全端工程師 \
  --area 台北市,新北市 --exclude-industry 人力派遣,銀行,保險 --group --xlsx output.xlsx

# 5. 同時排除特定公司與職稱(用「包含」比對),精準過濾雜訊
python search104.py Java --jobcat 後端工程師,全端工程師 --area 台北市,新北市 \
  --exclude-company 派遣,顧問,證券 --exclude-title 實習,儲備,工讀,Intern --group

# 6. 用「包含」過濾鎖定想要的:職稱含「後端/Backend」、整篇有提到「Spring」
python search104.py Java --area 台北市 \
  --include-title 後端,Backend --include-keyword Spring,微服務

# 7. 條件太長?寫進 JSON 設定檔,一行帶入
python search104.py --config search.json
```

---

## 參數總覽

| 參數 | 預設 | 說明 |
|------|------|------|
| `keyword`(位置參數) | 無 | 送給 104 的**搜尋關鍵字**(API 端搜尋)。**可省略,但需至少提供關鍵字或 `--jobcat` 其一**。含空格時請用引號,例:`"Python 後端"`。 |
| `--config 檔名` | 無 | 從 **JSON 設定檔**讀取所有條件;CLI 參數會**覆蓋**設定檔同名欄位。見[JSON 設定檔](#json-設定檔)。 |
| `--area` | 不限 | 地區,逗號分隔**城市名或數字代碼**,例:`台北市,新北市`。見[支援地區](#支援地區)。 |
| `--jobcat` | 不限 | 職務類別,逗號分隔**名稱或數字代碼**,例:`軟體工程師,後端工程師`。見[支援職務類別](#支援職務類別)。 |
| `--include-keyword` | 不過濾 | **只保留**整則職缺文字(職稱+描述+公司+業種)含任一關鍵字者。廣域比對,適合鎖定技術棧,例:`Spring,微服務`。 |
| `--exclude-keyword` | 不過濾 | **排除**整則職缺文字含任一關鍵字者。 |
| `--include-industry` | 不過濾 | **只保留**業種(`coIndustryDesc`)含任一關鍵字者,例:`電腦軟體,資訊服務`。 |
| `--exclude-industry` | 不過濾 | **排除**業種含任一關鍵字者,例:`人力派遣,銀行`:`人力派遣` 會濾掉「人力派遣服務業」。 |
| `--include-company` | 不過濾 | **只保留**公司名(`custName`)含任一關鍵字者。 |
| `--exclude-company` | 不過濾 | **排除**公司名含任一關鍵字者,例:`鴻海,證券`:`證券` 會濾掉所有公司名含「證券」者。 |
| `--include-title` | 不過濾 | **只保留**職稱(`jobName`)含任一關鍵字者,例:`後端,Backend`。 |
| `--exclude-title` | 不過濾 | **排除**職稱含任一關鍵字者,例:`實習,儲備,工讀`。 |
| `--exclude-url` | 不過濾 | **排除指定職缺**,逗號分隔網址或職缺 ID,例:`https://www.104.com.tw/job/8yto7`。見[排除指定職缺](#用網址排除指定職缺)。 |
| `--exclude-url-file` | 不過濾 | 從**文字檔**讀取要排除的職缺網址(一行一個),適合累積「已看過/已投遞」清單。 |
| `--group` | 關閉 | 依公司分組顯示,並附「公司職缺數排行」表;與 `--xlsx` 併用時另存一份排行 xlsx。 |
| `--xlsx 檔名` | 關閉 | 匯出 xlsx(可直接用 Excel 開啟,中文不亂碼)。**指定後不在終端機印表格。** |

> 行為固定為:**一次抓取全部頁**、排序依「符合度」、終端機表格**一律顯示完整欄位**(職稱、公司、員工人數、地區、薪資、經歷、更新日期、連結)。
>
> 所有 `--include-*` / `--exclude-*` 過濾都在**抓取後、輸出前**套用,對表格/分組/xlsx 全部生效。詳見下節。

---

## 包含/排除過濾

抓取完資料後,可用四種維度做**後過濾**,每種都有「包含(include)」與「排除(exclude)」兩個方向:

| 維度 | 比對欄位 | `--include-*`(只保留) | `--exclude-*`(濾掉) |
|------|----------|------------------------|----------------------|
| **關鍵字** | 職稱 + 描述 + 公司 + 業種(整篇文字) | `--include-keyword` | `--exclude-keyword` |
| **業種** | `coIndustryDesc` | `--include-industry` | `--exclude-industry` |
| **公司** | `custName` | `--include-company` | `--exclude-company` |
| **職稱** | `jobName` | `--include-title` | `--exclude-title` |

規則:

- **逗號分隔多個關鍵字**,以「**包含**」(substring) 比對,**大小寫敏感**(所以 `iOS` 與 `IOS` 需各自列出)。
- **任一命中即算符合**:`--exclude-title 實習,工讀` 會濾掉職稱含「實習」**或**「工讀」者;`--include-title 後端,Backend` 會保留職稱含「後端」**或**「Backend」者。
- **`keyword` 維度 vs `title` 維度**:`title` 只看職稱;`keyword` 看整則職缺文字(含職缺描述、公司、業種),適合用技術棧字詞(如 `Spring`、`Kubernetes`)做廣域篩選。
- **套用順序**:關鍵字 → 業種 → 公司 → 職稱,每個維度先 include 再 exclude;任一步驟濾到 0 筆即停止並提示。
- 每套用一個過濾會在輸出印出 `已排除/只保留 〈維度〉 …:N → M 筆。`,方便看出每步濾掉多少。

> 注意 `keyword`(位置參數)是送給 104 的**伺服器端搜尋**,而 `--include-keyword` 是抓回來後的**本地過濾**,兩者不同。

### 用網址排除指定職缺

看過、投過或單純不感興趣的職缺,可以用網址精準剔除。兩種來源(會合併):

```bash
# 直接在命令列指定 (逗號分隔)
python search104.py Java --area 台北市 \
  --exclude-url https://www.104.com.tw/job/8yto7,https://www.104.com.tw/job/abcd1

# 或維護一份清單檔 (推薦,可長期累積)
python search104.py Java --area 台北市 --exclude-url-file seen.txt
```

清單檔格式:**一行一個網址**,空行與 `#` 開頭的註解會略過:

```text
# 已投遞
https://www.104.com.tw/job/8yto7
# 不感興趣
abcd1
```

比對規則:程式會把網址**正規化成 104 職缺 ID**(`/job/` 後面那段)再比對,所以:

- 直接從瀏覽器複製、**帶 `?jobsource=...` 等查詢字串的完整網址**也能對上;
- 只貼**裸職缺 ID**(如 `8yto7`)同樣有效。

> 此排除在所有包含/排除過濾**之前**套用。每次會印出 `已排除指定網址職缺:N → M 筆 (清單 K 筆)。`

---

## JSON 設定檔

條件很長時(例如要排除幾十家外包/派遣公司),把它們全寫在命令列很難維護。改用 `--config 檔名` 從 JSON 讀取:

```bash
python search104.py --config search.json
```

設定檔的鍵名對應 CLI 參數(底線命名),值可為**字串**或**字串陣列**:

```json
{
  "keyword": "Java",
  "area": ["台北市", "新北市"],
  "jobcat": ["軟體工程師", "後端工程師", "全端工程師"],

  "include_keyword": [],
  "exclude_keyword": [],
  "include_industry": [],
  "exclude_industry": ["人力派遣", "銀行", "保險"],
  "include_company": [],
  "exclude_company": ["派遣", "顧問", "證券"],
  "include_title": [],
  "exclude_title": ["實習", "儲備", "工讀", "Intern"],

  "exclude_url": ["https://www.104.com.tw/job/8yto7"],
  "exclude_url_file": "seen.txt",

  "group": true,
  "xlsx": "output.xlsx"
}
```

| 設定檔鍵名 | 型別 | 對應 CLI |
|------------|------|----------|
| `keyword` | 字串 | 位置參數 |
| `area` / `jobcat` | 字串或陣列 | `--area` / `--jobcat` |
| `include_keyword` / `exclude_keyword` | 字串或陣列 | `--include-keyword` / `--exclude-keyword` |
| `include_industry` / `exclude_industry` | 字串或陣列 | `--include-industry` / `--exclude-industry` |
| `include_company` / `exclude_company` | 字串或陣列 | `--include-company` / `--exclude-company` |
| `include_title` / `exclude_title` | 字串或陣列 | `--include-title` / `--exclude-title` |
| `exclude_url` | 字串或陣列 | `--exclude-url` |
| `exclude_url_file` | 字串(檔案路徑) | `--exclude-url-file` |
| `group` | 布林 | `--group` |
| `xlsx` | 字串 | `--xlsx` |

> `exclude_url`(設定檔/CLI)與 `exclude_url_file` 的內容會**合併**使用,不是互斥。

合併規則:

- **CLI 覆蓋設定檔**:若同一欄位 CLI 與設定檔都給了,以 CLI 為準。例:`--config search.json Go` 會用 `Go` 取代設定檔的 `keyword`。
- **`--group`**:CLI 或設定檔任一為真即啟用(CLI 無法關掉設定檔的 `true`)。
- 設定檔可只放部分欄位,其餘留給 CLI 或預設值。
- 設定檔需為 UTF-8(可帶 BOM);最外層須為 JSON 物件 `{...}`,否則報錯。

> 專案附了一份 [`search.example.json`](search.example.json) 可直接複製修改。指定 `--xlsx` 時只寫檔、不印終端機表格。`--group` 為例外 — 它可與 `--xlsx` 併用,額外輸出一份排行 xlsx(見下方)。

### 1. 一般表格(預設)
終端機印出單一表格,欄位:職稱、公司、員工人數、地區、薪資、經歷、更新、連結,最後一行顯示「共 X 筆,顯示 Y 筆」。

### 2. 分組顯示(`--group`)
每家公司一個區塊(依職缺數由多到少),區塊標題列出公司名、職缺數與員工人數;區塊內列出該公司職缺;最後附**公司職缺數排行表**(含員工人數)與「共 X 筆…分屬 N 家公司」統計。

### 3. xlsx 匯出(`--xlsx 檔名`)
- 只寫檔、不印表格。
- 單獨使用 → 產出一個職缺明細 xlsx。
- **與 `--group` 併用 → 額外產出一份「公司職缺數排行」xlsx**,檔名由主檔名自動推導:

  | 檔案 | 內容 |
  |------|------|
  | `output.xlsx` | 職缺明細(一筆一列) |
  | `output_companies.xlsx` | 公司職缺數排行(公司、職缺數、員工人數) |

> 抓取進度會印在 **stderr**(`第 N/M 頁 …`),不影響輸出內容;導向檔案時可用 `2>/dev/null` 隱藏。

---

## xlsx 欄位與樞紐分析

明細 xlsx 欄位(順序固定):

| 欄位 | 來源 | 說明 |
|------|------|------|
| 公司 | `custName` | 公司名稱 |
| 業種 | `coIndustryDesc` | 行業別,如「電腦軟體服務業」 |
| 員工人數 | `employeeCount` | **數值**(方便 Excel 排序),如 `9000`;API 未提供時為 `0`。(終端機表格仍顯示「9,000 人 / 未提供」) |
| 職稱 | `jobName` | |
| 地區 | `jobAddrNoDesc` | 如「台北市內湖區」 |
| 薪資 | 由薪資低/高組成 | 文字版,如 `60,000 以上`、`面議` |
| 薪資低 | `salaryLow` | **數值**(`0` = 面議) |
| 薪資高 | `salaryHigh` | **數值**(`9999999` = 以上) |
| 經歷 | `period` | 如「3年以上」「不拘」 |
| 更新日期 | `appearDate` | 格式 `YYYYMMDD` |
| 連結 | `link.job` | 104 職缺網址 |

**樞紐分析建議**:在 Excel/Google Sheet 插入樞紐分析表 → 列放「公司」或「業種」、值放「職稱(計數)」即可看徵才數排行;把「薪資低」放進值並取平均,可比較各公司開出的薪資。

---

## 支援地區

`--area` 可用以下城市名(逗號分隔),或直接傳 104 數字代碼(例:`6001001000` = 台北市):

> 台北市、新北市、基隆市、宜蘭縣、桃園市、新竹市、新竹縣、台中市、苗栗縣、彰化縣、台南市、南投縣、雲林縣、嘉義市、嘉義縣、高雄市、屏東縣、花蓮縣、台東縣、澎湖縣、金門縣、連江縣

輸入不在清單內的名稱會報錯並列出支援清單。

---

## 支援職務類別

`--jobcat` 可用以下名稱(逗號分隔),或直接傳 104 數字代碼(例:`2007001016` = 後端工程師):

> 軟體工程師、後端工程師、全端工程師、前端工程師、iOS工程師、Android工程師、韌體工程師、遊戲工程師、資料工程師、資料科學家、資料分析師、AI工程師、機器學習工程師、演算法工程師、DevOps工程師、區塊鏈工程師、系統分析師、通訊軟體工程師、軟體助理工程師

(皆屬 104「資訊軟體系統類 > 軟體／工程類人員」。)

---

## 資料欄位的呈現規則

- **薪資**:`salaryHigh == 9999999` → 顯示「{低} 以上」;低=高 → 單一數字;低與高皆為 0/空 → 「面議」;否則顯示「{低}~{高}」。
- **經歷**:`period == 0` → 「不拘」;否則「{period}年以上」。
- **連結**:API 已回傳完整 URL;若為 `//` 開頭會補上 `https:`。

---

## 常見問題與限制

- **抓不到資料、回 HTTP 403 或非 JSON**:104 可能啟用需執行 JavaScript 的完整 Turnstile 挑戰,`curl_cffi` 的指紋偽裝不足以通過。可嘗試升級 `curl_cffi`、更換 `impersonate` 版本(如 `chrome120`),或改用真實瀏覽器(Playwright)後備方案。
- **最多約 3000 筆**:104 API 分頁上限為第 100 頁,本工具一律抓到上限。結果超過此數時請用 `--area` / `--jobcat` / 關鍵字縮小範圍。
- **重複職缺自動去除**:104 會因置頂(促銷)或同一職缺符合多個職類而回傳重複項,本工具在抓取後**以網址去重**(保留第一次出現),所以表格/分組/xlsx 筆數一致。有去除時會印出「已去除 N 筆重複職缺」。
- **顯示筆數可能與回報總數略有出入**:去重後筆數通常略少於 API 回報的 `total`;另因 104 採「符合度」排序且每次請求重新計算,而本工具分多頁(多次請求)抓取,**同一條件每次抓到的結果集會小幅變動(約 1~2%)**,屬正常現象。
- **空關鍵字會被 104 拒絕(400)**:程式已處理 — 只在有值時才送出 `keyword`,所以可單用 `--jobcat` 搜尋。
- **員工人數**已可直接取得(來自職缺回應的 `employeeCount` 欄位),顯示於表格、分組與 xlsx。**資本額等其他公司詳細資訊**仍不在職缺搜尋回應裡,需另呼叫公司 API,目前未實作。

---

## 實際使用範例

搜尋 Java 後端/全端職缺、限台北新北、排除派遣與金融業種、過濾掉一長串外包/派遣/顧問公司與實習類職稱,最後依公司分組並輸出雙 xlsx。

### 推薦:用 JSON 設定檔(條件太長時最好維護)

把所有條件寫進 `search.json`(可參考專案附的 [`search.example.json`](search.example.json)),然後:

```bash
python search104.py --config search.json
```

需要臨時調整某個欄位時,直接在後面加 CLI 參數覆蓋即可,例如改抓 Python:

```bash
python search104.py Python --config search.json
```

### 等效的 CLI 寫法

以下是同條件、不用設定檔的完整指令(已加上行尾 `\` 反斜線,可直接複製到終端機執行)。

### For Windows
```bash
python search104.py Java --jobcat 軟體工程師,後端工程師,全端工程師 --area 台北市,新北市 --exclude-industry 人力派遣,銀行,保險,汽車及其零件製造業,  --exclude-title 嵌入式,CAD,.Net,C#,韌體,ERP,ASP.NET,iOS,PHP,Android,IOS,BPM,Embedded,助理,替代役,無經驗,新鮮人,Intern,駐點,測試,Test,實習生,業務,顧問,Consultant,派駐 --exclude-company 華苓,聯成電腦,加坡商易呈,英屬維,鴻揚,大學,醫院,國泰,保險,顧問,博彥,威普羅,塔塔,印福思,人力,人事,安復仕,普鴻,祐安,碩誠,神通,德義,明瑞資通,緯德,艾力特,精誠,資拓,凌群,叡揚,台灣大哥,藝珂,元大金融, --group --xlsx output.xlsx
```

### For Linux
```bash
python search104.py Java \
  --jobcat 軟體工程師,後端工程師,全端工程師 \
  --area 台北市,新北市 \
  --exclude-industry 人力派遣,銀行,保險 \
  --exclude-title 嵌入式,CAD,.Net,C#,韌體,ERP,ASP.NET,iOS,PHP,Android,IOS,BPM,Embedded,助理,替代役,無經驗,新鮮人,Intern,駐點,測試,Test,實習生,業務,顧問,Consultant,派駐 \
  --exclude-company 新加坡商易呈,英屬維,鴻揚,大學,醫院,國泰,保險,顧問,博彥,威普羅,塔塔,印福思,人力,人事,安復仕,普鴻,祐安,碩誠,神通,德義,明瑞資通,緯德,艾力特,精誠,資拓,凌群,叡揚,台灣大哥,藝珂,元大金融 \
  --group \
  --xlsx output.xlsx
```