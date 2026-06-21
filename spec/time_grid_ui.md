# Component Spec: 會議室預訂狀態時間軸 (Time Grid UI)

## 1. 功能概述 (Overview)
- 在 Streamlit 預約介面上渲染當日 09:00 至 21:00 的會議室預訂狀態時間軸。
- 提供開始時間與結束時間的並排下拉選單（`st.selectbox`），並根據當前時間與既有預約自動過濾可用時段。

## 2. 商業邏輯與限制 (Business Rules)
- **1小時前限制**：使用者無法預約當前時間加 1 小時內（含過去）的時段。
- **30分鐘緩衝期**：每個成功預約（Booking）的前後各自動加上 30 分鐘的清理與準備時間，這段時間同樣列入「不可預訂」範圍。
- **結束時間過濾**：當使用者選定「開始時間」後，結束時間選單必須至少大於開始時間 30 分鐘，且一旦中間遇到任何不可預訂時段，後續時段皆不予顯示。

## 3. UI 畫面樣式與顏色規範 (UI Specs)
時間軸由 72 格（每格 10 分鐘）的水平區塊緊密組成，顏色必須嚴格對齊以下圖例：
- 🟩 **已選擇 (Green)**：當前下拉選單中，自「開始時間」至「結束時間」所涵蓋的區間。
  - CSS 樣式：`background-color: #4ade80;`
- ⬜ **可預訂 (White)**：目前尚未被佔用、且符合 1 小時前限制的開放預約時段。
  - CSS 樣式：`background-color: #ffffff;`
- ▒ **不可預訂 (Gray with stripes)**：已被他人預約之時段、既有預約前後的 30 分鐘緩衝期，以及已過去的歷史時間。
  - CSS 樣式：`background-color: #e2e8f0; background-image: linear-gradient(45deg, #cbd5e1 25%, transparent 25%, transparent 50%, #cbd5e1 50%, #cbd5e1 75%, transparent 75%, transparent); background-size: 8px 8px;`

## 4. 當前完美的實作程式碼 (Current Stable Code)
```python
def time_grid(room, d, def_s=None, def_e=None):
    times = ts()
    bookings = [x for x in db()["bookings"] if x["room"] == room and x["date"] == d and not (def_s and x["start"] == def_s and x["end"] == def_e)]
    limit_t = dt.datetime.now() + dt.timedelta(hours=1)
    
    def is_slot_busy(s):
        t = dtime(d, s)
        if t <= limit_t: return True
        return any(dtime(d, b["start"]) - dt.timedelta(minutes=30) <= t < dtime(d, b["end"]) + dt.timedelta(minutes=30) for b in bookings)

    valid_starts = [s for s in times[:-1] if dtime(d, s) > limit_t]
    if not valid_starts:
        st.error("當日已無可預約時段"); return ("", "")

    c_s, c_e = st.columns(2)
    with c_s:
        start = st.selectbox("開始時間", valid_starts, index=valid_starts.index(def_s) if def_s in valid_starts else 0, key=f"sel_s_{room}_{d}_{def_s}")
    
    with c_e:
        valid_ends = []
        start_idx = times.index(start)
        for e in times[start_idx+3:]:
            if any(is_slot_busy(times[step]) for step in range(start_idx, times.index(e))): break
            valid_ends.append(e)
        end = st.selectbox("結束時間", valid_ends if valid_ends else ["該時段無法預約"], disabled=not valid_ends, key=f"sel_e_{room}_{d}_{def_s}")
        if not valid_ends: end = "該時段無法預約"

    st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:15px; margin-bottom:5px;'>會議室當日預訂狀態時間軸</p>", unsafe_allow_html=True)
    st.markdown("""
        <style>
        div[data-testid='stHorizontalBlock'] > div { min-width: 0px !important; padding: 0px !important; }
        .timeline-container { display: flex; width: 100%; border: 1px solid #cbd5e1; height: 35px; border-radius: 6px; overflow: hidden; background-color: #ffffff; margin-bottom: 25px; }
        .timeline-label-item { position: absolute; transform: translateX(-50%); font-size: 11px; font-weight: 600; color: #475569; white-space: nowrap; top: 39px; }
        </style>
    """, unsafe_allow_html=True)

    active_labels = { "09:00": 0.0, "21:00": 100.0 }
    t_base = dt.datetime.strptime(f"{d} 09:00", "%Y-%m-%d %H:%M")
    get_pos = lambda ts_str: ((dt.datetime.strptime(f"{d} {ts_str}", "%Y-%m-%d %H:%M") - t_base).total_seconds() / 43200) * 100    
    
    if end != "該時段無法預約" and start and end:
        active_labels[start], active_labels[end] = get_pos(start), get_pos(end)

    for b in bookings:
        bs_dt, be_dt = dtime(d, b["start"]) - dt.timedelta(minutes=30), dtime(d, b["end"]) + dt.timedelta(minutes=30)
        bs = bs_dt.strftime("%H:%M") if bs_dt >= t_base else "09:00"
        be = be_dt.strftime("%H:%M") if be_dt <= dtime(d, "21:00") else "21:00"
        active_labels[bs], active_labels[be] = get_pos(bs), get_pos(be)

    if t_base <= limit_t <= dtime(d, "21:00"):
        lim_str = limit_t.strftime("%H:%M")[:-1] + "0"
        active_labels[lim_str] = get_pos(lim_str)

    bar_html = "<div style='position: relative; width: 100%;'><div class='timeline-container'>"
    for s in times[:-1]:
        is_selected = (end != "該時段無法預約" and start and end and dtime(d, start) <= dtime(d, s) < dtime(d, end))
        bg_style = "background-color: #4ade80;" if is_selected else ("background-color: #e2e8f0; background-image: linear-gradient(45deg, #cbd5e1 25%, transparent 25%, transparent 50%, #cbd5e1 50%, #cbd5e1 75%, transparent 75%, transparent); background-size: 8px 8px;" if is_slot_busy(s) else "background-color: #ffffff;")
        bar_html += f"<div style='width: calc(100% / 72); flex-shrink: 0; {bg_style}' title='{s}'></div>"
    bar_html += "</div>"

    filtered_labels = []
    for s, pos in sorted(active_labels.items(), key=lambda x: x[1]):
        if any(abs(pos - fp) < 3.5 for _, fp in filtered_labels) and s not in ["09:00", "21:00", start, end]: continue
        filtered_labels.append((s, pos))
        bar_html += f"<div class='timeline-label-item' style='left: {pos}%;'>{s}</div>"
    bar_html += "</div></div><br>"

    st.markdown(bar_html, unsafe_allow_html=True)
    st.markdown("""
        <div style='display: flex; gap: 20px; font-size: 12px; margin-top: 5px; justify-content: center;'>
            <div style='display: flex; align-items: center; gap: 6px;'><div style='width: 14px; height: 14px; background: #4ade80; border-radius: 3px;'></div>已選擇</div>
            <div style='display: flex; align-items: center; gap: 6px;'><div style='width: 14px; height: 14px; background: #cbd5e1; border-radius: 3px; background-image: linear-gradient(45deg, #94a3b8 25%, transparent 25%, transparent 50%, #94a3b8 50%, #94a3b8 75%, transparent 75%, transparent); background-size: 4px 4px;'></div>不可預訂</div>
            <div style='display: flex; align-items: center; gap: 6px;'><div style='width: 14px; height: 14px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 3px;'></div>可預訂</div>
        </div><br>
    """, unsafe_allow_html=True)  
    return (start, end) if end != "該時段無法預約" else (start, "")
```

## 5. 變更紀錄 (Change Log)
- **2026/06/21**：
  - 修正了因為程式碼精簡化導致可預訂區間大面積發灰、圖層疊加錯置的問題。
  - 將時間軸改回穩定度最高的單格 `div` 彈性佈局，並將每格寬度固定設為 `calc(100% / 72)`。
  - 成功修復 ▒ 不可預訂灰色斜線條紋在特定日期（如 6/24、6/25）會產生左右偏移的 Bug，確保條紋邊界與下方時間軸標籤精確對齊。