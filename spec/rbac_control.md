# Component Spec: 預約變更、取消與角色權限控管 (RBAC & Booking Control)

## 1. 功能概述 (Overview)
- 提供會議發起人（管理員）檢視、修改與取消自己所建立之會議（`org == st.session_state.uid`）的管理面板。
- 透過 `st.expander` 動態載入個別會議的變更表單，並結合時間軸元件進行變更時段的衝突偵測。

## 2. 商業邏輯與防呆控管 (Control Rules)
本模組負責執行系統最嚴格的狀態機防呆控管，確保數據有效性：
- **發起人權限隔離**：使用者僅能看見並管理自己發起的會議（透過 `x["org"] == st.session_state.uid` 過濾）。
- **1 小時前變更/取消限制**：無論變更或取消，會議的原本開始時間（`b["start"]`）距離當前時間必須大於 1 小時，否則無情阻擋（操作失敗）。
- **新時段衝突偵測**：變更會議時，新選定的時間必須通過 `valid(nd, ns, ne)` 的基本格式驗證，且不能與該會議室其他預約的前後 30 分鐘緩衝期衝突（透過 `hit()` 偵測）。

## 3. 資料庫更新與通知聯動 (Workflow)
- **取消會議**：從 `data["bookings"]` 移除該筆資料、同步寫入資料庫（`save`）、觸發 `mail_booking(mode="cancel")` 發送取消信，最後執行 `st.rerun()` 重新整理畫面。
- **變更會議**：在更新前先使用 `.copy()` 完整保留 `old_b` 資料，更新 `b` 欄位並儲存後，將新舊資料傳入 `mail_booking(b, old_b=old_b, mode="update")`，自動判斷並發送對應的更動通知信。

## 4. 當前完美的實作程式碼 (Current Stable Code)
```python
    st.subheader("我的可管理預約")
data=db()
for b in [x for x in data["bookings"] if x["org"]==st.session_state.uid]:
    with st.expander(f"{b['id']}｜{b['title']}｜{b['date']} {b['start']}-{b['end']} ({b['room']})"):
        nr=st.selectbox("新會議室",["A會議室","B會議室","C會議室"],["A會議室","B會議室","C會議室"].index(b["room"]),key="r"+b["id"])
        nd=str(st.date_input("新日期",dtime(b["date"],b["start"]).date(),key="d"+b["id"]))
        ns,ne=time_grid(nr,nd,def_s=b["start"],def_e=b["end"])
        st.caption(f"新時段：{ns or '--:--'} ~ {ne or '--:--'}")
        if st.button("變更會議",key="u"+b["id"]):
            if not ns or not ne: st.error("變更失敗：新選擇的時段或會議室無法預約。")
            elif (dtime(b["date"],b["start"])-dt.datetime.now()).total_seconds()<3600: st.error("操作失敗：會議變更必須在會議開始 1 小時前進行。")
            else:
                err=valid(nd,ns,ne) or ("變更失敗：新時段與既有預約或前後 30 分鐘緩衝期衝突。" if hit(nr,nd,ns,ne,b["id"]) else "")
                if err: st.error(err)
                else:
                    old_b=b.copy()
                    b.update({"room":nr,"date":nd,"start":ns,"end":ne})
                    save(data); mail_booking(b,old_b=old_b,mode="update"); st.success("已變更"); st.rerun()
        if st.button("取消會議",key="c"+b["id"]):
            if (dtime(b["date"],b["start"])-dt.datetime.now()).total_seconds()<3600: st.error("操作失敗：會議取消必須在會議開始 1 小時前進行。")
            else: data["bookings"]=[x for x in data["bookings"] if x["id"]!=b["id"]]; save(data); mail_booking(b,mode="cancel"); st.success("已取消"); st.rerun()
```

## 5. 變更紀錄 (Change Log)
- **2026/06/21**：
  - 定稿管理面板規格，完整歸檔「1小時前控管」與「新舊資料對比外發通知」之防呆商務邏輯。