import streamlit as st
import google.generativeai as genai
from PIL import Image
import datetime

st.set_page_config(page_title="PathanAI", page_icon="🔬")

# --- БЕЗОПАСНОЕ ПОДКЛЮЧЕНИЕ КЛЮЧА ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("⚠️ Ключ API не найден! Настройте 'Secrets' в панели управления Streamlit Cloud.")
    st.stop()

# --- НАСТРОЙКА МОДЕЛИ ---
genai.configure(api_key=api_key)

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

# --- ИНТЕРФЕЙС (ЗАГОЛОВКИ ОБНОВЛЕНЫ) ---
st.title("🔬 PathanAI")
st.header("Система поддержки принятия врачебных решений")
st.write("Разработано в целях улучшения результатов лечения пациентов с патологией, основанной на искусственном интеллекте")

# --- ШАГ 1: ДАННЫЕ ПАЦИЕНТА ---
with st.expander("📝 Данные пациента (Нажмите, чтобы свернуть/развернуть)", expanded=True):
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
    anamnesis = st.text_area("Анамнез:", placeholder="Жалобы, динамика роста, особенности течения...")

# --- ИНИЦИАЛИЗАЦИЯ ИСТОРИИ ЧАТА ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None 

# --- ШАГ 2: ЗАГРУЗКА ФОТО ---
st.markdown("---")
uploaded_file = st.file_uploader("Загрузите снимок для начала анализа", type=["jpg", "png", "jpeg"])

if "last_file" not in st.session_state:
    st.session_state.last_file = None

if uploaded_file and uploaded_file.name != st.session_state.last_file:
    st.session_state.messages = []
    st.session_state.chat_session = None
    st.session_state.last_file = uploaded_file.name

# --- ОСНОВНАЯ ЛОГИКА ---
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Образец", width=300)

    # Если история пуста, показываем кнопку запуска
    if not st.session_state.messages:
        if st.button("🚀 Начать анализ", type="primary"):
            if not model_name:
                st.error("Ошибка подключения к AI.")
            else:
                with st.spinner('ИИ анализирует снимок...'):
                    initial_prompt = f"""
                    Ты эксперт-патологоанатом. Проанализируй этот снимок.
                    Данные пациента: Пол {gender}, Вес {weight}, Д.Р. {dob}, Курение: {smoking}.
                    Тип ткани: {tissue_type}, Метод: {biopsy_method}.
                    Анамнез: {anamnesis}.
                    
                    Структура твоего ответа должна быть такой:
                    1. Микроскопическое описание (подробно).
                    2. Патологические изменения.
                    3. Развернутое заключение.
                    4. ОЧЕНЬ КРАТКИЙ ВЫВОД (резюме в 1-2 предложениях, самая суть для быстрого чтения).
                    """
                    
                    try:
                        model = genai.GenerativeModel(model_name)
                        chat = model.start_chat(history=[])
                        response = chat.send_message([initial_prompt, image])
                        
                        st.session_state.chat_session = chat
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Ошибка: {e}")

    # --- ОТОБРАЖЕНИЕ ЧАТА ---
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- ПОЛЕ ВВОДА ---
    if prompt := st.chat_input("Задайте уточняющий вопрос по снимку..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        if st.session_state.chat_session:
            try:
                with st.spinner("Думаю..."):
                    response = st.session_state.chat_session.send_message(prompt)
                    with st.chat_message("assistant"):
                        st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Ошибка соединения: {e}")
        else:
            st.error("Сессия истекла. Перезагрузите страницу.")
