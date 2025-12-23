import streamlit as st
import google.generativeai as genai
from PIL import Image
import datetime
from fpdf import FPDF
import tempfile
from pyairtable import Api
import time

# --- НАСТРОЙКА СТРАНИЦЫ ---
st.set_page_config(page_title="PathanAI Pro", page_icon="🔬", layout="wide")

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ (Для очистки формы) ---
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'analysis_pdf' not in st.session_state:
    st.session_state.analysis_pdf = None
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- ФУНКЦИЯ СБРОСА (ОЧИСТКИ) ---
def reset_analysis():
    # Очищаем результаты
    st.session_state.analysis_result = None
    st.session_state.analysis_pdf = None
    
    # Сбрасываем поля ввода через Session State
    st.session_state["w_p_name"] = ""
    st.session_state["w_weight"] = 0.0
    st.session_state["w_anamnesis"] = ""
    # Сбрасываем дату на дефолтную
    st.session_state["w_dob"] = datetime.date(1980, 1, 1)
    # Сбрасываем селекты на первый вариант (индекс 0)
    # (Streamlit сбрасывает selectbox, если удалить его ключ или перезагрузить, 
    # но надежнее просто обновить интерфейс)
    
    # Трюк для очистки загрузчика файлов (меняем ему ключ)
    st.session_state.uploader_key += 1

# --- ПОДКЛЮЧЕНИЕ КЛЮЧЕЙ ---
try:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_key)
    
    airtable_token = st.secrets["airtable"]["API_TOKEN"]
    base_id = st.secrets["airtable"]["BASE_ID"]
    table_users_name = st.secrets["airtable"]["TABLE_USERS"]
    table_records_name = st.secrets["airtable"]["TABLE_RECORDS"]
    
    api = Api(airtable_token)
    users_table = api.table(base_id, table_users_name)
    records_table = api.table(base_id, table_records_name)
    
except Exception as e:
    st.error(f"⚠️ Ошибка настройки ключей: {e}")
    st.stop()

# --- ФУНКЦИИ AIRTABLE ---

def login_user(name, password):
    formula = f"{{Name}}='{name}'"
    try:
        matches = users_table.all(formula=formula)
    except: return None
    if matches:
        user_record = matches[0]
        if user_record['fields'].get('Password') == password:
            return user_record
    return None

def register_user(name, password, email):
    formula = f"{{Name}}='{name}'"
    matches = users_table.all(formula=formula)
    if matches: return False
    users_table.create({"Name": name, "Password": password, "Email": email, "Role": "Doctor"})
    return True

def save_analysis(patient_data, analysis_full, summary, image_file, user_id):
    record_data = {
        "Patient Name": patient_data['p_name'],
        "Gender": patient_data['gender'],
        "Weight": patient_data['weight'],
        "Birth Date": str(patient_data['dob']),
        "Anamnesis": patient_data['anamnesis'],
        "Biopsy Method": patient_data['biopsy'],
        "AI Conclusion": analysis_full,
        "Short Summary": summary,
        "Doctor": [user_id]
    }
    records_table.create(record_data)

def get_history_debug(user_id, show_all=False):
    all_records = records_table.all()
    all_records.sort(key=lambda x: x['fields'].get('Created At', ''), reverse=True)
    filtered_records = []
    
    for r in all_records:
        fields = r['fields']
        is_my_record = False
        if 'Doctor' in fields and user_id in fields['Doctor']:
            is_my_record = True
        
        if show_all:
            fields['_debug_is_mine'] = is_my_record
            fields['_debug_doctor_field'] = fields.get('Doctor', 'ПУСТО')
            filtered_records.append(fields)
        elif is_my_record:
            filtered_records.append(fields)
            
    return filtered_records

def create_pdf(patient_data, analysis_text, image_obj):
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pdf.set_font('DejaVu', '', 12)
    except:
        pdf.set_font("Arial", size=12)

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
                pdf.image(tmp.name, x=55, w=100) 
        except: pass
    
    pdf.ln(5)
    pdf.cell(0, 10, 'ЗАКЛЮЧЕНИЕ ИИ:', ln=True, fill=True)
    pdf.ln(2)
    pdf.multi_cell(0, 6, analysis_text.replace('**', '').replace('* ', '- '))
    return pdf.output(dest='S').encode('latin-1')


# ==========================================
# ЛОГИКА ИНТЕРФЕЙСА
# ==========================================

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None

# --- ВХОД / РЕГИСТРАЦИЯ ---
if st.session_state.user_id is None:
    st.title("🔐 PathanAI: Вход")
    c1, c2 = st.columns([1, 2])
    with c1:
        tab1, tab2 = st.tabs(["Вход", "Регистрация"])
        with tab1:
            name = st.text_input("Имя Фамилия")
            pwd = st.text_input("Пароль", type="password")
            if st.button("Войти", use_container_width=True):
                u = login_user(name, pwd)
                if u:
                    st.session_state.user_id = u['id']
                    st.session_state.user_name = u['fields'].get('Name')
                    st.rerun()
                else: st.error("Ошибка входа")
        with tab2:
            n = st.text_input("Ваше Имя")
            p = st.text_input("Пароль", type="password")
            e = st.text_input("Email")
            if st.button("Создать аккаунт", use_container_width=True):
                if register_user(n, p, e): st.success("Готово! Войдите.")
                else: st.error("Имя занято")

# --- ГЛАВНОЕ ПРИЛОЖЕНИЕ ---
else:
    c_logo, c_user = st.columns([5, 2])
    with c_logo:
        st.title("🔬 PathanAI: Рабочее место")
    with c_user:
        st.write(f"👨‍⚕️ **{st.session_state.user_name}**")
        st.caption(f"ID: {st.session_state.user_id}")
        if st.button("Выйти"):
            st.session_state.user_id = None
            st.rerun()
    
    st.markdown("---")

    tab_new, tab_archive = st.tabs(["🧬 Новый анализ", "🗂 Архив пациентов"])

    # === ВКЛАДКА 1: НОВЫЙ АНАЛИЗ ===
    with tab_new:
        # Если анализ еще не проведен или мы нажали "Новый анализ", показываем форму
        with st.container(border=True):
            st.subheader("Данные пациента")
            # Добавили ключи (key=...) ко всем полям, чтобы уметь их очищать
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
            # Ключ загрузчика динамический, чтобы его можно было "пересоздать" для очистки
            upl = st.file_uploader("Загрузить гистологический снимок", type=["jpg", "png", "jpeg"], key=f"upl_{st.session_state.uploader_key}")
            
            if upl:
                img = Image.open(upl)
                st.image(img, width=400)
                
                # Кнопка Запуска
                if st.button("🚀 Запустить анализ", type="primary", use_container_width=True):
                    if not p_name: 
                        st.warning("Введите ФИО пациента!")
                    else:
                        with st.spinner("Анализ..."):
                            try:
                                model = genai.GenerativeModel('gemini-flash-latest')
                                prompt = f"Роль: Патологоанатом. Пациент: {p_name}, {gender}, {weight}, {dob}. Метод: {biopsy}. Анамнез: {anamnesis}. Опиши гистологию, дай заключение и КРАТКИЙ ВЫВОД."
                                
                                res = model.generate_content([prompt, img])
                                txt = res.text
                                summ = txt.split("ВЫВОД")[-1][:200] if "ВЫВОД" in txt else "См. полный отчет"
                                
                                p_data = {"p_name": p_name, "gender": gender, "weight": weight, "dob": dob, "anamnesis": anamnesis, "biopsy": biopsy}
                                
                                # Сохраняем результат в Session State, чтобы он не исчез
                                st.session_state.analysis_result = txt
