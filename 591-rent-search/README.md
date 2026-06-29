# 591 租屋網搜尋工具

透過 591 內部 JSON API (`bff-house.591.com.tw/v3/web/rent/list`) 搜尋租屋物件,
在終端機以表格呈現。此 API 不需要登入或 CSRF token,但仍使用 `curl_cffi`
偽裝 Chrome TLS 指紋以降低被擋的機率。

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
| `--section` | `section` | 鄉鎮/區代碼(數字) |
| `--kind` | `kind` | 房屋類型: 整層住家、獨立套房、分租套房、雅房(或代碼) |
| `--price-min` / `--price-max` | `price_min` / `price_max` | 租金範圍(元) |
| `--room` | `room` | 格局(房數): 1、2、3、4(代表 4 房以上) |
| `--area-min` / `--area-max` | `area_min` / `area_max` | 坪數範圍 |
| `--floor` | `floor` | 樓層區間: `1樓`、`2-6樓`、`6-12樓`、`12樓以上`(或原始代碼) |
| `--toilet` | `toilet` | 衛浴數量代碼 |
| `--shape` | `shape` | 型態: 公寓、電梯大樓、透天厝、別墅(或代碼) |
| `--features` | `features` | 特色,591 原始代碼,逗號分隔 |
| `--equipment` | `equipment` | 設備,591 原始代碼,逗號分隔 |
| `--fitment` | `fitment` | 裝潢程度,591 原始代碼 |
| `--included-fees` | `included_fees` | 租金含項目,591 原始代碼,逗號分隔 |
| `--notice` | `notice` | 須知,591 原始代碼,逗號分隔 |
| `--max-rows` | `max_rows` | 最多抓取筆數,預設 60 筆(每頁 30 筆,自動翻頁) |

### 支援的縣市代碼

台北市=1、基隆市=2、新北市=3、新竹市=4、新竹縣=5、桃園市=6、苗栗縣=7、
台中市=8、彰化縣=10、南投縣=11、嘉義市=12、嘉義縣=13、雲林縣=14、
台南市=15、高雄市=17、屏東縣=19、宜蘭縣=21、台東縣=22

(花蓮縣、澎湖縣、金門縣、連江縣代碼未確認,可直接嘗試代入數字代碼)

### 房屋類型 / 型態代碼

- `kind`(類型): 整層住家=1、獨立套房=2、分租套房=3、雅房=4
- `shape`(型態): 公寓=1(已實測確認)、電梯大樓=2、透天厝=3、別墅=4(後三者依畫面勾選順序推測,未逐一實測,如不準請改用「取得原始代碼」的方式自行確認)

### 特色 / 設備 / 裝潢 / 租金含 / 須知 — 不透明代碼

591 這幾類篩選的代碼是前端內部字串,沒有公開文件,目前已知:

- `features`(特色): 新上架 = `newPost`
- `equipment`(設備): 有冷氣 = `cold`
- `notice`(須知): 男女皆可 = `all_sex`、限男生 = `boy`(限女生推測為 `girl`,未實測確認)
- `fitment`(裝潢)、`included_fees`(租金含): 目前無已知代碼

#### 如何取得原始代碼

1. 用 Chrome 開啟 591 租屋搜尋頁,按 F12 打開開發者工具,切到 Network 分頁,勾選「保留紀錄檔」
2. 在畫面上勾選你想知道代碼的那個篩選項目(一次勾一個,方便比對)
3. 按搜尋,在請求清單找到 `rent/list` 的請求,複製 Request URL
4. 比對網址上新增的參數(例如 `other=xxx`、`option=xxx`、`fitment=xxx`、`priceadd=xxx`、`multiNotice=xxx`),那就是該選項的代碼
5. 把代碼填入 CLI 參數或 `search.json` 即可重複使用
