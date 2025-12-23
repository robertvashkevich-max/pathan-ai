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

# --- ФУНКЦИИ ---

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
    # Данные точно совпадают с Airtable
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

def get_doctor_history(user_id):
    all_records = records_table.all()
    my_records = []
    for r in all_records:
        if 'Doctor' in r['fields'] and user_id in r['fields']['Doctor']:
            my_records.append(r['fields'])
    # Сортировка по дате создания (новые сверху)
    my_records.sort(key=lambda x: x.get('Created At', ''), reverse=True)
    return my_records

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
    c1, c2 = st.columns([1, 2]) # Сделаем колонки для аккуратности
    
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
    # Шапка
    c_logo, c_user = st.columns([5, 1])
    with c_logo:
        st.title("🔬 PathanAI: Рабочее место")
    with c_user:
        st.write(f"👨‍⚕️ **{st.session_state.user_name}**")
        if st.button("Выйти"):
            st.session_state.user_id = None
            st.rerun()
    
    st.markdown("---")

    # ВКЛАДКИ (ГЛАВНОЕ ИЗМЕНЕНИЕ)
    tab_new, tab_archive = st.tabs(["🧬 Новый анализ", "🗂 Архив пациентов"])

    # === ВКЛАДКА 1: НОВЫЙ АНАЛИЗ ===
    with tab_new:
        with st.container(border=True):
            st.subheader("Данные пациента")
            p_name = st.text_input("ФИО Пациента", placeholder="Иванов И.И.")
            
            c1, c2, c3 = st.columns(3)
            gender = c1.selectbox("Пол", ["Мужской", "Женский"])
            biopsy = c2.selectbox("Метод", ["Мазок", "Пункция", "Эксцизия", "Резекция"])
            dob = c3.date_input("Дата рождения", datetime.date(1980,1,1))
            
            c4, c5 = st.columns(2)
            weight = c4.number_input("Вес (кг)", 0.0)
            anamnesis = st.text_area("Анамнез / Описание", height=100)

        st.write("") # Отступ
        
        with st.container(border=True):
            st.subheader("Загрузка материала")
            upl = st.file_uploader("Загрузить гистологический снимок", type=["jpg", "png", "jpeg"])
            
            if upl:
                img = Image.open(upl)
                st.image(img, width=400)
                
                if st.button("🚀 Запустить анализ", type="primary", use_container_width=True):
                    if not p_name: 
                        st.warning("Введите ФИО пациента!")
                    else:
                        with st.spinner("ИИ анализирует снимок..."):
                            try:
                                model = genai.GenerativeModel('gemini-flash-latest')
                                prompt = f"Роль: Патологоанатом. Пациент: {p_name}, {gender}, {weight}, {dob}. Метод: {biopsy}. Анамнез: {anamnesis}. Опиши гистологию, дай заключение и КРАТКИЙ ВЫВОД."
                                
                                res = model.generate_content([prompt, img])
                                txt = res.text
                                summ = txt.split("ВЫВОД")[-1][:200] if "ВЫВОД" in txt else "См. полный отчет"
                                
                                st.success("Анализ завершен!")
                                st.markdown("### Результат")
                                st.write(txt)
                                
                                p_data = {"p_name": p_name, "gender": gender, "weight": weight, "dob": dob, "anamnesis": anamnesis, "biopsy": biopsy}
                                save_analysis(p_data, txt, summ, img, st.session_state.user_id)
                                
                                pdf = create_pdf(p_data, txt, img)
                                st.download_button("📥 Скачать PDF отчет", pdf, f"report_{p_name}.pdf", "application/pdf", use_container_width=True)
                                
                            except Exception as e:
                                st.error(f"Ошибка: {e}")

    # === ВКЛАДКА 2: ИСТОРИЯ (АРХИВ) ===
    with tab_archive:
        st.subheader("История анализов")
        
        # Поиск
        search_query = st.text_input("🔍 Поиск по ФИО...", placeholder="Начните вводить фамилию").lower()
        
        if st.button("🔄 Обновить список"):
            st.rerun()
            
        history = get_doctor_history(st.session_state.user_id)
        
        if history:
            count = 0
            for item in history:
                # Фильтрация поиска
                p_name_db = item.get('Patient Name', 'Без имени')
                if search_query and search_query not in p_name_db.lower():
                    continue
                
                count += 1
                
                # Данные для отобра
