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

# Функция для получения рабочей модели
def get_model():
    valid_model = None
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Приоритет: Flash -> Pro -> Любая
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
st.title("🔬 PathanAI: Чат")
st.markdown("Система поддержки принятия врачебных решений с возможностью диалога.")

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
    st.session_state.chat_session = None # Здесь будем хранить объект чата Google

# --- ШАГ 2: ЗАГРУЗКА ФОТО ---
uploaded_file = st.file_uploader("Загрузите снимок для начала чата", type=["jpg", "png", "jpeg"])

# Логика сброса чата при смене файла
if "last_file" not in st.session_state:
    st.session_state.last_file = None

if uploaded_file and uploaded_file.name != st.session_state.last_file:
    # Если загрузили новый файл - чистим историю
    st.session_state.messages = []
    st.session_state.chat_session = None
    st.session_state.last_file = uploaded_file.name

# --- ОСНОВНАЯ ЛОГИКА ---
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Образец", width=300) # Делаем картинку поменьше, чтобы не мешала чату

    # Если история пуста, показываем кнопку "Начать анализ"
    if not st.session_state.messages:
        if st.button("🚀 Начать анализ", type="primary"):
            if not model_name:
                st.error("Ошибка подключения к AI.")
            else:
                with st.spinner('ИИ анализирует снимок...'):
                    # 1. Формируем первый системный промпт
                    initial_prompt = f"""
                    Ты эксперт-патологоанатом. Проанализируй этот снимок.
                    Данные пациента: Пол {gender}, Вес {weight}, Д.Р. {dob}, Курение: {smoking}.
                    Тип ткани: {tissue_type}, Метод: {biopsy_method}.
                    Анамнез: {anamnesis}.
                    
                    Дай подробное описание: микроскопия, патология, заключение.
                    Будь готов отвечать на уточняющие вопросы врача.
                    """
                    
                    try:
                        # Запускаем чат-сессию. Важно: передаем историю (сначала пустую)
                        model = genai.GenerativeModel(model_name)
                        chat = model.start_chat(history=[])
                        
                        # Отправляем первое сообщение С КАРТИНКОЙ
                        response = chat.send_message([initial_prompt, image])
                        
                        # Сохраняем сессию и сообщение в память
                        st.session_state.chat_session = chat
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        
                        # Перезагружаем страницу, чтобы отобразить чат
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Ошибка: {e}")

    # --- ОТОБРАЖЕНИЕ ЧАТА ---
    # Показываем все сообщения из истории
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- ПОЛЕ ВВОДА НОВОГО ВОПРОСА ---
    if prompt := st.chat_input("Задайте уточняющий вопрос по снимку..."):
        # 1. Показываем сообщение пользователя
        with st.chat_message("user"):
            st.markdown(prompt)
        # Добавляем в историю для отображения
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 2. Отправляем в Google (в существующую сессию)
        if st.session_state.chat_session:
            try:
                with st.spinner("Думаю..."):
                    response = st.session_state.chat_session.send_message(prompt)
                    
                    # 3. Показываем ответ модели
                    with st.chat_message("assistant"):
                        st.markdown(response.text)
                    
                    # Добавляем в историю
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Ошибка соединения: {e}")
        else:
            st.error("Сессия истекла. Пожалуйста, перезагрузите страницу или нажмите 'Начать анализ' заново.")
