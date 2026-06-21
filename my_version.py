import os,json,time,smtplib,datetime as dt
from dotenv import load_dotenv
load_dotenv()
from email.mime.text import MIMEText
import streamlit as st
from pydantic import BaseModel,Field
DB="meeting_database.json";AUTO=1800
EMP={"A123456789":{"name":"查理","birthday":"20000101","email":"fantasticharlie@gmail.com","dept":"總經理室","role":"Boss"},"B123456789":{"name":"永和","birthday":"20000202","email":"ned5438@gmail.com","dept":"研發部","role":"Employee"},"C123456789":{"name":"思妤","birthday":"20000303","email":"jennysha26@gmail.com","dept":"研發部","role":"Employee"},"D123456789":{"name":"韋丞","birthday":"20000404","email":"Weicheng0307@gmail.com","dept":"人事部","role":"Employee"},"E123456789":{"name":"哲豪","birthday":"20000505","email":"ALIVEcso62@gmail.com","dept":"業務部","role":"Employee"}}
class GeminiMeetingReport(BaseModel):
    meeting_title:str=Field(description="正式會議主題")
    executive_summary:str=Field(description="核心決策與項目進度")
    key_topics:list[str]=Field(description="主要議題與下次會議目標")
    action_items:list[str]=Field(description="責任人、待辦事項與期限")
def save(db):
    with open(DB,"w",encoding="utf-8") as f: json.dump(db,f,ensure_ascii=False,indent=2)
def db():
    if not os.path.exists(DB): save({"bookings":[],"reports":[]})
    with open(DB,encoding="utf-8") as f: return json.load(f)
def ts(): return [f"{h:02d}:{m:02d}" for h in range(9,21) for m in (0,30)] + ["21:00"]
def dtime(d,t): return dt.datetime.strptime(f"{d} {t}","%Y-%m-%d %H:%M")
def valid(d,s,e):
    a,b=dtime(d,s),dtime(d,e)
    if not (dt.time(9)<=a.time() and b.time()<=dt.time(21)): return "預約失敗：會議時間必須在營業時間 09:00 至 21:00 之間。"
    if a.minute not in (0,30) or b.minute not in (0,30): return "預約失敗：會議時間間距必須以 30 分鐘為單位（例如 10:00 或 10:30）。"
    if (b-a).total_seconds()<1800: return "預約失敗：結束時間必須晚於開始時間至少 30 分鐘。"
    if (a-dt.datetime.now()).total_seconds()<3600: return "操作失敗：會議預約、變更或取消必須在會議開始 1 小時前進行。"
    return ""
def hit(room,d,s,e,skip=""):
    a,b=dtime(d,s),dtime(d,e)
    return any(x["id"]!=skip and x["room"]==room and x["date"]==d and a<dtime(d,x["end"])+dt.timedelta(minutes=30) and b>dtime(d,x["start"])-dt.timedelta(minutes=30) for x in db()["bookings"])
def user_hit(uid,d,s,e):
    a,b=dtime(d,s),dtime(d,e)
    return next((x["id"] for x in db()["bookings"] if uid in x["people"] and x["date"]==d and a<dtime(d,x["end"]) and b>dtime(d,x["start"])),"")
def time_grid(room, d):
    times = ts(); bookings = [x for x in db()["bookings"] if x["room"] == room and x["date"] == d]
    def is_slot_busy(s):
        t = dtime(d, s)
        return any(dtime(d, b["start"]) - dt.timedelta(minutes=30) <= t < dtime(d, b["end"]) + dt.timedelta(minutes=30) for b in bookings) or t <= dt.datetime.now() + dt.timedelta(hours=1) 
    c_s, c_e = st.columns(2)
    with c_s: start = st.selectbox("開始時間", times[:-1], key=f"sel_s_{room}_{d}")
    with c_e:
        if is_slot_busy(start): end = "該時段無法預約"; st.selectbox("結束時間", ["該時段無法預約"], disabled=True, key=f"sel_e_{room}_{d}")
        else:
            valid_ends = []
            for e in times[times.index(start)+1:]:
                if is_slot_busy(times[times.index(e)-1]): break
                valid_ends.append(e)
            if valid_ends: end = st.selectbox("結束時間", valid_ends, key=f"sel_e_{room}_{d}")
            else: end = "該時段無法預約"; st.selectbox("結束時間", ["該時段無法預約"], disabled=True, key=f"sel_e_{room}_{d}")          
    st.markdown("<p style='font-size:14px; font-weight:bold; margin-top:15px; margin-bottom:5px;'>會議室當日預訂狀態時間軸</p>", unsafe_allow_html=True)
    st.markdown("""
        <style>
        div[data-testid='stHorizontalBlock'] > div { min-width: 0px !important; padding: 0px !important; }
        .timeline-container { display: flex; width: 100%; border: 1px solid #cbd5e1; height: 35px; border-radius: 6px; overflow: hidden; }
        .timeline-labels { display: flex; width: 100%; position: relative; height: 25px; margin-top: 4px; }
        .timeline-label-item { position: absolute; transform: translateX(-50%); font-size: 11px; font-weight: 600; color: #475569; white-space: nowrap; }
        </style>
    """, unsafe_allow_html=True)
    active_labels = { "09:00": 0.0, "21:00": 100.0 }
    t_base = dt.datetime.strptime(f"{d} 09:00", "%Y-%m-%d %H:%M")
    get_pos = lambda ts_str: ((dt.datetime.strptime(f"{d} {ts_str}", "%Y-%m-%d %H:%M") - t_base).total_seconds() / 43200) * 100    
    is_past_day = dt.datetime.now().date() > dt.datetime.strptime(d, "%Y-%m-%d").date()    
    if not is_past_day:
        past_limit = dt.datetime.now() + dt.timedelta(hours=1)
        if t_base < past_limit < t_base + dt.timedelta(hours=12):
            mins_rem = past_limit.minute % 30
            if mins_rem != 0: past_limit += dt.timedelta(minutes=(30 - mins_rem))
            past_str = past_limit.strftime("%H:%M")
            active_labels[past_str] = get_pos(past_str)
        if end != "該時段無法預約" and start and end:
            active_labels[start], active_labels[end] = get_pos(start), get_pos(end)
        for b in bookings:
            b_s = dtime(d, b["start"]) - dt.timedelta(minutes=30)
            b_e = dtime(d, b["end"]) + dt.timedelta(minutes=30)
            if t_base <= b_s <= t_base + dt.timedelta(hours=12): active_labels[b_s.strftime("%H:%M")] = get_pos(b_s.strftime("%H:%M"))
            if t_base <= b_e <= t_base + dt.timedelta(hours=12): active_labels[b_e.strftime("%H:%M")] = get_pos(b_e.strftime("%H:%M"))           
    bar_html = "<div class='timeline-container'>"
    for s in times[:-1]:
        if end != "該時段無法預約" and start and end and dtime(d, start) <= dtime(d, s) < dtime(d, end): bg_style = "background-color: #4ade80;"
        elif is_slot_busy(s): bg_style = "background-color: #e2e8f0; background-image: linear-gradient(45deg, #cbd5e1 25%, transparent 25%, transparent 50%, #cbd5e1 50%, #cbd5e1 75%, transparent 75%, transparent); background-size: 8px 8px;"
        else: bg_style = "background-color: #ffffff;"
        bar_html += f"<div style='flex: 1; {bg_style}' title='{s}'></div>"
    bar_html += "</div>"; st.markdown(bar_html, unsafe_allow_html=True)
    labels_html = "<div class='timeline-labels'>"
    for s, pos in sorted(active_labels.items(), key=lambda x: x[1]):
        labels_html += f"<div class='timeline-label-item' style='left: {pos}%;'>{s}</div>"
    labels_html += "</div>"; st.markdown(labels_html, unsafe_allow_html=True)
    st.markdown("""
        <div style='display: flex; gap: 20px; font-size: 12px; margin-top: 5px; justify-content: center;'>
            <div style='display: flex; align-items: center; gap: 6px;'><div style='width: 14px; height: 14px; background: #4ade80; border-radius: 3px;'></div>已選擇</div>
            <div style='display: flex; align-items: center; gap: 6px;'><div style='width: 14px; height: 14px; background: #cbd5e1; border-radius: 3px; background-image: linear-gradient(45deg, #94a3b8 25%, transparent 25%, transparent 50%, #94a3b8 50%, #94a3b8 75%, transparent 75%, transparent); background-size: 4px 4px;'></div>不可預訂</div>
            <div style='display: flex; align-items: center; gap: 6px;'><div style='width: 14px; height: 14px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 3px;'></div>可預訂</div>
        </div><br>
    """, unsafe_allow_html=True)  
    return (start, end) if end != "該時段無法預約" else (start, "")
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
def report_body(r):
    rr=r["report"]
    return f"""會議大綱：{rr['meeting_title']}
項目進度：{rr['executive_summary']}
與會人待辦事項與期限：
{chr(10).join('- '+x for x in rr['action_items'])}
下次會議目標：
{chr(10).join('- '+x for x in rr['key_topics'])}"""
def mail_report(r):
    b=next((x for x in db()["bookings"] if x["id"]==r["booking_id"]),None)
    if b:
        for eid in b["people"]: mail(EMP[eid]["email"],f"會議摘要：{r['report']['meeting_title']}",report_body(r))
def auto_mail():
    data=db();changed=False
    for r in data["reports"]:
        if not r["sent"] and not r["is_confirmed"] and time.time()-r["created"]>=AUTO:
            mail_report(r); r["sent"]=changed=True
    if changed: save(data)
def stt(file):
    try:
        from openai import OpenAI
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY")).audio.transcriptions.create(model="whisper-1",file=file).text
    except Exception:
        return "測試逐字稿：確認登入權限、預約防呆與摘要通知流程。研發部需於下週五前完成整合測試。"
def ai_report(text):
    prompt=f"你是企業會議助理。請輸出 JSON，僅含 meeting_title、executive_summary、key_topics、action_items，並涵蓋會議大綱、項目進度、待辦與期限、下次會議目標。逐字稿：{text}"
    try:
        from google import genai
        from google.genai import types
        res=genai.Client(api_key=os.getenv("GEMINI_API_KEY")).models.generate_content(model="gemini-2.5-flash",contents=prompt,config=types.GenerateContentConfig(response_mime_type="application/json",response_schema=GeminiMeetingReport))
        return json.loads(res.text)
    except Exception:
        return {"meeting_title":"測試會議摘要","executive_summary":"已完成預約、防呆、權限、轉譯摘要與通知流程驗證。","key_topics":["下次檢查真實 API 與 SMTP","確認會議紀錄權限"],"action_items":["[研發部] 下週五前完成整合測試","[產品部] 明天下班前整理驗收清單"]}
st.set_page_config("AI 智慧會議室管理系統",layout="wide"); auto_mail()
st.title("AI 智慧會議室管理系統 - 個人測試版")
if "uid" not in st.session_state:
    with st.form("login"):
        uid=st.text_input("身分證字號"); pw=st.text_input("生日 YYYYMMDD",type="password")
        ok=st.form_submit_button("登入")
    if ok and uid in EMP and EMP[uid]["birthday"]==pw: st.session_state.uid=uid; st.rerun()
    if ok: st.error("登入失敗")
    st.stop()
me=EMP[st.session_state.uid]
st.caption(f"{me['name']}｜{me['role']}｜{me['dept']}")
if st.button("登出"): st.session_state.clear(); st.rerun()
t1,t2,t3=st.tabs(["會議預約","錄音摘要","會議紀錄"])
with t1:
    title=st.text_input("會議主題","核心系統專案討論會")
    room=st.selectbox("會議室",["A會議室","B會議室","C會議室"])
    date=str(st.date_input("日期",dt.date.today()))
    start,end=time_grid(room,date)
    st.caption(f"已選擇：{start or '--:--'} ~ {end or '--:--'}")
    people=st.multiselect("與會人員",list(EMP),[st.session_state.uid],format_func=lambda x: EMP[x]["name"])
    if st.button("確認預約"):
        if not start or not end: st.error("預約失敗：當前選擇的時段無法預約，請重新選擇有效的時間。")
        else:
            err=valid(date,start,end) or ("預約失敗：該時段與既有預約或前後 30 分鐘緩衝期衝突。" if hit(room,date,start,end) else "")
            if err: st.error(err); st.session_state.pop("force_book",None)
            elif st.session_state.uid not in people: st.error("預約失敗：發起人必須在與會名單內。"); st.session_state.pop("force_book",None)
            else:
                overlap_id=user_hit(st.session_state.uid,date,start,end)
                if overlap_id and not st.session_state.get("force_book"):
                    st.warning(f"⚠️ 提示：您在該時段已參與其他會議（會議代碼：{overlap_id}），請確認是否仍要預約此時段？")
                    if st.button("我了解，仍要確認預約"): st.session_state.force_book=True; st.rerun()
                else:
                    data=db(); b={"id":f"BK{int(time.time())}","title":title,"room":room,"date":date,"start":start,"end":end,"org":st.session_state.uid,"org_name":me["name"],"people":people}
                    data["bookings"].append(b); save(data); mail_booking(b); st.session_state.pop("force_book",None); st.success(f"預約成功：{b['id']}")
    st.subheader("我的可管理預約")
data=db()
for b in [x for x in data["bookings"] if x["org"]==st.session_state.uid]:
    with st.expander(f"{b['id']}｜{b['title']}｜{b['date']} {b['start']}-{b['end']} ({b['room']})"):
        nr=st.selectbox("新會議室",["A會議室","B會議室","C會議室"],["A會議室","B會議室","C會議室"].index(b["room"]),key="r"+b["id"])
        nd=str(st.date_input("新日期",dtime(b["date"],b["start"]).date(),key="d"+b["id"]))
        ns,ne=time_grid(nr,nd)
        st.caption(f"新時段：{ns or '--:--'} ~ {ne or '--:--'}")
        if st.button("變更會議",key="u"+b["id"]):
            if not ns or not ne: st.error("變更失敗：新選擇的時段或會議室無法預約。")
            else:
                err=valid(nd,ns,ne) or ("變更失敗：新時段與既有預約或前後 30 分鐘緩衝期衝突。" if hit(nr,nd,ns,ne,b["id"]) else "")
                if err: st.error(err)
                else:
                    old_b=b.copy()
                    b.update({"room":nr,"date":nd,"start":ns,"end":ne})
                    save(data); mail_booking(b,old_b=old_b,mode="update"); st.success("已變更"); st.rerun()
        if st.button("取消會議",key="c"+b["id"]):
            err=valid(b["date"],b["start"],b["end"])
            if err: st.error(err)
            else: data["bookings"]=[x for x in data["bookings"] if x["id"]!=b["id"]]; save(data); mail_booking(b,mode="cancel"); st.success("已取消"); st.rerun()
with t2:
    own=[b for b in db()["bookings"] if b["org"]==st.session_state.uid]
    if not own: st.info("請先建立一筆由你發起的會議。")
    else:
        pick=st.selectbox("選擇會議",own,format_func=lambda b:f"{b['id']}｜{b['title']}")
        audio=st.file_uploader("會議錄音",type=["mp3","wav"])
        if st.button("轉譯並生成摘要") and audio:
            data=db(); text=stt(audio)
            data["reports"].append({"id":f"RP{int(time.time())}","booking_id":pick["id"],"transcript":text,"report":ai_report(text),"is_confirmed":False,"sent":False,"created":time.time()})
            save(data); st.success("摘要已建立，30 分鐘內未確認會自動寄出。")
        for r in [x for x in db()["reports"] if any(b["id"]==x["booking_id"] for b in own)]:
            with st.expander(f"{r['id']}｜{r['report']['meeting_title']}｜sent={r['sent']}"):
                st.json(r["report"])
                if not r["sent"] and st.button("確認發送",key=r["id"]):
                    mail_report(r); data=db();
                    for x in data["reports"]:
                        if x["id"]==r["id"]: x["is_confirmed"] = x["sent"] = True
                    save(data); st.success("摘要已寄出")
with t3:
    visible=db()["bookings"] if me["role"]=="Boss" else [b for b in db()["bookings"] if st.session_state.uid in b["people"]]
    for b in visible:
        st.write(f"{b['id']}｜{b['title']}｜{b['room']}｜{b['date']} {b['start']}-{b['end']}｜發起人：{b['org_name']}")
        for r in [x for x in db()["reports"] if x["booking_id"]==b["id"]]: st.caption(f"摘要：{r['report']['meeting_title']}｜is_confirmed={r['is_confirmed']}｜sent={r['sent']}")
