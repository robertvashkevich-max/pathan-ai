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

# --- СЛОВАРЬ ПЕРЕВОДОВ ---
TR = {
    "login_title": {"RU": "🔐 PathanAI: Вход", "EN": "🔐 PathanAI: Login"},
    "tab_login": {"RU": "Вход", "EN": "Login"},
    "tab_register": {"RU": "Регистрация", "EN": "Register"},
    "lbl_name": {"RU": "Имя Фамилия", "EN": "Full Name"},
    "lbl_pass": {"RU": "Пароль", "EN": "Password"},
    "btn_login": {"RU": "Войти", "EN": "Sign In"},
    "err_login": {"RU": "Ошибка входа", "EN": "Login failed"},
    "lbl_your_name": {"RU": "Ваше Имя", "EN": "Your Name"},
    "lbl_create_pass": {"RU": "Придумайте Пароль", "EN": "Create Password"},
    "lbl_email": {"RU": "Email", "EN": "Email"},
    "btn_register": {"RU": "Создать аккаунт", "EN": "Create Account"},
    "success_reg": {"RU": "Готово! Войдите.", "EN": "Success! Please login."},
    "err_name_taken": {"RU": "Имя занято", "EN": "Name already taken"},
    
    "app_title": {"RU": "🔬 PathanAI: Рабочее место", "EN": "🔬 PathanAI: Workspace"},
    "btn_logout": {"RU": "Выйти", "EN": "Logout"},
    
    "tab_new_analysis": {"RU": "🧬 Новый анализ", "EN": "🧬 New Analysis"},
    "tab_archive": {"RU": "🗂 Общая база", "EN": "🗂 Patient Database"},
    
    "sec_patient": {"RU": "Данные пациента", "EN": "Patient Data"},
    "in_p_name": {"RU": "ФИО Пациента", "EN": "Patient Name"},
    "ph_p_name": {"RU": "Иванов И.И.", "EN": "John Doe"},
    "in_gender": {"RU": "Пол", "EN": "Gender"},
    "opt_male": {"RU": "Мужской", "EN": "Male"},
    "opt_female": {"RU": "Женский", "EN": "Female"},
    "in_method": {"RU": "Метод", "EN": "Method"},
    "in_dob": {"RU": "Дата рождения", "EN": "Date of Birth"},
    "in_weight": {"RU": "Вес (кг)", "EN": "Weight (kg)"},
    "in_anamnesis": {"RU": "Анамнез / Описание", "EN": "Anamnesis / Description"},
    
    "sec_upload": {"RU": "Загрузка материала", "EN": "Upload Image"},
    "upl_label": {"RU": "Загрузить снимок", "EN": "Upload histology image"},
    "btn_run": {"RU": "🚀 Запустить анализ", "EN": "🚀 Run Analysis"},
    "warn_name": {"RU": "Введите ФИО!", "EN": "Enter Patient Name!"},
    "spinner": {"RU": "Анализ...", "EN": "Analyzing..."},
    "success_save": {"RU": "Готово! Результат сохранен.", "EN": "Done! Result saved."},
    "err_api": {"RU": "Ошибка", "EN": "Error"},
    
    "res_title": {"RU": "📋 Результат анализа", "EN": "📋 Analysis Result"},
    "btn_download": {"RU": "📥 Скачать PDF отчет", "EN": "📥 Download PDF Report"},
    "btn_reset": {"RU": "✨ Новый анализ", "EN": "✨ New Analysis"},
    
    "arch_title": {"RU": "🗂 Общая база пациентов", "EN": "🗂 All Patient Records"},
    "btn_refresh": {"RU": "🔄 Обновить", "EN": "🔄 Refresh"},
    "arch_empty": {"RU": "Архив пуст.", "EN": "Database is empty."},
    "exp_full": {"RU": "📄 Полный текст", "EN": "📄 Full Report"},
    "btn_print": {"RU": "🖨️ Печать PDF", "EN": "🖨️ Print PDF"},
    
    "pdf_title": {"RU": "PathanAI: Медицинское заключение", "EN": "PathanAI: Medical Report"},
    "pdf_data": {"RU": "ДАННЫЕ:", "EN": "PATIENT DATA:"},
    "pdf_concl": {"RU": "ЗАКЛЮЧЕНИЕ:", "EN": "CONCLUSION:"},
    "pdf_pat": {"RU": "Пациент", "EN": "Patient"},
    "pdf_gen": {"RU": "Пол", "EN": "Gender"},
    "pdf_meth": {"RU": "Метод", "EN": "Method"},
    "pdf_w": {"RU": "Вес", "EN": "Weight"},
    "pdf_dob": {"RU": "Д.Р.", "EN": "DOB"},
    "pdf_anam": {"RU": "Анамнез", "EN": "History"}
}

# --- CSS: СКРЫВАЕМ ЛИШНЕЕ ---
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
if 'language' not in st.session_state: st.session_state.language = 'RU'
if 'analysis_result' not in st.session_state: st.session_state.analysis_result = None
if 'analysis_pdf' not in st.session_state: st.session_state.analysis_pdf = None
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'user_name' not in st.session_state: st.session_state.user_name = None

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ БАЗЫ ---
api = None
users_table = None
records_table = None

# Функция переключения языка
def toggle_language():
    if st.session_state.language == 'RU':
        st.session_state.language = 'EN'
    else:
        st.session_state.language = 'RU'

def t(key):
    return TR[key][st.session_state.language]

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
    if not name or not password or not users_table: return None
    try:
        matches = users_table.all(formula=f"{{Name}}='{name}'")
        if matches and matches[0]['fields'].get('Password') == password:
            return matches[0]
    except: return None
    return None

def get_user_by_id(record_id):
    if not users_table: return None
    try: return users_table.get(record_id)
    except: return None

def register_user(name, password, email):
    if not users_table: return False
    try:
        if users_table.all(formula=f"{{Name}}='{name}'"): return False
        users_table.create({"Name": name, "Password": password, "Email": email, "Role": "Doctor"})
        return True
    except: return False

def save_analysis(patient_data, analysis_full, summary, image_file, user_id):
    if not records_table: return
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
    # Эта функция исправлена для надежной загрузки
    if not records_table: return []
    try:
        all_records = records_table.all()
        
        # Безопасная сортировка
        # Используем системное время createdTime, если оно есть, иначе пустую строку
        # чтобы sort не падал с ошибкой
        all_records.sort(key=lambda x: x.get('createdTime', ''), reverse=True)
        
        processed = []
        for r in all_records:
            fields = r.get('fields', {})
            fields['record_id'] = r.get('id')
            fields['created_time'] = r.get('createdTime', '')
            processed.append(fields)
            
        return processed
    except:
        return []

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

def create_pdf(patient_data, analysis_text, image_obj, lang_code):
    def pdf_t(k): return TR[k][lang_code]
    pdf = FPDF()
    pdf.add_page()
    try: pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True); pdf.set_font('DejaVu', '', 12)
    except: pdf.set_font("Arial", size=12)
    
    pdf.set_font('DejaVu', '', 20)
    pdf.cell(0, 10, pdf_t("pdf_title"), ln=True, align='C')
    pdf.ln(5)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('DejaVu', '', 12)
    pdf.cell(0, 10, pdf_t("pdf_data"), ln=True, fill=True)
    
    text = f"{pdf_t('pdf_pat')}: {patient_data['p_name']}\n{pdf_t('pdf_gen')}: {patient_data['gender']} | {pdf_t('pdf_meth')}: {patient_data['biopsy']}\n{pdf_t('pdf_w')}: {patient_data['weight']} | {pdf_t('pdf_dob')}: {patient_data['dob']}\n{pdf_t('pdf_anam')}: {patient_data['anamnesis']}"
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
    pdf.cell(0, 10, pdf_t("pdf_concl"), ln=True, fill=True)
    pdf.ln(2)
    pdf.multi_cell(0, 6, analysis_text.replace('**', '').replace('##', '').replace('* ', '- '))
    return pdf.output(dest='S').encode('latin-1')

def try_auto_login():
    query_params = st.query_params
    uid_in_url = query_params.get("uid", None)
    if st.session_state.user_id is None and uid_in_url:
        user_rec = get_user_by_id(uid_in_url)
        if user_rec:
            st.session_state.user_id = user_rec['id']
            st.session_state.user_name = user_rec['fields'].get('Name')

try_auto_login()

# ==========================================
# ИНТЕРФЕЙС
# ==========================================

if st.session_state.user_id is None:
    col_t1, col_t2 = st.columns([5, 1])
    with col_t1: st.title(t("login_title"))
    with col_t2: 
        if st.button("🇬🇧/🇷🇺", key="lang_login"): toggle_language(); st.rerun()

    c1, c2 = st.columns([1, 2])
    with c1:
        tab1, tab2 = st.tabs([t("tab_login"), t("tab_register")])
        with tab1:
            name = st.text_input(t("lbl_name"), key="login_name")
            pwd = st.text_input(t("lbl_pass"), type="password", key="login_pass")
            if st.button(t("btn_login"), use_container_width=True):
                u = login_user(name, pwd)
                if u:
                    st.session_state.user_id = u['id']
                    st.session_state.user_name = u['fields'].get('Name')
                    st.query_params["uid"] = u['id']
                    st.rerun()
                else: st.error(t("err_login"))
        with tab2:
            n = st.text_input(t("lbl_your_name"), key="reg_name")
            p = st.text_input(t("lbl_create_pass"), type="password", key="reg_pass")
            e = st.text_input(t("lbl_email"), key="reg_email")
            if st.button(t("btn_register"), use_container_width=True):
                if register_user(n, p, e): st.success(t("success_reg"))
                else: st.error(t("err_name_taken"))

else:
    c_logo, c_user, c_lang = st.columns([5, 2, 1])
    with c_logo: st.title(t("app_title"))
    with c_user:
        st.write(f"👨‍⚕️ **{st.session_state.user_name}**")
        if st.button(t("btn_logout")):
            st.session_state.user_id = None
            st.query_params.clear()
            st.rerun()
    with c_lang:
        if st.button("🇬🇧/🇷🇺", key="lang_main"): toggle_language(); st.rerun()

    st.markdown("---")

    tab_new, tab_archive = st.tabs([t("tab_new_analysis"), t("tab_archive")])

    # Вкладка 1: Новый анализ
    with tab_new:
        with st.container(border=True):
            st.subheader(t("sec_patient"))
            p_name = st.text_input(t("in_p_name"), placeholder=t("ph_p_name"), key="w_p_name")
            c1, c2, c3 = st.columns(3)
            gender = c1.selectbox(t("in_gender"), [t("opt_male"), t("opt_female")], key="w_gender")
            biopsy = c2.selectbox(t("in_method"), ["Мазок", "Пункция", "Эксцизия", "Резекция"], key="w_biopsy")
            dob = c3.date_input(t("in_dob"), datetime.date(1980,1,1), key="w_dob")
            c4, c5 = st.columns(2)
            weight = c4.number_input(t("in_weight"), 0.0, key="w_weight")
            anamnesis = st.text_area(t("in_anamnesis"), height=100, key="w_anamnesis")

        st.write("")
        with st.container(border=True):
            st.subheader(t("sec_upload"))
            upl = st.file_uploader(t("upl_label"), type=["jpg", "png", "jpeg"], key=f"upl_{st.session_state.uploader_key}")
            if upl:
                img = Image.open(upl)
                st.image(img, width=400)
                if st.button(t("btn_run"), type="primary", use_container_width=True):
                    if not p_name: st.warning(t("warn_name"))
                    else:
                        with st.spinner(t("spinner")):
                            try:
                                model = genai.GenerativeModel('gemini-flash-latest')
                                if st.session_state.language == 'RU':
                                    prompt = f"Роль
