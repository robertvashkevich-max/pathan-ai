import streamlit as st
import google.generativeai as genai
from PIL import Image
import datetime
from fpdf import FPDF
import tempfile

st.set_page_config(page_title="PathanAI", page_icon="🔬")

# --- БЕЗОПАСНОЕ ПОДКЛЮЧЕНИЕ КЛЮЧА ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("⚠️ Ключ API не найден! Настройте 'Secrets' в панели управления Streamlit Cloud.")
    st.stop()

genai.configure(api_key=api_key)

# --- ФУНКЦИЯ ГЕНЕРАЦИИ PDF ---
def create_pdf(patient_data, analysis_text, image_obj):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Подключаем русский шрифт
    try:
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pdf.set_font('DejaVu', '', 12)
    except:
        pdf.set_font("Arial", size=12)

    # 2. Заголовок
    pdf.set_font('DejaVu', '', 20)
    pdf.cell(0, 10, 'PathanAI: Медицинское заключение', ln=True, align='C')
    pdf.set_font('DejaVu', '', 10)
    pdf.cell(0, 10, 'Система поддержки принятия врачебных решений', ln=True, align='C')
    pdf.ln(5)

    # 3. Данные пациента
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('DejaVu', '', 12)
    
    pdf.cell(0, 10, 'ДАННЫЕ ПАЦИЕНТА:', ln=True, fill=True)
    text_data = (
        f"Пол: {patient_data['gender']} | Вес: {patient_data['weight']} кг | Д.Р.: {patient_data['dob']}\n"
        f"Курение: {patient_data['smoking']}\n"
        f"Биопсия: {patient_data['biopsy']} | Ткань: {patient_data['tissue']}\n"
        f"Анамнез: {patient_data['anamnesis']}"
    )
    pdf.multi_cell(0, 8, text_data)
    pdf.ln(5)

    # 4. Изображение
    if image_obj:
        try:
            if image_obj.mode == 'RGBA':
                image_obj = image_obj.convert('RGB')
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                image_obj.save(tmp.name)
                pdf.image(tmp.name, x=55, w=100) 
                pdf.ln(5)
        except Exception as e:
            pdf.set_font('DejaVu', '', 10)
            pdf.cell(0, 10, f'[Не удалось добавить изображение: {str(e)}]', ln=True)

    # 5. Результаты
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('DejaVu', '', 12)
    pdf.cell(0, 10, 'ЗАКЛЮЧЕНИЕ ИИ:', ln=True, fill=True)
    pdf.ln(2)
    
    clean_text = analysis_text.replace('**', '').replace('##', '').replace('* ', '- ')
    pdf.multi_cell(0, 6, clean_text)
    
    # 6. Подвал
    pdf.ln(10)
    pdf.set_font('DejaVu', '', 8)
    pdf.cell(0, 10, 'Дисклеймер: Данный отчет создан ИИ-прототипом PathanAI. Требует верификации врачом.', ln=True, align='C')

    return pdf.output(dest='S').encode('latin-1')

# --- ПОЛУЧЕНИЕ МОДЕЛИ ---
def get_model():
    valid_model = None
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for name in all_models:
            if 'flash' in name:
                valid_model = name
                break
        if not valid_model:
            for name in all_models:
                if 'pro' in name:
                    valid_model = name
                    break
        if not valid_model and all_models:
            valid_model = all_models[0]
    except:
        pass
    return valid_model

model_name = get_model()

# --- ИНТЕРФЕЙС ---
st.title("🔬 PathanAI")
st.header("Система поддержки принятия врачебных решений")
st.write("Разработано в целях улучшения результатов лечения пациентов с патологией, основанной на искусственном интеллекте")

# --- ШАГ 1: ДАННЫЕ ---
with st.expander("📝 Данные пациента", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        gender = st.selectbox("Пол", ["Не указан", "Мужской", "Женский"])
    with col2:
        weight = st.number_input("Вес (кг)", min_value=0.0, step=0.1, format="%.1f")
    with col3:
        dob = st.date_input("Дата рождения", min_value=datetime.date(1900, 1, 1), max_value=datetime.date.today(), value=datetime.date(1980, 1, 1))

    col4, col5 = st.columns(2)
    with col4:
        biopsy_method = st.selectbox("Метод биопсии:", ["Неизвестно", "Эксцизионная", "Пункция", "Мазок", "Операция"])
    with col5:
        smoking = st.selectbox("Курение:", ["Не курит", "Курит сейчас", "В прошлом", "Неизвестно"])

    tissue_type = st.selectbox("Тип ткани:", ["Неизвестно", "Кожа", "Слизистая", "Лимфоузел", "Молочная железа", "Печень", "Легкое", "Другое"])
    anamnesis = st.text_area("Анамнез:", placeholder="Жалобы...")

# --- ИСТОРИЯ ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "full_analysis" not in st.session_state:
    st.session_state.full_analysis = ""

# --- ШАГ 2: ФОТО ---
st.markdown("---")
uploaded_file = st.file_uploader("Загрузите снимок", type=["jpg", "png", "jpeg"])

if "last_file" not in st.session_state:
    st.session_state.last_file = None

if uploaded_file and uploaded_file.name != st.session_state.last_file:
    st.session_state.messages = []
    st.session_state.chat_session = None
    st.session_state.full_analysis = ""
    st.session_state.last_file = uploaded_file.name

# --- ЛОГИКА ---
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Образец", width=300)

    if not st.session_state.messages:
        if st.button("🚀 Начать анализ", type="primary"):
            if not model_name:
                st.error("Ошибка AI.")
            else:
                with st.spinner('Анализ...'):
                    initial_prompt = f"""
                    Ты эксперт-патологоанатом. Анализ снимка.
                    Пациент: {gender}, {weight}кг, д.р. {dob}, курение: {smoking}.
                    Ткань: {tissue_type}, Метод: {biopsy_method}.
                    Анамнез: {anamnesis}.
                    
                    Структура ответа:
                    1. Микроскопическое описание.
                    2. Патология.
                    3. Заключение.
                    4. ОЧЕНЬ КРАТКИЙ ВЫВОД.
                    """
                    try:
                        model = genai.GenerativeModel(model_name)
                        chat = model.start_chat(history=[])
                        response = chat.send_message([initial_prompt, image])
                        
                        st.session_state.chat_session = chat
                        st.session_state.full_analysis = response.text
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}")

    # ЧАТ
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- КНОПКА СКАЧИВАНИЯ PDF ---
    if st.session_state.full_analysis:
        st.markdown("---")
        p_data = {
            "gender": gender, "weight": weight, "dob": dob, "smoking": smoking,
            "biopsy": biopsy_method, "tissue": tissue_type, "anamnesis": anamnesis
        }
        
        pdf_bytes = create_pdf(p_data, st.session_state.full_analysis, image)
        
        st.download_button(
            label="📄 Скачать официальный отчет (PDF)",
            data=pdf_bytes,
            file_name=f"PathanAI_Report_{datetime.date.today()}.pdf",
            mime="application/pdf"
        )

    # ВВОД
    if prompt := st.chat_input("Вопрос по снимку..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        if st.session_state.chat_session:
            try:
                response = st.session_state.chat_session.send_message(prompt)
                with st.chat_message("assistant"):
                    st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Ошибка: {e}")
