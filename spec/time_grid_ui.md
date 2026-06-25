# Component Spec: 會議室預訂狀態時間軸

## 1. 功能概述

`time_grid()` 負責在 Streamlit 預約與行程變更介面中顯示指定會議室、指定日期的可預約狀態。

元件包含：

- 開始時間下拉選單。
- 結束時間下拉選單。
- 09:00 至 21:00 的水平時間軸。
- 已選擇 / 不可預訂 / 可預訂圖例。

時間軸不顯示標題。

## 2. 時間粒度

- 營業時間固定為 09:00 至 21:00。
- 時間選項以 10 分鐘為單位。
- 時間軸共 72 格，每格代表 10 分鐘。
- `ts()` 必須回傳：

```python
[f"{h:02d}:{m:02d}" for h in range(9, 21) for m in range(0, 60, 10)] + ["21:00"]
```

## 3. 可預約規則

- 使用者必須在會議開始 1 小時前預約。
- `limit_t = dt.datetime.now() + dt.timedelta(hours=1)`。
- `dtime(d, s) <= limit_t` 的格子視為不可預訂。
- 既有預約的前 30 分鐘與後 30 分鐘皆視為不可預訂。
- 結束時間至少必須晚於開始時間 30 分鐘，因此從 `times[start_idx+3:]` 開始列出。
- 結束時間選項遇到第一個不可預訂格後即停止，後續時間不再顯示。

## 4. 函式介面

```python
def time_grid(room, d, def_s=None, def_e=None, exclude_booking_id="", widget_key=""):
```

參數說明：

- `room`：會議室名稱。
- `d`：日期字串，格式為 `YYYY-MM-DD`。
- `def_s`：預設開始時間，主要用於行程變更介面。
- `def_e`：預設結束時間，主要用於行程變更介面。
- `exclude_booking_id`：排除指定 booking，讓行程變更時原會議本身不阻擋自己的時段。
- `widget_key`：自訂 Streamlit widget key 前綴，避免行程變更介面多筆會議的 selectbox key 衝突。

## 5. 下拉選單規格

開始與結束時間需使用左右兩欄：

```python
c_s, c_e = st.columns(2)
```

開始時間：

- 選項來自 `valid_starts`。
- 若 `def_s` 存在且仍在 `valid_starts` 中，預設選中 `def_s`。
- 有 `widget_key` 時，key 格式為：

```python
f"{widget_key}_start_{room}_{d}"
```

結束時間：

- 選項來自 `valid_ends`。
- 若 `def_e` 存在且仍在 `valid_ends` 中，預設選中 `def_e`。
- 沒有可用結束時間時，顯示 `該時段無法預約` 並禁用 selectbox。
- 有 `widget_key` 時，key 格式為：

```python
f"{widget_key}_end_{room}_{d}"
```

## 6. 時間軸顏色

每格時間軸必須依照下列優先順序決定顏色：

1. 已選擇區間：綠色。
2. 不可預訂區間：灰色斜線。
3. 可預訂區間：白色。

樣式：

```css
/* 已選擇 */
background-color: #4ade80;

/* 可預訂 */
background-color: #ffffff;

/* 不可預訂 */
background-color: #e2e8f0;
background-image: linear-gradient(45deg, #cbd5e1 25%, transparent 25%, transparent 50%, #cbd5e1 50%, #cbd5e1 75%, transparent 75%, transparent);
background-size: 8px 8px;
```

時間軸容器：

```css
.timeline-container {
    display: flex;
    width: 100%;
    border: 1px solid #cbd5e1;
    height: 35px;
    border-radius: 6px;
    overflow: hidden;
    background-color: #ffffff;
    margin-bottom: 25px;
}
```

每格寬度固定：

```python
width: calc(100% / 72);
```

## 7. 下方時間標籤規則

必須顯示：

- `09:00`
- `21:00`
- 目前已選擇區間的開始時間與結束時間。
- 不可預訂區間的起始與結束時間。

不可預訂區間需先合併後再顯示邊界：

1. 先建立目前時間限制區間：`09:00` 至 `limit_boundary`。
2. `limit_boundary` 需將 `limit_t` 無條件進位到下一個 10 分鐘刻度，並且不超過 `21:00`。
3. 加入所有既有預約的 30 分鐘緩衝區間。
4. 將重疊或相接的不可預訂區間合併。
5. 顯示合併後每個區間的起點與終點。

範例：

- 當前時間 17:00，則 `09:00-18:00` 不可預訂，標籤只需顯示 `09:00`、`18:00`、`21:00`。
- 當前時間 14:00，若既有緩衝區間與目前時間限制合併為 `09:00-17:00`，標籤只需顯示 `09:00`、`17:00`、`21:00`。
- 當前時間 10:00，若另有既有緩衝區間 `12:30-17:00`，標籤需顯示 `09:00`、`11:00`、`12:30`、`17:00`、`21:00`。

標籤不得因距離過近而被過濾掉；已選擇區間的開始與結束時間必須保留。

標籤字體大小：

```css
font-size: 12px;
```

## 8. 圖例

時間軸下方需顯示三個圖例：

- 已選擇：綠色方塊。
- 不可預訂：灰色斜線方塊。
- 可預訂：白色方塊。

圖例文字大小為 12px，置中排列。

## 9. 行程變更介面使用規則

行程變更與異動管理介面呼叫 `time_grid()` 時，必須傳入原會議資料：

```python
ns, ne = time_grid(
    nr,
    nd,
    def_s=b["start"],
    def_e=b["end"],
    exclude_booking_id=b["id"],
    widget_key=f"edit_{b['id']}",
)
```

目的：

- 讓原本會議的時段在該會議的變更介面中視為可預約。
- 讓開始/結束時間下拉選單預設為該會議原本的時間。
- 避免多筆會議同時展開時發生 widget key 衝突。

此規則只限於行程變更與異動管理，不影響一般會議排程申請介面。

## 10. 變更紀錄

- 2026/06/21：
  - 改為 72 格單格 `div` 彈性佈局。
  - 每格寬度固定為 `calc(100% / 72)`。
- 2026/06/25：
  - 時間粒度定稿為 10 分鐘。
  - 移除時間軸標題。
  - 標籤字體調整為 12px。
  - 不可預訂標籤改為先合併區間後顯示邊界。
  - 已選擇區間開始/結束標籤不得被隱藏。
  - 行程變更介面新增 `exclude_booking_id` 與 `widget_key` 使用規則。
