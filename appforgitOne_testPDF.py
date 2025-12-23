import streamlit as st
import google.generativeai as genai
from PIL import Image
import datetime
from fpdf import FPDF
import tempfile
from pyairtable import Api
import time

# --- НАСТРОЙКА СТРАНИЦЫ ---
st.set_page_config(page_title="PathanAI 2.0", page_icon="🔬")

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
    st.error(f"⚠️ Ошибка настройки ключей: {e}")
    st.stop()

# --- ФУНКЦИИ AIRTABLE ---

def login_user(name, password):
    formula = f"{{Name}}='{name}'"
    try:
        matches = users_table.all(formula=formula)
    except:
        return None
    
    if matches:
        user_record = matches[0]
        if user_record['fields'].get('Password') == password:
            return user_record
    return None

def register_user(name, password, email):
    formula = f"{{Name}}='{name}'"
    matches = users_table.all(formula=formula)
    if matches:
        return False
    
    users_table.create({
        "Name": name, "Password": password, "Email": email, "Role": "Doctor"
    })
    return True

def save_analysis(patient_data, analysis_full, summary, image_file, user_id):
    # Сохраняем в Airtable
    records_table.create({
        "Patient Name": patient_data['p_name'],
        "Gender": patient_data['gender'],
        "Weight": patient_data['weight'],
        "Birth Date": str(patient_data['dob']),
        "Anamnesis": patient_data['anamnesis'],
        "AI Conclusion": analysis_full,
        "Short Summary": summary,
        "Doctor": [user_id]
    })

def get_doctor_history(user_id):
    # История только текущего врача
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
    text = f"Пациент: {patient_data['p_name']}\nПол: {patient_data['gender']} | Вес: {patient_data['weight']}\nАнамнез: {patient_data['anamnesis']}"
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
    pdf.cell(0, 10, 'ЗАКЛЮЧЕНИЕ ИИ (Gemini 2.0):', ln=True, fill=True)
    pdf.ln(2)
    pdf.multi_cell(0, 6, analysis_text.replace('**', '').replace('* ', '- '))
    return pdf.output(dest='S').encode('latin-1')


# ==========================================
# ЛОГИКА ПРИЛОЖЕНИЯ
# ==========================================

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None

# --- ЭКРАН ВХОДА ---
if st.session_state.user_id is None:
    st.title("🔐 PathanAI: Вход")
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    
    with tab1:
        name = st.text_input("Имя Фамилия")
        pwd = st.text_input("Пароль", type="password")
        if st.button("Войти"):
            u = login_user(name, pwd)
            if u:
                st.session_state.user_id = u['id']
                st.session_state.user_name = u['fields'].get('Name')
                st.rerun()
            else: st.error("Неверное имя или пароль")
            
    with tab2:
        n = st.text_input("Ваше Имя")
        p = st.text_input("Придумайте Пароль", type="password")
        e = st.text_input("Email")
        if st.button("Зарегистрироваться"):
            if register_user(n, p, e): st.success("Успешно! Теперь войдите.")
            else: st.error("Такое имя уже занято.")

# --- РАБОЧИЙ КАБИНЕТ ---
else:
    with st.sidebar:
        st.write(f"👨‍⚕️ Врач: **{st.session_state.user_name}**")
        if st.button("Выйти"):
            st.session_state.user_id = None
            st.rerun()
        
        st.divider()
        st.caption("История анализов")
        if st.button("Обновить"): st.rerun()
        
        hist = get_doctor_history(st.session_state.user_id)
        if hist:
            for h in hist:
                d = h.get('Created At', '')[:10]
                pat = h.get('Patient Name', '?')
                with st.expander(f"{d} | {pat}"):
                    st.write(h.get('Short Summary'))
        else:
            st.info("Пусто")

    # ОСНОВНОЙ ЭКРАН
    st.title("🔬 PathanAI: Анализ")
    
    with st.expander("📝 Карточка пациента", expanded=True):
        p_name = st.text_input("ФИО Пациента")
        c1, c2, c3 = st.columns(3)
        gender = c1.selectbox("Пол", ["М", "Ж"])
        weight = c2.number_input("Вес", 0.0)
        dob = c3.date_input("Дата рождения", datetime.date(1980,1,1))
        anamnesis = st.text_area("Анамнез")
        
    upl = st.file_uploader("Загрузить снимок", type=["jpg", "png", "jpeg"])
    
    if upl:
        img = Image.open(upl)
        st.image(img, width=400)
        
        if st.button("🚀 Начать анализ", type="primary"):
            if not p_name: 
                st.warning("Введите имя пациента!")
            else:
                with st.spinner("Gemini 2.0 анализирует..."):
                    try:
                        # ТУТ МЫ ИСПОЛЬЗУЕМ ВАШУ МОДЕЛЬ ИЗ СПИСКА
                        model = genai.GenerativeModel('gemini-2.0-flash-exp')
                        
                        prompt = f"Роль: Патологоанатом. Пациент: {p_name}, {gender}, {weight}, {dob}. Анамнез: {anamnesis}. Опиши гистологию, дай заключение и КРАТКИЙ ВЫВОД."
                        
                        res = model.generate_content([prompt, img])
                        txt = res.text
                        
                        # Вывод
                        summ = txt.split("ВЫВОД")[-1][:200] if "ВЫВОД" in txt else "См. полный отчет"
                        st.markdown("### Результат")
                        st.write(txt)
                        
                        # Сохранение
                        save_analysis({"p_name": p_name, "gender": gender, "weight": weight, "dob": dob, "anamnesis": anamnesis}, txt, summ, img, st.session_state.user_id)
                        
                        # PDF
                        pdf = create_pdf({"p_name": p_name, "gender": gender, "weight": weight, "dob": dob, "anamnesis": anamnesis}, txt, img)
                        st.download_button("Скачать PDF", pdf, "report.pdf", "application/pdf")
                        
                        st.success("✅ Анализ сохранен в базу!")
                        
                    except Exception as e:
                        st.error(f"Ошибка API: {e}")
