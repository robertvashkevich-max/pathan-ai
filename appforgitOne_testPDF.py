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
        "Doctor": [user_id] # ВАЖНО: Это поле должно быть типом Link to Users
    }
    records_table.create(record_data)

def get_history_debug(user_id, show_all=False):
    # Получаем вообще ВСЕ записи
    all_records = records_table.all()
    
    # Сортировка: новые сверху (обработка случаев без даты)
    all_records.sort(key=lambda x: x['fields'].get('Created At', ''), reverse=True)
    
    filtered_records = []
    
    for r in all_records:
        fields = r['fields']
        
        # Логика фильтрации
        is_my_record = False
        if 'Doctor' in fields:
            # Doctor возвращается как список ID ['rec...']
            if user_id in fields['Doctor']:
                is_my_record = True
        
        if show_all:
            # В режиме отладки добавляем метку, чей это файл
            fields['_debug_is_mine'] = is_my_record
            fields['_debug_doctor_field'] = fields.get('Doctor', 'ПУСТО')
            filtered_records.append(fields)
        elif is_my_record:
            # В обычном режиме только мои
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
    # Шапка
    c_logo, c_user = st.columns([5, 2])
    with c_logo:
        st.title("🔬 PathanAI: Рабочее место")
    with c_user:
        st.write(f"👨‍⚕️ **{st.session_state.user_name}**")
        st.caption(f"ID: {st.session_state.user_id}") # DEBUG INFO
        if st.button("Выйти"):
            st.session_state.user_id = None
            st.rerun()
    
    st.markdown("---")

    # ВКЛАДКИ
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

        st.write("")
        
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
                        with st.spinner("Анализ..."):
                            try:
                                model = genai.GenerativeModel('gemini-flash-latest')
                                prompt = f"Роль: Патологоанатом. Пациент: {p_name}, {gender}, {weight}, {dob}. Метод: {biopsy}. Анамнез: {anamnesis}. Опиши гистологию, дай заключение и КРАТКИЙ ВЫВОД."
                                
                                res = model.generate_content([prompt, img])
                                txt = res.text
                                summ = txt.split("ВЫВОД")[-1][:200] if "ВЫВОД" in txt else "См. полный отчет"
                                
                                st.success("Готово!")
                                st.write(txt)
                                
                                p_data = {"p_name": p_name, "gender": gender, "weight": weight, "dob": dob, "anamnesis": anamnesis, "biopsy": biopsy}
                                save_analysis(p_data, txt, summ, img, st.session_state.user_id)
                                
                                pdf = create_pdf(p_data, txt, img)
                                st.download_button("📥 Скачать PDF", pdf, f"report.pdf", "application/pdf")
                                
                            except Exception as e:
                                st.error(f"Ошибка: {e}")

    # === ВКЛАДКА 2: ИСТОРИЯ (АРХИВ) ===
    with tab_archive:
        c_head, c_check = st.columns([3, 2])
        with c_head:
            st.subheader("История анализов")
        with c_check:
            # ВОТ ЭТА ГАЛОЧКА ПОКАЖЕТ ПОТЕРЯННЫЕ ЗАПИСИ
            show_debug = st.checkbox("🕵️‍♂️ Показать ВСЕ записи (Debug)")
        
        if st.button("🔄 Обновить список"):
            st.rerun()
            
        # Загружаем историю (с флагом debug или без)
        history = get_history_debug(st.session_state.user_id, show_all=show_debug)
        
        if history:
            for item in history:
                p_name_db = item.get('Patient Name', 'Без имени')
                date_created = item.get('Created At', '')[:10]
                summary = item.get('Short Summary', 'Нет данных')
                method = item.get('Biopsy Method', '-')
                gen = item.get('Gender', '?')
                icon = "👨" if gen == "Мужской" else "👩"
                
                # Цвет границы: зеленый (мой) или красный (чужой/потерянный)
                border_color = "green"
                debug_info = ""
                
                if show_debug:
                    if item.get('_debug_is_mine'):
                        debug_info = "✅ МОЯ ЗАПИСЬ"
                    else:
                        debug_info = f"❌ ЧУЖАЯ ИЛИ БЕЗ ВРАЧА (Поле Doctor: {item.get('_debug_doctor_field')})"
                
                with st.container(border=True):
                    if show_debug: st.caption(debug_info)
                    
                    col_h1, col_h2, col_h3 = st.columns([3, 2, 2])
                    with col_h1: st.markdown(f"**{icon} {p_name_db}**")
                    with col_h2: st.caption(f"📅 {date_created}")
                    with col_h3: st.caption(f"🔬 {method}")
                    
                    st.divider()
                    st.write(summary)
        else:
            st.info("Архив пуст.")
            if not show_debug:
                st.caption("Попробуйте нажать галочку 'Показать ВСЕ записи', возможно ваши записи остались без привязки.")
