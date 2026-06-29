# 591 租屋網搜尋工具

透過 591 內部 JSON API (`bff-house.591.com.tw/v3/web/rent/list`) 搜尋租屋物件,
在終端機以表格呈現。此 API 不需要登入或 CSRF token,但仍使用 `curl_cffi`
偽裝 Chrome TLS 指紋以降低被擋的機率。

所有篩選條件(含特色/設備/裝潢/租金含/須知)皆已對應成中文名稱,代碼表是
直接從 591 前端 JS 原始碼挖出來的完整清單,不需要自己用瀏覽器複製網址。

## 安裝

```bash
pip install -r requirements.txt
```

## 使用方式

```bash
python search591.py --region 新竹縣 --kind 分租套房 --price-min 5000 --price-max 10000 --max-rows 30
```

也可以用 JSON 設定檔一次帶入所有條件(CLI 參數會覆蓋設定檔中的同名欄位):

```bash
python search591.py --config search.json
```

請複製 `search.example.json` 為 `search.json` 並依需求修改。

## 參數說明

| CLI 參數 | JSON 欄位 | 說明 |
|---|---|---|
| `--region` | `region` | 縣市名稱或代碼,例如 `台北市` 或 `1` |
| `--section` | `section` | 鄉鎮/區代碼(數字,從網址 `sectionid` 取得) |
| `--kind` | `kind` | 房屋類型: 整層住家、獨立套房、分租套房、雅房 |
| `--price-min` / `--price-max` | `price_min` / `price_max` | 租金範圍(元) |
| `--room` | `room` | 格局: 1房、2房、3房、4房以上 |
| `--area-min` / `--area-max` | `area_min` / `area_max` | 坪數範圍 |
| `--floor` | `floor` | 樓層: 1層、2-6層、6-12層、12層以上 |
| `--toilet` | `toilet` | 衛浴: 1衛、2衛、3衛、4衛及以上 |
| `--shape` | `shape` | 型態: 公寓、電梯大樓、透天厝、別墅、店面 |
| `--features` | `features` | 特色,中文名稱或代碼,逗號分隔(見下表) |
| `--equipment` | `equipment` | 設備,中文名稱或代碼,逗號分隔(見下表) |
| `--fitment` | `fitment` | 裝潢: 新裝潢、中檔裝潢、高檔裝潢 |
| `--included-fees` | `included_fees` | 租金含項目,中文名稱或代碼,逗號分隔(見下表) |
| `--notice` | `notice` | 須知: 男女皆可、限男生、限女生、排除頂樓加蓋 |
| `--max-rows` | `max_rows` | 最多抓取筆數,預設 60 筆(每頁 30 筆,自動翻頁) |

`region`/`section`/`room`/`floor`/`toilet`/`shape`/`fitment`/`notice`/`features`/
`equipment`/`included_fees` 皆可直接填中文名稱,程式會自動轉換成 591 內部代碼;
也可以直接填代碼。JSON 設定檔裡可多選的欄位(features/equipment/included_fees/
notice)請用陣列,例如 `["新上架", "近捷運"]`。

### 支援的縣市代碼

台北市=1、基隆市=2、新北市=3、新竹市=4、新竹縣=5、桃園市=6、苗栗縣=7、
台中市=8、彰化縣=10、南投縣=11、嘉義市=12、嘉義縣=13、雲林縣=14、
台南市=15、高雄市=17、屏東縣=19、宜蘭縣=21、台東縣=22

(花蓮縣、澎湖縣、金門縣、連江縣代碼未確認,可直接嘗試代入數字代碼)

### 特色(`--features`)

新上架、近捷運、可養寵物、可開伙、有車位、有電梯、優選好屋、屋主直租、
影片賞屋、AI影音講房、有陽台、可短期租賃、免服務費、降價物件、免押金、
押一付一、社會住宅、非社會住宅、租金補貼、高齡友善、可報稅、可入籍

### 設備(`--equipment`)

有冷氣、有洗衣機、有冰箱、有熱水器、有天然瓦斯、有網路、床、有衣櫃

### 租金含項目(`--included-fees`)

管理費、水費、電費、網路費、第四台、瓦斯費、清潔費、車位租金
