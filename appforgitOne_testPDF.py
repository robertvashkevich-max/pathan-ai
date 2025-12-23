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
    
    # Airtable ключи
    airtable_token = st.secrets["airtable"]["API_TOKEN"]
    base_id = st.secrets["airtable"]["BASE_ID"]
    table_users_name = st.secrets["airtable"]["TABLE_USERS"]
    table_records_name = st.secrets["airtable"]["TABLE_RECORDS"]
    
    api = Api(airtable_token)
    users_table = api.table(base_id, table_users_name)
    records_table = api.table(base_id, table_records_name)
    
except Exception as e:
    st.error(f"⚠️ Ошибка настройки ключей: {e}. Проверьте Secrets в Streamlit Cloud.")
    st.stop()

# --- ФУНКЦИИ AIRTABLE ---

def login_user(name, password):
    # Ищем пользователя строго по имени
    formula = f"{{Name}}='{name}'"
    try:
        matches = users_table.all(formula=formula)
    except Exception as e:
        st.error(f"Ошибка соединения с базой: {e}")
        return None
    
    if matches:
        user_record = matches[0]
        stored_password = user_record['fields'].get('Password')
        if stored_password == password:
            return user_record
    return None

def register_user(name, password, email):
    # 1. Сначала проверяем, занято ли имя
    formula = f"{{Name}}='{name}'"
    matches = users_table.all(formula=formula)
    
    if matches:
        return False # Врач уже есть
    
    # 2. Если чисто — создаем
    users_table.create({
        "Name": name,
        "Password": password,
        "Email": email,
        "Role": "Doctor"
    })
    return True

def save_analysis(patient_data, analysis_full, summary, image_file, user_id):
    # Сохраняем данные в Airtable
    # Я добавил сюда сохранение Anamnesis!
    record_data = {
        "Patient Name": patient_data['p_name'],
        "Gender": patient_data['gender'],
        "Weight": patient_data['weight'],
        "Birth Date": str(patient_data['dob']),
        "Anamnesis": patient_data['anamnesis'], # <-- ВАЖНО: сохраняем анамнез
        "AI Conclusion": analysis_full,
        "Short Summary": summary,
        "Doctor": [user_id] # Связь с врачом
    }
    records_table.create(record_data)

def get_doctor_history(user_id):
    # Получаем историю только текущего врача
    all_records = records_table.all()
    my_records = []
    for r in all_records:
        if 'Doctor' in r['fields'] and user_id in r['fields']['Doctor']:
            my_records.append(r['fields'])
    # Сортировка: новые записи сверху (если есть дата создания)
    # В Airtable поле называется 'Created At', но API возвращает его как 'createdTime' на уровне метаданных
    # или как поле, если мы его явно запрашиваем. Для простоты просто реверсируем список.
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
    
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 8)
    pdf.cell(0, 10, 'Внимание: Результат создан ИИ. Требует проверки врачом.', ln=True, align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# --- МОДЕЛЬ AI ---
def get_model():
    try:
        return genai.GenerativeModel('gemini-1.5-flash')
    except:
        return genai.GenerativeModel('gemini-pro-vision')
model_ai = get_model()


# ==========================================
# ЛОГИКА ПРИЛОЖЕНИЯ
# ==========================================

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None

# --- ЭКРАН ВХОДА / РЕГИСТРАЦИИ ---
if st.session_state.user_id is None:
    st.title("🔐 Вход в PathanAI (Test Mode)")
    st.info("Тестовая версия с базой данных Airtable")
    
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    
    with tab1:
        with st.form("login_form"):
            login_name = st.text_input("Имя Фамилия")
            login_pass = st.text_input("Пароль", type="password")
            submit_login = st.form_submit_button("Войти")
            
            if submit_login:
                user = login_user(login_name, login_pass)
                if user:
                    st.success(f"Рады видеть вас, {user['fields'].get('Name')}!")
                    st.session_state.user_id = user['id']
                    st.session_state.user_name = user['fields'].get('Name')
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Ошибка входа. Проверьте имя и пароль.")

    with tab2:
        st.write("Создание учетной записи врача")
        with st.form("reg_form"):
            new_name = st.text_input("Ваше Имя и Фамилия (это будет ваш логин)")
            new_pass = st.text_input("Придумайте пароль", type="password")
            new_email = st.text_input("Email (для связи, необязательно)")
            submit_reg = st.form_submit_button("Зарегистрироваться")
            
            if submit_reg:
                if new_name and new_pass:
                    result = register_user(new_name, new_pass, new_email)
                    if result == True:
                        st.success("✅ Регистрация успешна! Теперь перейдите на вкладку 'Вход' и войдите.")
                    else:
                        st.error("⛔ Врач с таким именем уже зарегистрирован.")
                        st.warning("Пожалуйста, добавьте Отчество или цифру к имени.")
                else:
                    st.warning("Пожалуйста, заполните Имя и Пароль.")

# --- РАБОЧИЙ КАБИНЕТ ---
else:
    # Сайдбар
    with st.sidebar:
        st.markdown(f"### 👨‍⚕️ {st.session_state.user_name}")
        if st.button("Выйти из системы", type="secondary"):
            st.session_state.user_id = None
            st.session_state.user_name = None
            st.rerun()
        
        st.divider()
        st.header("🗂 История анализов")
        if st.button("🔄 Обновить список"):
            st.rerun()
            
        history = get_doctor_history(st.session_state.user_id)
        if history:
            for item in history:
                date_c = item.get('Created At', '')[:10]
                p_name = item.get('Patient Name', 'Без имени')
                summary = item.get('Short Summary', 'Нет данных')[:40]
                
                with st.expander(f"{date_c} | {p_name}"):
                    st.caption(f"**Резюме:** {summary}...")
                    st.info("Полный отчет в базе.")
        else:
            st.info("История пока пуста.")

    # Основная часть
    st.title("🔬 PathanAI: Рабочее место")
    
    with st.expander("📝 Карточка пациента", expanded=True):
        st.write("Заполните данные для отчета:")
        patient_name = st.text_input("ФИО Пациента / ID карты", placeholder="например: Иванов А.А. №4521")
        
        c1, c2, c3 = st.columns(3)
        gender = c1.selectbox("Пол", ["Мужской", "Женский"])
        weight = c2.number_input("Вес (кг)", 0.0, step=0.1)
        dob = c3.date_input("Дата рождения", datetime.date(1980, 1, 1))
        anamnesis = st.text_area("Анамнез и описание образца")
        
    st.markdown("---")
    uploaded_file = st.file_uploader("Загрузить гистологический снимок", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, width=400, caption="Предпросмотр")
        
        if st.button("🚀 Начать анализ и Сохранить", type="primary"):
            if not patient_name:
                st.warning("⚠️ Пожалуйста, введите ФИО пациента.")
            else:
                with st.spinner("Искусственный интеллект анализирует снимок..."):
                    prompt = f"""
                    Роль: Опытный патологоанатом.
                    Пациент: {patient_name}, Пол: {gender}, Вес: {weight}, Д.Р.: {dob}.
                    Анамнез: {anamnesis}.
                    Задача: Проанализируй гистологический снимок.
                    Структура ответа:
                    1. Микроскопическое описание.
                    2. Заключение.
                    3. ОЧЕНЬ КРАТКИЙ ВЫВОД (1-2 предложения для базы данных).
                    """
                    
                    try:
                        response = model_ai.generate_content([prompt, image])
                        text = response.text
                        
                        # Пытаемся вычленить краткий вывод
                        summary = "См. полный отчет"
                        if "ВЫВОД" in text:
                            summary = text.split("ВЫВОД")[-1].replace(":", "").strip()[:200]
                        elif "3." in text:
                             summary = text.split("3.")[-1][:200]
                        
                        st.success("✅ Готово!")
                        st.markdown("### Результат анализа")
                        st.write(text)
                        
                        # Сохраняем в Airtable (ТЕПЕРЬ С АНАМНЕЗОМ)
                        save_analysis(
                            {
                                "p_name": patient_name, 
                                "gender": gender, 
                                "weight": weight, 
                                "dob": dob,
                                "anamnesis": anamnesis # Добавил передачу анамнеза
                            }, 
                            text, 
                            summary, 
                            image, 
                            st.session_state.user_id
                        )
                        st.caption("💾 Результат автоматически сохранен в вашу базу Airtable.")
                        
                        # PDF
                        pdf_data = create_pdf(
                            {"p_name": patient_name, "gender": gender, "weight": weight, "dob": dob, "anamnesis": anamnesis}, 
                            text, 
                            image
                        )
                        st.download_button("📄 Скачать PDF отчет", pdf_data, f"Report_{patient_name}.pdf", "application/pdf")
                        
                    except Exception as e:
                        st.error(f"Произошла ошибка: {e}")
