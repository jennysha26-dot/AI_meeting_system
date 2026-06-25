# Component Spec: 使用者個人行程重疊確認

## 1. 功能概述

在「會議排程申請」介面中，使用者送出預約前，系統需檢查目前登入者是否已參與同日、同時段的其他會議。若發生重疊，系統不直接建立預約，而是顯示提示並要求使用者二次確認。

此功能只處理「人的行程重疊提醒」，不改變會議室時間軸、不改變會議室可預約判斷，也不把其他會議室的會議顯示到目前會議室時間軸上。

## 2. 檢查規則

- 檢查對象為目前登入者：`st.session_state.uid`。
- 不使用 `actor_uid` 作為個人撞期檢查對象。
- 只檢查使用者是否在既有會議的 `people` 名單內。
- 只檢查同一天：`booking["date"] == date`。
- 時間重疊條件：

```python
selected_start < existing_end and selected_end > existing_start
```

- 不套用會議室前後 30 分鐘緩衝，因為這不是會議室占用檢查。
- `user_hit()` 回傳第一筆重疊會議的完整 booking dict；若沒有重疊則回傳 `None`。

```python
def user_hit(uid, d, s, e):
    a, b = dtime(d, s), dtime(d, e)
    return next((x for x in db()["bookings"] if uid in x.get("people", []) and x["date"] == d and a < dtime(d, x["end"]) and b > dtime(d, x["start"])), None)
```

## 3. 送出預約流程

「送出預約申請」按鈕需放在左右兩欄的左欄，寬度與單顆「確認繼續預約」按鈕一致。

```python
submit_col, _ = st.columns(2)
with submit_col:
    submit_booking = st.button("送出預約申請", type="primary", use_container_width=True)
```

使用者點擊「送出預約申請」時，流程如下：

1. 清除舊的成功/取消提示狀態。
2. 檢查是否有有效的開始與結束時間。
3. 執行 `valid(date, start, end)` 基本預約規則。
4. 執行 `hit(room, date, start, end)` 會議室占用與緩衝期檢查。
5. 檢查發起人是否在與會名單內。
6. 建立待送出的 booking dict。
7. 執行 `user_hit(st.session_state.uid, date, start, end)`。
8. 若沒有個人行程重疊，直接儲存、寄信並顯示成功訊息。
9. 若有個人行程重疊，暫存 booking 與 conflict 到 session state，等待使用者二次確認。

## 4. 個人行程重疊提示

若偵測到重疊會議，顯示警示提示：

```text
提醒：您在 {date} {start}-{end} 已有「{title}」會議，地點為 {room}。目前選擇的時段會與該會議重疊，是否仍要繼續預約？
```

提示下方顯示兩顆按鈕：

- `確認繼續預約`：primary button，半寬。
- `取消此次預約`：一般 button，半寬。

兩顆按鈕使用：

```python
c_confirm, c_cancel = st.columns(2)
```

## 5. 確認繼續預約

使用者點擊「確認繼續預約」後：

1. 將 `pending_booking` 寫入 `data["bookings"]`。
2. 執行 `save(data)`。
3. 執行 `mail_booking(pending)`。
4. 清除 `pending_booking` 與 `pending_booking_conflict`。
5. 設定 `st.session_state.booking_success_notice = pending["id"]`。
6. 執行 `st.rerun()`。

重新渲染後：

- 原本的警示提示消失。
- `確認繼續預約` 與 `取消此次預約` 按鈕消失。
- 顯示綠色成功訊息：

```text
預約成功：BK...
```

## 6. 取消此次預約

使用者點擊「取消此次預約」後：

1. 清除 `pending_booking` 與 `pending_booking_conflict`。
2. 設定 `st.session_state.booking_cancelled_notice = True`。
3. 執行 `st.rerun()`。

重新渲染後：

- 原本的警示提示消失。
- `確認繼續預約` 與 `取消此次預約` 按鈕消失。
- 顯示藍色資訊訊息：

```text
已取消此次預約。
```

## 7. 狀態顯示優先順序

提示區塊的顯示優先順序如下：

1. 若存在 `booking_success_notice`，顯示綠色成功訊息。
2. 否則若存在 `booking_cancelled_notice`，顯示藍色取消訊息。
3. 否則若存在 `pending_booking` 與 `pending_booking_conflict`，顯示重疊警示與二次確認按鈕。

再次點擊「送出預約申請」時，需先清除舊的：

```python
st.session_state.pop("booking_cancelled_notice", None)
st.session_state.pop("booking_success_notice", None)
```

## 8. 不影響範圍

- 不影響 `time_grid()` 的時間軸繪製。
- 不影響會議室 `hit()` 的 30 分鐘緩衝規則。
- 不影響其他會議室是否顯示在目前時間軸。
- 不影響「行程變更與異動管理」中的時間軸邏輯。

## 9. 變更紀錄

- 2026/06/25：
  - 將個人行程重疊檢查正式納入會議排程申請流程。
  - 新增二段式確認：確認繼續預約 / 取消此次預約。
  - 確認繼續預約後以 `st.rerun()` 切換為單一綠色成功訊息。
  - 取消此次預約後以 `st.rerun()` 切換為單一藍色取消訊息。
  - 將「送出預約申請」按鈕調整為左半寬，與單顆確認按鈕一致。
