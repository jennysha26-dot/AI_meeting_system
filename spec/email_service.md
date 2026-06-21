# Component Spec: 信件通知與安全性驗證系統 (Email Service)

## 1. 功能概述 (Overview)
- 當會議室預約成功、變更（改時間/改地點/兩者皆改）或取消時，系統會自動比對新舊資料。
- 自動查詢與會人員清單，並依據對應的異動狀態（Mode）發送對應的通知信件至與會同仁的 G-mail 信箱。

## 2. 安全性與驗證機制 (Security & Authentication)
- **環境變數隔離與清洗**：寄件者的 G-mail 帳號與應用程式密碼統一由環境變數 `GMAIL_USER` 與 `GMAIL_APP_PASSWORD` 讀取，並加上 `.replace("\xa0", "")` 強制清洗不乾淨的隱形空白，防止驗證失敗。
- **加密傳輸**：發信時強制啟用 `s.starttls()` 進行 TLS 安全加密連線，確保驗證資訊與信件內文不外洩。

## 3. 信件狀態切換邏輯 (Notification Modes)
系統支援 5 種通知情境，並包含完整人性化的提醒文字（*如：務必於會議開始前10分鐘抵達*）：
- `create`: 會議通知（新預約成功）。
- `cancel`: 會議取消通知。
- `time`: 會議時程更動通知（日期或時間改變）。
- `room`: 會議地點更動通知（會議室改變）。
- `both`: 會議時程與地點更動通知（時間與會議室皆改變）。

## 4. 當前完美的實作程式碼 (Current Stable Code)
```python
import os
import smtplib
from email.mime.text import MIMEText
import streamlit as st

def mail(to,sub,body):
    user = os.getenv("GMAIL_USER", "").strip().replace("\xa0", " ")
    pwd = os.getenv("GMAIL_APP_PASSWORD", "").strip().replace("\xa0", "")
    if not user or not pwd: st.info(f"[測試模式未寄信] {to}｜{sub}"); return False
    msg=MIMEText(body,"plain","utf-8"); msg["Subject"],msg["From"],msg["To"]=sub,user,to
    with smtplib.SMTP("smtp.gmail.com",587) as s: s.starttls(); s.login(user,pwd); s.send_message(msg)
    return True
def mail_booking(b, old_b=None, mode="create"):
    sub_map = {
        "create": (f"會議通知：{b['title']}", lambda p: f"{p['name']}，您於 {b['date']} {b['start']} 有一場關於 {b['title']} 的會議，地點在 {b['room']}，發起人為 {b['org_name']}，請備好相關文件，務必於會議開始前10分鐘抵達 {b['room']}。"),
        "cancel": (f"會議取消通知：{b['title']}", lambda p: f"{p['name']}，您於 {b['date']} {b['start']} 關於 {b['title']} 的會議已取消，請留意後續會議時程調整通知。"),
        "time": (f"會議時程更動通知：{b['title']}", lambda p: f"{p['name']}，關於您參與的 {b['title']} 的會議時程已更動至 {b['date']} {b['start']}，地點在 {b['room']}，發起人為 {b['org_name']}，請備好相關文件，留意更動時程，務必於會議開始前10分鐘抵達 {b['room']}。"),
        "room": (f"會議地點更動通知：{b['title']}", lambda p: f"{p['name']}，您於 {b['date']} {b['start']} 有一場關於 {b['title']} 的會議，地點更改為 {b['room']}，發起人為 {b['org_name']}，請備好相關文件，務必於會議開始前10分鐘抵達 {b['room']}。"),
        "both": (f"會議時程與地點更動通知：{b['title']}", lambda p: f"{p['name']}，關於您參與的 {b['title']} 的會議時程已更動至 {b['date']} {b['start']}，地點更改在 {b['room']}，發起人為 {b['org_name']}，請備好相關文件，留意更動時程，務必於會議開始前10分鐘抵達 {b['room']}。")
    }
    if mode == "update" and old_b:
        t_chg = (old_b["date"] != b["date"] or old_b["start"] != b["start"])
        r_chg = (old_b["room"] != b["room"])
        if t_chg and r_chg: mode = "both"
        elif t_chg: mode = "time"
        elif r_chg: mode = "room"
        else: return True
    sub, body_func = sub_map.get(mode, sub_map["create"])
    for eid in b["people"]:
        if eid in EMP:
            p = EMP[eid]
            mail(p["email"], sub, body_func(p))
    return True
```

---

## 5. 變更紀錄 (Change Log)
- **2026/06/21**：
  - 定稿並歸檔基礎發信與多情境聯動發信（mail_booking）邏輯。
  - 保留特定環境變數 .replace("\xa0") 隱形字元清洗機制以防範環境密鑰驗證漏洞。