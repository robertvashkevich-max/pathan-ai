import streamlit as st
import google.generativeai as genai
from PIL import Image
import datetime
from fpdf import FPDF
import tempfile
from pyairtable import Api
import time
import requests
from io import BytesIO

# --- НАСТРОЙКА СТРАНИЦЫ ---
st.set_page_config(page_title="PathanAI Pro", page_icon="🔬", layout="wide")

# --- CSS: СКРЫВАЕМ ВСЕ ЛИШНЕЕ ---
st.markdown("""
    <style>
    .stException { display: none !important; }
    div[data-testid="stNotification"] { display: none !important; }
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    [data-testid="stDecoration"] {display:none;}
    [data-testid="stStatusWidget"] {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ ---
if 'analysis_result' not in st.session_state: st.session_state.analysis_result = None
if 'analysis_pdf' not in st.session_state: st.session_state.analysis_pdf = None
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'user_name' not in st.session_state: st.session_state.user_name = None

# --- ПОДКЛЮЧЕНИЕ КЛЮЧЕЙ ---
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    if "airtable" in st.secrets:
        api = Api(st.secrets["airtable"]["API_TOKEN"])
        base_id = st.secrets["airtable"]["BASE_ID"]
        users_table = api.table(base_id, st.secrets["airtable"]["TABLE_USERS"])
        records_table = api.table(base_id, st.secrets["airtable"]["TABLE_RECORDS"])
except Exception: pass

# --- ФУНКЦИИ БАЗЫ ДАННЫХ ---
def login_user(name, password):
    if not name or not password: return None
    try:
        matches = users_table.all(formula=f"{{Name}}='{name}'")
        if matches and matches[0]['fields'].get('Password') == password:
            return matches[0]
    except: return None
    return None

def get_user_by_id(record_id):
    # Восстановление пользователя по ID (для авто-входа)
    try:
        return users_table.get(record_id)
    except: return None

def register_user(name, password, email):
    try:
        if users_table.all(formula=f"{{Name}}='{name}'"): return False
        users_table.create({"Name": name, "Password": password, "Email": email, "Role": "Doctor"})
        return True
    except: return False

def save_analysis(patient_data, analysis_full, summary, image_file, user_id):
    try:
        records_table.create({
            "Patient Name": patient_data['p_name'],
            "Gender": patient_data['gender'],
            "Weight": patient_data['weight'],
            "Birth Date": str(patient_data['dob']),
            "Anamnesis": patient_data['anamnesis'],
            "Biopsy Method": patient_data['biopsy'],
            "AI Conclusion": analysis_full,
            "Short Summary": summary,
            "Doctor": [user_id]
        })
    except: pass

def get_all_history_records():
    try:
        all_records = records_table.all()
        all_records.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
        return [{'fields': r['fields'], 'record_id': r['id'], 'created_time': r.get('createdTime', '')} for r in all_records]
    except: return []

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def reset_analysis():
    st.session_state.analysis_result = None
    st.session_state.analysis_pdf = None
    st.session_state["w_p_name"] = ""
    st.session_state["w_weight"] = 0.0
    st.session_state["w_anamnesis"] = ""
    st.session_state["w_dob"] = datetime.date(1980, 1, 1)
    st.session_state.uploader_key += 1

def get_image_from_url(url):
    try: return Image.open(BytesIO(requests.get(url).content))
    except: return None

def create_pdf(patient_data, analysis_text, image_obj):
    pdf = FPDF()
    pdf.add_page()
    try: pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True); pdf.set_font('DejaVu', '', 12)
    except: pdf.set_font("Arial", size=12)
    
    pdf.set_font('DejaVu', '', 20)
    pdf.cell(0, 10, 'PathanAI: Медицинское заключение', ln=True, align='C')
    pdf.ln(5)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('DejaVu', '', 12)
    pdf.cell(0, 10, 'ДАННЫЕ:', ln=True, fill=True)
    text = f"Пациент: {patient_data['p_name']}\nПол: {patient_data['gender']} | Метод: {patient_data['biopsy']}\nВес: {patient_data['weight']} | Д.Р.: {patient_data['dob']}\nАнамнез: {patient_data['anamnesis']}"
    pdf.multi_cell(0, 8, text)
    pdf.ln(5)
    if image_obj:
        try:
            if image_obj.mode == 'RGBA': image_obj = image_obj.convert('RGB')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                image_obj.save(tmp.name)
                pdf.image(tmp.name, x=(210-100)/2, w=100)
        except: pass
    pdf.ln(5)
    pdf.cell(0, 10, 'ЗАКЛЮЧЕНИЕ:', ln=True, fill=True)
    pdf.ln(2)
    pdf.multi_cell(0, 6, analysis_text.replace('**', '').replace('##', '').replace('* ', '- '))
    return pdf.output(dest='S').encode('latin-1')

# --- АВТОМАТИЧЕСКИЙ ВХОД ПО URL (НОВОЕ!) ---
def try_auto_login():
    # Проверяем параметры URL
    query_params = st.query_params
    uid_in_url = query_params.get("uid", None)
    
    if st.session_state.user_id is None and uid_in_url:
        # Если есть ID в URL, пробуем найти пользователя в базе
        user_rec = get_user_by_id(uid_in_url)
        if user_rec:
            st.session_state.user_id = user_rec['id']
            st.session_state.user_name = user_rec['fields'].get('Name')
            # Перезагрузка не нужна, состояние обновилось

# Запускаем авто-вход при каждом обновлении страницы
try_auto_login()

# ==========================================
# ИНТЕРФЕЙС
# ==========================================

# --- ЭКРАН ВХОДА ---
if st.session_state.user_id is None:
    st.title("🔐 PathanAI: Вход")
    c1, c2 = st.columns([1, 2])
    with c1:
        tab1, tab2 = st.tabs(["Вход", "Регистрация"])
        with tab1:
            name = st.text_input("Имя Фамилия", key="login_name")
            pwd = st.text_input("Пароль", type="password", key="login_pass")
            if st.button("Войти", use_container_width=True):
                u = login_user(name, pwd)
                if u:
                    st.session_state.user_id = u['id']
                    st.session_state.user_name = u['fields'].get('Name')
                    # СОХРАНЯЕМ ID В URL БРАУЗЕРА
                    st.query_params["uid"] = u['id']
                    st.rerun()
                else: st.error("Ошибка входа")
        with tab2:
            n = st.text_input("Ваше Имя", key="reg_name")
            p = st.text_input("Придумайте Пароль", type="password", key="reg_pass")
            e = st.text_input("Email", key="reg_email")
            if st.button("Создать аккаунт", use_container_width=True):
                if register_user(n, p, e): st.success("Готово! Войдите.")
                else: st.error("Имя занято")

# --- ГЛАВНОЕ ПРИЛОЖЕНИЕ ---
else:
    c_logo, c_user = st.columns([5, 2])
    with c_logo: st.title("🔬 PathanAI: Рабочее место")
    with c_user:
        st.write(f"👨‍⚕️ **{st.session_state.user_name}**")
        if st.button("Выйти"):
            st.session_state.user_id = None
            # ОЧИЩАЕМ URL ПРИ ВЫХОДЕ
            st.query_params.clear()
            st.rerun()
    st.markdown("---")

    tab_new, tab_archive = st.tabs(["🧬 Новый анализ", "🗂 Архив пациентов"])

    # Вкладка 1
    with tab_new:
        with st.container(border=True):
            st.subheader("Данные пациента")
            p_name = st.text_input("ФИО Пациента", placeholder="Иванов И.И.", key="w_p_name")
            c1, c2, c3 = st.columns(3)
            gender = c1.selectbox("Пол", ["Мужской", "Женский"], key="w_gender")
            biopsy = c2.selectbox("Метод", ["Мазок", "Пункция", "Эксцизия", "Резекция"], key="w_biopsy")
            dob = c3.date_input("Дата рождения", datetime.date(1980,1,1), key="w_dob")
            c4, c5 = st.columns(2)
            weight = c4.number_input("Вес (кг)", 0.0, key="w_weight")
            anamnesis = st.text_area("Анамнез / Описание", height=100, key="w_anamnesis")

        st.write("")
        with st.container(border=True):
            st.subheader("Загрузка материала")
            upl = st.file_uploader("Загрузить снимок", type=["jpg", "png", "jpeg"], key=f"upl_{st.session_state.uploader_key}")
            if upl:
                img = Image.open(upl)
                st.image(img, width=400)
                if st.button("🚀 Запустить анализ", type="primary", use_container_width=True):
                    if not p_name: st.warning("Введите ФИО!")
                    else:
                        with st.spinner("Анализ..."):
                            try:
                                model = genai.GenerativeModel('gemini-flash-latest')
                                prompt = f"Роль: Патологоанатом. Пациент: {p_name}, {gender}, {weight}, {dob}. Метод: {biopsy}. Анамнез: {anamnesis}. Опиши гистологию, дай заключение и КРАТКИЙ ВЫВОД."
                                res = model.generate_content([prompt, img])
                                txt = res.text
                                summ = txt.split("ВЫВОД")[-1][:200] if "ВЫВОД" in txt else "См. отчет"
                                p_data = {"p_name": p_name, "gender": gender, "weight": weight, "dob": dob, "anamnesis": anamnesis, "biopsy": biopsy}
                                
                                st.session_state.analysis_result = txt
                                save_analysis(p_data, txt, summ, img, st.session_state.user_id)
                                st.session_state.analysis_pdf = create_pdf(p_data, txt, img)
                                st.success("Готово!"); st.rerun()
                            except Exception as e: st.error(f"Ошибка: {e}")

        if st.session_state.analysis_result:
            st.markdown("---"); st.subheader("📋 Результат")
            st.write(st.session_state.analysis_result)
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                if st.session_state.analysis_pdf:
                    st.download_button("📥 Скачать PDF", st.session_state.analysis_pdf, "report.pdf", "application/pdf", use_container_width=True)
            with c_d2: st.button("✨ Новый анализ", on_click=reset_analysis, use_container_width=True, type="secondary")

    # Вкладка 2
    with tab_archive:
        col_head, col_refresh = st.columns([4, 1])
        with col_head: st.subheader("🗂 Общая база")
        with col_refresh:
            if st.button("🔄 Обновить", use_container_width=True): st.rerun()
        history = get_all_history_records()
        if history:
            for item in history:
                rec_id = item.get('record_id')
                p_name_db = item.get('Patient Name', 'Без имени')
                date_created = item.get('Created At', '')[:10]
                summary = item.get('Short Summary', 'Нет данных')
                method = item.get('Biopsy Method', '-')
                icon = "👨" if item.get('Gender') == "Мужской" else "👩"
                
                with st.container(border=True):
                    c_h1, c_h2, c_h3 = st.columns([3, 2, 2])
                    with c_h1: st.markdown(f"**{icon} {p_name_db}**")
                    with c_h2: st.caption(f"📅 {date_created}")
                    with c_h3: st.caption(f"🔬 {method}")
                    st.divider(); st.write(summary)
                    with st.expander("📄 Полный текст"):
                        st.write(item.get('AI Conclusion', ''))
                        st.markdown("---")
                        if st.button("🖨️ Печать PDF", key=f"btn_{rec_id}", use_container_width=True):
                            with st.spinner("Создание PDF..."):
                                img_obj = None
                                if 'Image' in item and len(item['Image']) > 0:
                                    img_obj = get_image_from_url(item['Image'][0].get('url'))
                                pdf_bytes = create_pdf({
                                    'p_name': p_name_db, 'gender': item.get('Gender', '?'), 'weight': item.get('Weight', 0),
                                    'dob': item.get('Birth Date', '-'), 'anamnesis': item.get('Anamnesis', '-'), 'biopsy': method
                                }, item.get('AI Conclusion', ''), img_obj)
                                st.download_button("📥 Скачать файл", pdf_bytes, f"Report_{p_name_db}.pdf", "application/pdf", key=f"dl_{rec_id}")
        else: st.info("Архив пуст.")
