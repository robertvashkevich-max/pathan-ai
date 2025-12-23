import streamlit as st
import google.generativeai as genai
from PIL import Image
import datetime
from fpdf import FPDF
import tempfile
from pyairtable import Api
import time

# --- НАСТРОЙКА СТРАНИЦЫ ---
st.set_page_config(page_title="PathanAI Test", page_icon="🧪")

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
    st.error(f"⚠️ Ошибка настройки ключей: {e}. Проверьте Secrets.")
    st.stop()

# --- ФУНКЦИИ AIRTABLE ---

def login_user(name, password):
    formula = f"{{Name}}='{name}'"
    try:
        matches = users_table.all(formula=formula)
    except Exception as e:
        return None
    
    if matches:
        user_record = matches[0]
        stored_password = user_record['fields'].get('Password')
        if stored_password == password:
            return user_record
    return None

def register_user(name, password, email):
    formula = f"{{Name}}='{name}'"
    matches = users_table.all(formula=formula)
    if matches:
        return False
    
    users_table.create({
        "Name": name,
        "Password": password,
        "Email": email,
        "Role": "Doctor"
    })
    return True

def save_analysis(patient_data, analysis_full, summary, image_file, user_id):
    record_data = {
        "Patient Name": patient_data['p_name'],
        "Gender": patient_data['gender'],
        "Weight": patient_data['weight'],
        "Birth Date": str(patient_data['dob']),
        "Anamnesis": patient_data['anamnesis'],
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
    my_records.reverse() 
    return my_records

# --- ФУНКЦИЯ PDF ---
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
    text_data = f"Пациент: {patient_data['p_name']}\nПол: {patient_data['gender']} | Вес: {patient_data['weight']} | Д.Р.: {patient_data['dob']}\nАнамнез: {patient_data['anamnesis']}"
    pdf.multi_cell(0, 8, text_data)
    pdf.ln(5)

    if image_obj:
        try:
            if image_obj.mode == 'RGBA': image_obj = image_obj.convert('RGB')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                image_obj.save(tmp.name)
                pdf.image(tmp.name, x=55, w=100) 
                pdf.ln(5)
        except: pass

    pdf.cell(0, 10, 'ЗАКЛЮЧЕНИЕ ИИ:', ln=True, fill=True)
    pdf.ln(2)
    clean_text = analysis_text.replace('**', '').replace('##', '').replace('* ', '- ')
    pdf.multi_cell(0, 6, clean_text)
    
    return pdf.output(dest='S').encode('latin-1')

# --- УМНАЯ ФУНКЦИЯ ГЕНЕРАЦИИ (С ЗАПАСНЫМ ПЛАНОМ) ---
def generate_content_safe(prompt, image):
    # Список моделей от быстрой к мощной
    models_to_try = ['gemini-1.5-flash-latest', 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro-vision']
    
    last_error = None
    
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([prompt, image])
            return response.text # Если сработало — возвращаем текст и выходим
        except Exception as e:
            last_error = e
            continue # Если ошибка — пробуем следующую модель в списке
            
    # Если ничего не сработало, выбрасываем ошибку
    raise last_error

# ==========================================
# ЛОГИКА ПРИЛОЖЕНИЯ
# ==========================================

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None

# --- ЭКРАН ВХОДА ---
if st.session_state.user_id is None:
    st.title("🔐 Вход в PathanAI (Test)")
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    
    with tab1:
        with st.form("login_form"):
            login_name = st.text_input("Имя Фамилия")
            login_pass = st.text_input("Пароль", type="password")
            submit_login = st.form_submit_button("Войти")
            
            if submit_login:
                user = login_user(login_name, login_pass)
                if user:
                    st.success(f"Привет, {user['fields'].get('Name')}!")
                    st.session_state.user_id = user['id']
                    st.session_state.user_name = user['fields'].get('Name')
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Ошибка входа.")

    with tab2:
        st.write("Регистрация")
        with st.form("reg_form"):
            new_name = st.text_input("Имя Фамилия")
            new_pass = st.text_input("Пароль", type="password")
            new_email = st.text_input("Email")
            submit_reg = st.form_submit_button("Зарегистрироваться")
            
            if submit_reg:
                if new_name and new_pass:
                    if register_user(new_name, new_pass, new_email):
                        st.success("Успешно! Войдите.")
                    else:
                        st.error("Такой врач уже есть.")
                else:
                    st.warning("Введите данные.")

# --- РАБОЧИЙ КАБИНЕТ ---
else:
    with st.sidebar:
        st.write(f"Врач: {st.session_state.user_name}")
        if st.button("Выйти"):
            st.session_state.user_id = None
            st.rerun()
        
        st.divider()
        if st.button("Обновить историю"): st.rerun()
        history = get_doctor_history(st.session_state.user_id)
        if history:
            for item in history:
                d = item.get('Created At', '')[:10]
                n = item.get('Patient Name', '?')
                with st.expander(f"{d} | {n}"):
                    st.write(item.get('Short Summary'))
        else:
            st.info("История пуста")

    st.title("🔬 PathanAI: Анализ")
    
    with st.expander("📝 Карточка пациента", expanded=True):
        patient_name = st.text_input("ФИО Пациента")
        c1, c2, c3 = st.columns(3)
        gender = c1.selectbox("Пол", ["М", "Ж"])
        weight = c2.number_input("Вес", 0.0)
        dob = c3.date_input("Д.Р.", datetime.date(1980, 1, 1))
        anamnesis = st.text_area("Анамнез")
        
    uploaded_file = st.file_uploader("Загрузить снимок", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, width=300)
        
        if st.button("🚀 Начать анализ", type="primary"):
            if not patient_name:
                st.warning("Введите имя пациента!")
            else:
                with st.spinner("Думаю... (Пробую разные модели)"):
                    prompt = f"Патологоанатом. Пациент: {patient_name}, {gender}, {weight}, {dob}. Анамнез: {anamnesis}. Опиши снимок, дай заключение и КРАТКИЙ ВЫВОД."
                    
                    try:
                        # ТЕПЕРЬ ИСПОЛЬЗУЕМ УМНУЮ ФУНКЦИЮ
                        text = generate_content_safe(prompt, image)
                        
                        # Обработка ответа
                        summary = "См. полный отчет"
                        if "ВЫВОД" in text: summary = text.split("ВЫВОД")[-1][:200]
                        
                        st.markdown("### Результат")
                        st.write(text)
                        
                        save_analysis(
                            {"p_name": patient_name, "gender": gender, "weight": weight, "dob": dob, "anamnesis": anamnesis}, 
                            text, summary, image, st.session_state.user_id
                        )
                        st.success("✅ Сохранено в базу!")
                        
                        pdf_data = create_pdf({"p_name": patient_name, "gender": gender, "weight": weight, "dob": dob, "anamnesis": anamnesis}, text, image)
                        st.download_button("Скачать PDF", pdf_data, "report.pdf", "application/pdf")
                        
                    except Exception as e:
                        st.error(f"Не удалось получить ответ ни от одной модели. Ошибка: {e}")
