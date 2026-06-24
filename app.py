import os, sys, json, time, smtplib, threading, logging, datetime as dt, secrets
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
DOTENV_LOADED = load_dotenv(ENV_PATH, override=True)

from email.mime.text import MIMEText
from email.utils import formataddr

import streamlit as st

from streamlit.runtime.scriptrunner import get_script_run_ctx

from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

if get_script_run_ctx() is None:
    print("This is a Streamlit app. Please run it with: python -m streamlit run app.py")
    sys.exit(0)


DB = str(BASE_DIR / "meeting_database.json")

AUTO = 1800

LOGIN_SESSION_TTL = 86400

DEFAULT_REFRESH_SECONDS = 30

def env_email(key, fallback):
    return os.getenv(key, fallback).strip()

def env_app_password(key):
    return os.getenv(key, "").replace(" ", "").strip()

def env_status():
    employee_keys = [f"EMP_{code}_APP_PASSWORD" for code in "ABCDE"]
    pending_accounts = 0
    try:
        if os.path.exists(DB):
            with open(DB, encoding="utf-8") as f:
                pending_accounts = len(json.load(f).get("account_requests", []))
    except Exception:
        pending_accounts = 0
    return {
        ".env path": str(ENV_PATH),
        ".env exists": ENV_PATH.exists(),
        ".env loaded": DOTENV_LOADED,
        "Local Whisper model": os.getenv("WHISPER_MODEL_SIZE", "base"),
        "Gemini key": bool(os.getenv("GEMINI_API_KEY")),
        "System mail sender": env_email("EMP_C_EMAIL", "jennysha26@gmail.com"),
        "System mail host": "smtp.gmail.com",
        "Employee email count": sum(bool(os.getenv(f"EMP_{code}_EMAIL")) for code in "ABCDE"),
        "System mail password": bool(env_app_password("EMP_C_APP_PASSWORD")),
        "Pending account requests": pending_accounts,
    }

EMP = {

    "A123456789": {"name": "查理", "birthday": "20000101", "email": env_email("EMP_A_EMAIL", "fantasticharlie@gmail.com"), "dept": "總經理室", "role": "Boss"},

    "B123456789": {"name": "永和", "birthday": "20000202", "email": env_email("EMP_B_EMAIL", "ned5438@gmail.com"), "dept": "研發部", "role": "Employee"},

    "C123456789": {"name": "思妤", "birthday": "20000303", "email": env_email("EMP_C_EMAIL", "jennysha26@gmail.com"), "dept": "研發部", "role": "SuperAdmin"},

    "D123456789": {"name": "韋丞", "birthday": "20000404", "email": env_email("EMP_D_EMAIL", "Weicheng0307@gmail.com"), "dept": "人事部", "role": "Employee"},

    "E123456789": {"name": "哲豪", "birthday": "20000505", "email": env_email("EMP_E_EMAIL", "ALIVEcso62@gmail.com"), "dept": "業務部", "role": "Employee"}

}

SUPER_ADMIN_EMAIL = "jennysha26@gmail.com"

def is_super_admin(uid):
    user = EMP.get(uid, {})
    return user.get("role") == "SuperAdmin" or user.get("email", "").lower() == SUPER_ADMIN_EMAIL

def visible_bookings(data, uid):
    if is_super_admin(uid):
        return data["bookings"]
    return [b for b in data["bookings"] if b["org"] == uid]

def visible_record_bookings(data, uid):
    if is_super_admin(uid):
        return data["bookings"]
    return [b for b in data["bookings"] if b["org"] == uid or uid in b.get("people", [])]

def employee_label(eid):
    p = EMP.get(eid)
    if not p:
        return eid
    return f"{p['name']} <{p['email']}>"

def attendee_names(people):
    return "、".join(employee_label(eid) for eid in people) if people else "無"

class GeminiMeetingReport(BaseModel):

    meeting_title: str = Field(description="正式會議主題")

    executive_summary: str = Field(description="核心決策與項目進度")

    key_topics: list[str] = Field(description="主要議題與下次會議目標")

    action_items: list[str] = Field(description="責任人、待辦事項與期限")

def save(db):

    with open(DB, "w", encoding="utf-8") as f: 

        json.dump(db, f, ensure_ascii=False, indent=2)


def db():

    if not os.path.exists(DB): save({"bookings": [], "reports": [], "employees": {}, "account_requests": [], "login_sessions": {}})

    with open(DB, encoding="utf-8") as f:
        data = json.load(f)

    changed = False
    for key, default in {"bookings": [], "reports": [], "employees": {}, "account_requests": [], "login_sessions": {}}.items():
        if key not in data:
            data[key] = default
            changed = True
    if changed:
        save(data)
    return data


def load_dynamic_employees():

    for uid, profile in db().get("employees", {}).items():

        if uid not in EMP:

            EMP[uid] = profile


def cleanup_login_sessions(data):

    now = time.time()

    sessions = data.get("login_sessions", {})

    active = {token: item for token, item in sessions.items() if item.get("expires", 0) > now}

    if len(active) != len(sessions):

        data["login_sessions"] = active

        return True

    return False


def create_login_session(uid):

    data = db()

    cleanup_login_sessions(data)

    token = secrets.token_urlsafe(32)

    data["login_sessions"][token] = {"uid": uid, "expires": time.time() + LOGIN_SESSION_TTL}

    save(data)

    return token


def restore_login_session():

    token = st.query_params.get("auth", "")

    if not token:

        return

    data = db()

    changed = cleanup_login_sessions(data)

    session = data.get("login_sessions", {}).get(token)

    if not session:

        if changed:

            save(data)

        return

    uid = session.get("uid", "")

    if uid in EMP:

        st.session_state.uid = uid

        data["login_sessions"][token]["expires"] = time.time() + LOGIN_SESSION_TTL

        save(data)


def clear_login_session():

    token = st.query_params.get("auth", "")

    if token:

        data = db()

        if token in data.get("login_sessions", {}):

            del data["login_sessions"][token]

            save(data)

        del st.query_params["auth"]

    st.session_state.clear()


def inject_auto_refresh(seconds):

    if seconds <= 0:

        return

    st.markdown(
        f"""
        <script>
        setTimeout(function() {{
            window.parent.location.reload();
        }}, {int(seconds) * 1000});
        </script>
        """,
        unsafe_allow_html=True,
    )


def account_request_exists(uid, email):

    data = db()

    email = email.lower().strip()

    if uid in EMP or uid in data.get("employees", {}):
        return "此身分證字號已經有帳號。"

    if any(req["uid"] == uid for req in data.get("account_requests", [])):
        return "此身分證字號已有待審申請。"

    if email and any(req["email"].lower() == email for req in data.get("account_requests", [])):
        return "此 Email 已有待審申請。"

    if email and any(profile.get("email", "").lower() == email for profile in EMP.values()):
        return "此 Email 已經有帳號。"

    return ""


def submit_account_request(uid, name, birthday, email, dept):

    request = {
        "id": f"AR{int(time.time())}",
        "uid": uid.strip(),
        "name": name.strip(),
        "birthday": birthday.strip(),
        "email": email.strip(),
        "dept": dept.strip(),
        "role": "Employee",
        "created": time.time(),
    }

    data = db()

    data["account_requests"].append(request)

    save(data)

    body = (
        "有新的帳號申請等待審核：\n\n"
        f"申請單號：{request['id']}\n"
        f"姓名：{request['name']}\n"
        f"身分證字號：{request['uid']}\n"
        f"部門：{request['dept']}\n"
        f"Email：{request['email']}\n\n"
        "請登入會議室系統，到「帳號審核」頁籤確認。"
    )

    api_send_real_email(SUPER_ADMIN_EMAIL, "新帳號申請待審核", body, to_name="最高權限者")

    return request["id"]


def approve_account_request(request_id):

    data = db()

    request = next((item for item in data["account_requests"] if item["id"] == request_id), None)

    if not request:
        return False

    data["employees"][request["uid"]] = {
        "name": request["name"],
        "birthday": request["birthday"],
        "email": request["email"],
        "dept": request["dept"],
        "role": request.get("role", "Employee"),
    }

    data["account_requests"] = [item for item in data["account_requests"] if item["id"] != request_id]

    save(data)

    load_dynamic_employees()

    api_send_real_email(
        request["email"],
        "帳號申請已通過",
        f"{request['name']} 您好：\n\n您的會議室系統帳號已審核通過，現在可以使用身分證字號與生日登入。",
        to_name=request["name"],
    )

    return True


def reject_account_request(request_id):

    data = db()

    request = next((item for item in data["account_requests"] if item["id"] == request_id), None)

    if not request:
        return False

    data["account_requests"] = [item for item in data["account_requests"] if item["id"] != request_id]

    save(data)

    api_send_real_email(
        request["email"],
        "帳號申請未通過",
        f"{request['name']} 您好：\n\n您的會議室系統帳號申請未通過，若有疑問請聯絡系統管理者。",
        to_name=request["name"],
    )

    return True


def employee_contact(eid):

    person = EMP.get(eid, {})

    name = person.get("name", eid)

    email = person.get("email", "")

    if email:

        return f"{name} [{email}](mailto:{email})"

    return name


def render_report_bullets(report, booking=None):

    title = report.get("meeting_title", "未命名會議摘要")

    summary = report.get("executive_summary", "")

    key_topics = report.get("key_topics", [])

    action_items = report.get("action_items", [])

    if booking:

        st.markdown(f"**發起人：** {employee_contact(booking.get('org', ''))}")

        attendees = "、".join(employee_contact(eid) for eid in booking.get("people", [])) or "無"

        st.markdown(f"**與會人員：** {attendees}")

        st.markdown("---")

    st.markdown(f"### {title}")

    if summary:

        st.markdown("**摘要**")

        st.markdown(f"- {summary}")

    if key_topics:

        st.markdown("**主要議題 / 下次目標**")

        for topic in key_topics:

            st.markdown(f"- {topic}")

    if action_items:

        st.markdown("**待辦事項**")

        for item in action_items:

            st.markdown(f"- {item}")


def ts():

    return [f"{h:02d}:{m:02d}" for h in range(9, 21) for m in range(0, 60, 10)] + ["21:00"]


def dtime(d, t): 

    return dt.datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")


def valid(d, s, e):

    a, b = dtime(d, s), dtime(d, e)

    if not (dt.time(9) <= a.time() and b.time() <= dt.time(21)): return "預約失敗：會議時間必須在營業時間 09:00 至 21:00 之間。"

    if a.minute % 10 != 0 or b.minute % 10 != 0: return "預約失敗：會議時間間距必須以 10 分鐘為單位（例如 10:00 或 10:10）。"

    if (b - a).total_seconds() < 1800: return "預約失敗：結束時間必須晚於開始時間至少 30 分鐘。"

    if (a - dt.datetime.now()).total_seconds() < 3600: return "操作失敗：會議預約、變更或取消必須在會議開始 1 小時前進行。"

    return ""


def hit(room, d, s, e, skip=""):

    a, b = dtime(d, s), dtime(d, e)

    return any(x["id"] != skip and x["room"] == room and x["date"] == d and a < dtime(d, x["end"]) + dt.timedelta(minutes=30) and b > dtime(d, x["start"]) - dt.timedelta(minutes=30) for x in db()["bookings"])


def user_hit(uid, d, s, e):

    a, b = dtime(d, s), dtime(d, e)

    return next((x["id"] for x in db()["bookings"] if uid in x["people"] and x["date"] == d and a < dtime(d, x["end"]) and b > dtime(d, x["start"])), "")


def time_grid(room, d, def_s=None, def_e=None, exclude_booking_id="", widget_key=""):

    times = ts()

    bookings = [x for x in db()["bookings"] if x["room"] == room and x["date"] == d and x["id"] != exclude_booking_id]

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

        start_key = f"{widget_key}_start_{room}_{d}" if widget_key else f"sel_s_{room}_{d}_{def_s}"
        start = st.selectbox("開始時間", valid_starts, index=valid_starts.index(def_s) if def_s in valid_starts else 0, key=start_key)

    

    with c_e:

        valid_ends = []

        start_idx = times.index(start)

        for e in times[start_idx+3:]:

            if any(is_slot_busy(times[step]) for step in range(start_idx, times.index(e))): break

            valid_ends.append(e)

        end_options = valid_ends if valid_ends else ["該時段無法預約"]
        end_key = f"{widget_key}_end_{room}_{d}" if widget_key else f"sel_e_{room}_{d}_{def_s}"
        end = st.selectbox(
            "結束時間",
            end_options,
            index=valid_ends.index(def_e) if def_e in valid_ends else 0,
            disabled=not valid_ends,
            key=end_key,
        )

        if not valid_ends: end = "該時段無法預約"

    st.markdown("""
        <style>
        div[data-testid='stHorizontalBlock'] > div { min-width: 0px !important; padding: 0px !important; }
        .timeline-container { display: flex; width: 100%; border: 1px solid #cbd5e1; height: 35px; border-radius: 6px; overflow: hidden; background-color: #ffffff; margin-bottom: 25px; }
        .timeline-label-item { position: absolute; transform: translateX(-50%); font-size: 12px; font-weight: 600; color: #475569; white-space: nowrap; top: 39px; }
        </style>
    """, unsafe_allow_html=True)

    active_labels = {"09:00": 0.0, "21:00": 100.0}
    t_base = dtime(d, "09:00")
    t_end = dtime(d, "21:00")
    get_pos = lambda ts_str: ((dtime(d, ts_str) - t_base).total_seconds() / 43200) * 100

    limit_boundary = limit_t.replace(second=0, microsecond=0)
    if limit_boundary < limit_t:
        limit_boundary += dt.timedelta(minutes=1)
    limit_boundary += dt.timedelta(minutes=(-limit_boundary.minute) % 10)
    limit_boundary = min(limit_boundary, t_end)

    unavailable_ranges = []
    if t_base <= limit_boundary:
        unavailable_ranges.append((t_base, limit_boundary))

    for b in bookings:
        buffer_start = max(dtime(d, b["start"]) - dt.timedelta(minutes=30), t_base)
        buffer_end = min(dtime(d, b["end"]) + dt.timedelta(minutes=30), t_end)
        unavailable_ranges.append((buffer_start, buffer_end))

    unavailable_ranges.sort(key=lambda interval: interval[0])
    merged_ranges = []

    for range_start, range_end in unavailable_ranges:
        if merged_ranges and range_start <= merged_ranges[-1][1]:
            merged_start, merged_end = merged_ranges[-1]
            merged_ranges[-1] = (merged_start, max(merged_end, range_end))
        else:
            merged_ranges.append((range_start, range_end))

    for range_start, range_end in merged_ranges:
        for boundary in (range_start, range_end):
            label = boundary.strftime("%H:%M")
            active_labels[label] = get_pos(label)

    if end != "該時段無法預約" and start and end:
        active_labels[start] = get_pos(start)
        active_labels[end] = get_pos(end)

    bar_html = "<div style='position: relative; width: 100%;'><div class='timeline-container'>"
    for s in times[:-1]:
        is_selected = end != "該時段無法預約" and start and end and dtime(d, start) <= dtime(d, s) < dtime(d, end)
        bg_style = (
            "background-color: #4ade80;"
            if is_selected
            else (
                "background-color: #e2e8f0; background-image: linear-gradient(45deg, #cbd5e1 25%, transparent 25%, transparent 50%, #cbd5e1 50%, #cbd5e1 75%, transparent 75%, transparent); background-size: 8px 8px;"
                if is_slot_busy(s)
                else "background-color: #ffffff;"
            )
        )
        bar_html += f"<div style='width: calc(100% / 72); flex-shrink: 0; {bg_style}' title='{s}'></div>"
    bar_html += "</div>"

    for s, pos in sorted(active_labels.items(), key=lambda x: x[1]):
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

def ensure_local_ffmpeg():

    """把 imageio-ffmpeg 內建的 ffmpeg 加進 PATH，避免要求使用者另外裝系統 FFmpeg。"""

    try:

        import imageio_ffmpeg

        ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())

        bin_dir = BASE_DIR / ".local_bin"

        bin_dir.mkdir(exist_ok=True)

        shim = bin_dir / "ffmpeg.exe"

        if not shim.exists():

            shim.write_bytes(ffmpeg_path.read_bytes())

        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{ffmpeg_path.parent}{os.pathsep}{os.environ.get('PATH', '')}"

        return str(ffmpeg_path)

    except Exception as e:

        logging.warning(f"imageio-ffmpeg 初始化失敗: {e}")

        return ""


@st.cache_resource(show_spinner=False)
def load_local_whisper_model(model_size):

    """載入本地 Whisper 模型，Streamlit 會快取模型，避免每次重新載入。"""

    import whisper

    return whisper.load_model(model_size)


def api_transcribe_audio(file):

    """使用本地 openai-whisper 進行語音轉文字，不呼叫 OpenAI API。"""

    import tempfile

    try:

        ensure_local_ffmpeg()

        model_size = os.getenv("WHISPER_MODEL_SIZE", "base").strip() or "base"

        language = os.getenv("WHISPER_LANGUAGE", "zh").strip() or "zh"

        suffix = Path(file.name).suffix or ".wav"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:

            tmp.write(file.getvalue())

            audio_path = tmp.name

        model = load_local_whisper_model(model_size)

        result = model.transcribe(

            audio_path,

            language=language,

            fp16=False,

            verbose=False,

        )

        return result.get("text", "").strip()

    except ModuleNotFoundError:

        raise Exception("轉譯失敗：尚未安裝本地 Whisper。請先執行 `python -m pip install -U openai-whisper imageio-ffmpeg`。")

    except Exception as e:

        logging.error(f"本地 Whisper STT 錯誤: {e}")

        raise Exception(f"轉譯失敗，請確認 openai-whisper 與 FFmpeg 已正確安裝：{str(e)}")

    finally:

        if "audio_path" in locals():

            Path(audio_path).unlink(missing_ok=True)


def local_fallback_summary(text):

    """Gemini 額度不足或暫時不可用時，用本地規則產生基本摘要，確保文稿仍能存檔。"""

    cleaned = " ".join(text.split())

    preview = cleaned[:300] if cleaned else "本次音訊未辨識出明確文字內容。"

    return {

        "meeting_title": "本地備援會議摘要",

        "executive_summary": f"Gemini 目前無法產生 AI 摘要，系統已先保存語音轉文字文稿。文稿開頭：{preview}",

        "key_topics": ["請稍後在 Gemini 額度恢復後重新上傳，或依逐字稿人工整理會議重點。"],

        "action_items": ["請查看完整語音轉文字文稿，確認待辦事項與負責人。"],

    }


def api_generate_summary(text):

    """API 2: Gemini 結構化提煉接口，遇到 503 會自動重試與切換備援模型。"""

    prompt = f"你是企業會議助理。請根據以下會議逐字稿，精準萃取資訊並輸出指定的 JSON 格式。逐字稿內容：\n{text}"

    from google import genai

    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:

        raise Exception("摘要生成失敗：缺少 GEMINI_API_KEY，請確認 .env 設定。")

    client = genai.Client(api_key=api_key)

    primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

    fallback_models = [

        model.strip()

        for model in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash-lite,gemini-2.0-flash").split(",")

        if model.strip() and model.strip() != primary_model

    ]

    models = [primary_model] + fallback_models

    last_error = None

    for model in models:

        for attempt in range(3):

            try:

                res = client.models.generate_content(

                    model=model,

                    contents=prompt,

                    config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=GeminiMeetingReport, temperature=0.2)

                )

                return json.loads(res.text)

            except Exception as e:

                last_error = e

                msg = str(e)

                quota_exhausted = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()

                retryable = "503" in msg or "UNAVAILABLE" in msg

                logging.warning(f"Gemini 摘要失敗 model={model} attempt={attempt + 1}/3 retryable={retryable} quota_exhausted={quota_exhausted}: {e}")

                if quota_exhausted:

                    logging.warning("Gemini 額度已用完，改用本地備援摘要。")

                    return local_fallback_summary(text)

                if not retryable:

                    break

                time.sleep(2 * (attempt + 1))

    logging.error(f"Gemini 生成錯誤: {last_error}")

    logging.warning("Gemini 目前忙碌或不可用，改用本地備援摘要。")

    return local_fallback_summary(text)


def api_send_real_email(to_email, subject, body, sender_id="", to_name=""):

    """API 3: SMTP 真實寄信接口。所有系統通知一律使用 Jenny 系統信箱寄出。"""

    user = env_email("EMP_C_EMAIL", "jennysha26@gmail.com")

    pwd = env_app_password("EMP_C_APP_PASSWORD")

    smtp_host = "smtp.gmail.com"

    smtp_port = 587

    sender_name = "會議室系統通知"

    if not user or not pwd: 

        logging.warning("[測試模式] 缺少系統信箱帳密，跳過寄信。")

        return False

    msg = MIMEText(body, "plain", "utf-8")

    msg["Subject"] = subject

    msg["From"] = formataddr((sender_name, user))

    msg["To"] = formataddr((to_name, to_email)) if to_name else to_email

    try:

        with smtplib.SMTP(smtp_host, smtp_port) as s: 

            s.starttls()

            s.login(user, pwd)

            s.send_message(msg)

        return True

    except Exception as e:

        logging.error(f"實體郵件發送失敗：{e}")

        return False

def mail_booking(b, old_b=None, mode="create"):

    sub_map = {

        "create": (f"會議通知：{b['title']}", lambda p: f"{p['name']}，您於 {b['date']} {b['start']} 有一場關於 {b['title']} 的會議，地點在 {b['room']}，發起人為 {b['org_name']}，請務必於會議開始前10分鐘抵達 {b['room']}。"),

        "cancel": (f"會議取消通知：{b['title']}", lambda p: f"{p['name']}，您於 {b['date']} {b['start']} 關於 {b['title']} 的會議已取消。"),

        "update": (f"會議異動通知：{b['title']}", lambda p: f"{p['name']}，關於 {b['title']} 的會議已更動至 {b['date']} {b['start']}，地點為 {b['room']}。")

    }

    mode = "update" if old_b else mode

    sub, body_func = sub_map.get(mode, sub_map["create"])

    for eid in b["people"]:

        if eid in EMP:

            api_send_real_email(EMP[eid]["email"], sub, body_func(EMP[eid]), sender_id=b.get("org", ""), to_name=EMP[eid]["name"])

    return True


def mail_report(r):

    """將生成的 JSON 報告轉為信件內文，發送給全體與會者"""

    b = next((x for x in db()["bookings"] if x["id"] == r["booking_id"]), None)

    if b:

        rr = r["report"]

        body = f"會議大綱：{rr['meeting_title']}\n項目進度：{rr['executive_summary']}\n與會人待辦事項與期限：\n" + "\n".join(f"- {x}" for x in rr['action_items']) + "\n下次會議目標：\n" + "\n".join(f"- {x}" for x in rr['key_topics'])

        sub = f"會議摘要：{rr['meeting_title']}"

        sent_count = 0

        failed = []

        for eid in b["people"]: 

            ok = api_send_real_email(EMP[eid]["email"], sub, body, sender_id=b.get("org", ""), to_name=EMP[eid]["name"])

            if ok:

                sent_count += 1

            else:

                failed.append(employee_label(eid))

        return sent_count, failed

    return 0, ["找不到對應會議"]

def remind_worker(rid, email, title):

    time.sleep(180)

    r = next((x for x in db()["reports"] if x["id"] == rid), None)

    if r and not r["is_confirmed"] and not r["sent"]:

        b = next((x for x in db()["bookings"] if x["id"] == r["booking_id"]), None)

        logging.info(f"[催簽發信觸發] 報告 {rid} 已逾時 180 秒未確認。")

        api_send_real_email(

            to_email=email, 

            subject=f"【催簽提醒】會議摘要待確認：{title}", 

            body=f"發起人您好：\n\n您的會議「{title}」之 AI 摘要已生成超過 180 秒，目前系統尚未收到確認。\n請儘速登入系統至「錄音摘要」頁籤進行核對與發送。謝謝！",

            sender_id=b.get("org", "") if b else ""

        )


def auto_mail():

    data = db(); changed = False

    for r in data["reports"]:

        if not r["sent"] and not r["is_confirmed"] and time.time() - r["created"] >= AUTO:

            _, failed = mail_report(r)

            if not failed:

                r["sent"] = changed = True

    if changed: save(data)

st.set_page_config("AI 智慧會議室管理系統", layout="wide"); auto_mail()


st.markdown("""

    <style>

    .report-card { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }

    .card-header { font-size: 18px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }

    .meta-tag { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; margin-right: 5px; }

    .tag-boss { background-color: #dbeafe; color: #1e40af; }

    .tag-emp { background-color: #f1f5f9; color: #475569; }

    .badge-active { background-color: #dcfce7; color: #14532d; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }

    .badge-pending { background-color: #fef9c3; color: #713f12; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }

    </style>

""", unsafe_allow_html=True)


st.title("智慧會議室排程與 AI 決策看板")


load_dynamic_employees()

restore_login_session()


if "uid" not in st.session_state:

    login_tab, request_tab = st.tabs(["安全登入", "申請帳號"])

    with login_tab:

        with st.form("login"):

            uid = st.text_input("身分證字號")

            pw = st.text_input("生日 YYYYMMDD", type="password")

            ok = st.form_submit_button("安全登入")

        if ok and uid in EMP and EMP[uid]["birthday"] == pw:

            st.session_state.uid = uid

            st.query_params["auth"] = create_login_session(uid)

            st.rerun()

        if ok:

            st.error("認證失敗：身分證字號或密碼錯誤，或帳號尚未審核通過。")

    with request_tab:

        with st.form("account_request"):

            req_uid = st.text_input("身分證字號", key="req_uid").strip()

            req_name = st.text_input("姓名", key="req_name").strip()

            req_birthday = st.text_input("生日 YYYYMMDD", key="req_birthday").strip()

            req_email = st.text_input("Email", key="req_email").strip()

            req_dept = st.text_input("部門", key="req_dept").strip()

            req_ok = st.form_submit_button("送出帳號申請")

        if req_ok:

            if not all([req_uid, req_name, req_birthday, req_email, req_dept]):

                st.error("請完整填寫身分證字號、姓名、生日、Email 與部門。")

            elif len(req_birthday) != 8 or not req_birthday.isdigit():

                st.error("生日格式需為 YYYYMMDD，例如 20000101。")

            elif "@" not in req_email or "." not in req_email:

                st.error("請輸入有效的 Email。")

            else:

                err = account_request_exists(req_uid, req_email)

                if err:

                    st.error(err)

                else:

                    rid = submit_account_request(req_uid, req_name, req_birthday, req_email, req_dept)

                    st.success(f"申請已送出，等待最高權限者審核。申請單號：{rid}")

    st.stop()


me = EMP[st.session_state.uid]

admin_mode = is_super_admin(st.session_state.uid)


c_user, c_logout = st.columns([8, 1])

with c_user:

    role_badge = f'<span class="meta-tag tag-boss">{me["role"]}</span>' if me["role"] in ("Boss", "SuperAdmin") else f'<span class="meta-tag tag-emp">同仁</span>'

    st.markdown(f"**當前使用者**：{me['name']} ｜ 部門：{me['dept']} ｜ 系統權限：{role_badge}", unsafe_allow_html=True)

with c_logout:

    if st.button("安全登出", use_container_width=True): clear_login_session(); st.rerun()

inject_auto_refresh(30)


st.markdown("---")

tab_labels = ["會議排程申請", "錄音音訊摘要", "企業會議紀錄"]

if admin_mode:

    tab_labels.append("帳號審核")

tabs = st.tabs(tab_labels)

t1, t2, t3 = tabs[:3]

t4 = tabs[3] if admin_mode else None

with t1:

    actor_uid = st.session_state.uid

    if admin_mode:

        actor_uid = st.selectbox("最高權限操作帳號", list(EMP), index=list(EMP).index(st.session_state.uid), format_func=lambda x: f"{EMP[x]['name']}｜{EMP[x]['email']}")

    actor = EMP[actor_uid]

    title = st.text_input("會議主題", "核心系統專案討論會")

    room = st.selectbox("會議室選擇", ["A會議室", "B會議室", "C會議室"])

    date = str(st.date_input("日期", dt.date.today()))

    start, end = time_grid(room, date)

    people = st.multiselect("指名與會人員", list(EMP), [actor_uid], format_func=lambda x: EMP[x]["name"])

    

    if st.button("送出預約申請", type="primary"):

        if not start or not end: st.error("預約失敗：當前選擇的時段無法預約。")

        else:

            err = valid(date, start, end) or ("預約失敗：該時段與既有預約或緩衝期衝突。" if hit(room, date, start, end) else "")

            if err: st.error(err)

            elif actor_uid not in people: st.error("預約失敗：發起人必須在與會名單內。")

            else:

                data = db()

                b = {"id": f"BK{int(time.time())}", "title": title, "room": room, "date": date, "start": start, "end": end, "org": actor_uid, "org_name": actor["name"], "people": people}

                data["bookings"].append(b); save(data); mail_booking(b); st.success(f"預約成功：{b['id']}")

    

    st.subheader("行程變更與異動管理")

data = db()

sorted_bookings = sorted(visible_bookings(data, st.session_state.uid), key=lambda x: (x.get("date", ""), x.get("start", "")))

for b in sorted_bookings:

    now = dt.datetime.now()
    start_dt = dtime(b["date"], b["start"])
    end_dt = dtime(b["date"], b["end"])
    
    if now > end_dt:
        prefix = "已結束:"
    elif start_dt <= now <= end_dt:
        prefix = "進行中:"
    else:
        prefix = "管理:"

    with st.expander(f"{prefix} {b['id']} ｜ {b['title']} ｜ {b['date']} {b['start']}-{b['end']}"):

        st.markdown(f"**發起人**：{employee_label(b.get('org', ''))}")

        st.markdown(f"**與會人員**：{attendee_names(b.get('people', []))}")

        if end_dt <= now:

            st.info("此會議已結束，無法再修改時程。")

            if st.button("刪除此歷史會議", key="c"+b["id"], use_container_width=True):

                data["bookings"] = [x for x in data["bookings"] if x["id"] != b["id"]]; save(data); st.success("已刪除歷史會議"); st.rerun()

            continue

        nr = st.selectbox("修改會議室", ["A會議室", "B會議室", "C會議室"], ["A會議室", "B會議室", "C會議室"].index(b["room"]), key="r"+b["id"])

        nd = str(st.date_input("修改日期", start_dt.date(), key="d"+b["id"]))

        ns, ne = time_grid(
            nr,
            nd,
            def_s=b["start"],
            def_e=b["end"],
            exclude_booking_id=b["id"],
            widget_key=f"edit_{b['id']}",
        )
        
        c_up, c_del = st.columns(2)

        with c_up:

            if st.button("儲存時間變更", key="u"+b["id"], use_container_width=True):

                if not ns or not ne: st.error("變更失敗：無法預約。")

                elif err := valid(nd, ns, ne) or ("變更失敗：該時段與既有預約或緩衝期衝突。" if hit(nr, nd, ns, ne, skip=b["id"]) else ""):

                    st.error(err)

                else:

                    old_b = b.copy()

                    b.update({"room": nr, "date": nd, "start": ns, "end": ne})

                    save(data); mail_booking(b, old_b=old_b, mode="update"); st.success("已變更時程"); st.rerun()

        with c_del:

            if st.button("撤銷此場會議", key="c"+b["id"], use_container_width=True):

                data["bookings"] = [x for x in data["bookings"] if x["id"] != b["id"]]; save(data); mail_booking(b, mode="cancel"); st.success("已成功撤銷會議"); st.rerun()

with t2:

    own = visible_bookings(db(), st.session_state.uid)

    if not own: st.info("目前尚無可操作的會議排程，建立預約後方可上傳開會錄音。")

    else:

        pick = st.selectbox("關聯會議綁定：", own, format_func=lambda b: f"{b['id']}｜{EMP.get(b['org'], {}).get('name', b['org'])}｜{b['title']}")

        audio = st.file_uploader("匯入現場開會音訊（支援 .mp3/.wav）：", type=["mp3", "wav"])

        if audio is not None:

            if st.button("提煉語音並派發 AI 任務", type="primary"):

                with st.spinner("AI 雙引擎連線中：Whisper 轉寫與 Gemini 提煉..."):

                    try:

                        real_text = api_transcribe_audio(audio)

                        real_report = api_generate_summary(real_text)

                        

                        data = db()

                        rid = f"RP{int(time.time())}"

                        data["reports"].append({"id": rid, "booking_id": pick["id"], "transcript": real_text, "report": real_report, "is_confirmed": False, "sent": False, "created": time.time()})

                        save(data)

                        st.success("真實結構化報告已生成！背景 Thread 已啟動 180 秒催簽倒數。")

                        

                        threading.Thread(target=remind_worker, args=(rid, me["email"], pick["title"]), daemon=True).start()

                    except Exception as e:

                        st.error(str(e))


        st.markdown("---")

        st.subheader("待確認與歷史摘要列表")

        booking_by_id = {b["id"]: b for b in own}

        for r in [x for x in db()["reports"] if x["booking_id"] in booking_by_id]:

            status_text = "已全員分發" if r["sent"] else "待審查發送 (180秒提醒)"

            with st.expander(f"報告單號: {r['id']} ｜ 狀態: {status_text}", expanded=not r["sent"]):

                render_report_bullets(r.get("report", {}), booking_by_id.get(r["booking_id"]))

                st.divider()

                if r.get("transcript"):

                    with st.expander("查看語音轉文字文稿"):

                        st.write(r["transcript"])

                

                if not r["sent"]:

                    c_send, c_delete = st.columns(2)

                    with c_send:

                        if st.button("核准並一鍵分發公文給全員", key=r["id"], type="primary", use_container_width=True):

                            with st.spinner("真實郵件 SMTP 派送中..."):

                                sent_count, failed = mail_report(r) 

                                if failed:

                                    st.error("部分或全部郵件未寄出：" + "、".join(failed))

                                    st.stop()

                                data = db()

                                for item in data["reports"]:

                                    if item["id"] == r["id"]:

                                        item["sent"] = True

                                        item["is_confirmed"] = True

                                        break

                                save(data)

                                st.success(f"已分發會議摘要，共寄出 {sent_count} 封。")

                                st.rerun()

                    delete_container = c_delete

                else:

                    st.success("此語音摘要已分發，發送鍵已停用。")

                    delete_container = st.container()

                with delete_container:

                    if st.button("刪除此語音摘要與文稿", key=f"del_report_{r['id']}", use_container_width=True):

                        data = db()

                        data["reports"] = [item for item in data["reports"] if item["id"] != r["id"]]

                        save(data)

                        st.success("已刪除語音摘要與文稿。")

                        st.rerun()


with t3:

    data = db()

    records = visible_record_bookings(data, st.session_state.uid)

    report_by_booking = {}

    for report in data.get("reports", []):

        report_by_booking.setdefault(report["booking_id"], []).append(report)

    if not records:

        st.info("目前沒有可查看的會議紀錄。")

    else:

        st.subheader("企業會議紀錄")

        st.caption("最高權限可查看全部會議；一般使用者只能查看自己發起或自己參與的會議。")

        records = sorted(records, key=lambda b: (b["date"], b["start"], b["id"]), reverse=True)

        for b in records:

            reports = report_by_booking.get(b["id"], [])

            with st.expander(f"{b['date']} {b['start']}-{b['end']} ｜ {b['room']} ｜ {b['title']}"):

                st.markdown(f"**會議主題**：{b['title']}")

                st.markdown(f"**時間地點**：{b['date']} {b['start']} - {b['end']} ｜ {b['room']}")

                st.markdown(f"**發起人**：{employee_label(b.get('org', ''))}")

                st.markdown(f"**與會人員**：{attendee_names(b.get('people', []))}")

                if not reports:

                    st.info("此會議尚未產生 AI 摘要紀錄。")

                for r in sorted(reports, key=lambda item: item.get("created", 0), reverse=True):

                    status = "已分發" if r.get("sent") else "未分發"

                    rr = r.get("report", {})

                    st.markdown("---")

                    st.markdown(f"**報告單號**：{r['id']} ｜ **狀態**：{status}")

                    st.markdown(f"**會議大綱**：{rr.get('meeting_title', '')}")

                    st.markdown(f"**項目進度**：{rr.get('executive_summary', '')}")

                    st.markdown("**與會人待辦事項與期限**")

                    for item in rr.get("action_items", []):

                        st.markdown(f"- {item}")

                    st.markdown("**下次會議目標**")

                    for topic in rr.get("key_topics", []):

                        st.markdown(f"- {topic}")

                    if r.get("transcript"):

                        with st.expander(f"查看逐字稿 {r['id']}"):

                            st.write(r["transcript"])


if admin_mode and t4 is not None:

    with t4:

        data = db()

        requests = data.get("account_requests", [])

        st.subheader("帳號申請審核")

        if not requests:

            st.info("目前沒有待審核的帳號申請。")

        for request in sorted(requests, key=lambda item: item.get("created", 0)):

            created_at = dt.datetime.fromtimestamp(request.get("created", time.time())).strftime("%Y-%m-%d %H:%M")

            with st.expander(f"{request['id']} ｜ {request['name']} ｜ {request['email']}", expanded=True):

                st.markdown(f"**申請時間**：{created_at}")

                st.markdown(f"**姓名**：{request['name']}")

                st.markdown(f"**身分證字號**：{request['uid']}")

                st.markdown(f"**生日**：{request['birthday']}")

                st.markdown(f"**部門**：{request['dept']}")

                st.markdown(f"**Email**：{request['email']}")

                c_approve, c_reject = st.columns(2)

                with c_approve:

                    if st.button("通過申請", key=f"approve_{request['id']}", type="primary", use_container_width=True):

                        if approve_account_request(request["id"]):

                            st.success("帳號已建立，並已通知申請人。")

                            st.rerun()

                        else:

                            st.error("找不到此申請，請重新整理後再試。")

                with c_reject:

                    if st.button("退回申請", key=f"reject_{request['id']}", use_container_width=True):

                        if reject_account_request(request["id"]):

                            st.success("申請已退回，並已通知申請人。")

                            st.rerun()

                        else:

                            st.error("找不到此申請，請重新整理後再試。")
