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
# ------------------------------------

# --- ЗАГОЛОВОК ---
st.title("🔬 PathanAI: Онлайн")
st.header("Система поддержки принятия врачебных решений")
st.info("Прототип для исследовательских целей. Не является медицинским изделием.")

# --- ПОДБОР МОДЕЛИ ---
valid_model_name = None
try:
    genai.configure(api_key=api_key)
    all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    for name in all_models:
        if 'flash' in name:
            valid_model_name = name
            break
    if not valid_model_name:
        for name in all_models:
            if 'pro' in name:
                valid_model_name = name
                break
    if not valid_model_name and all_models:
        valid_model_name = all_models[0]
except Exception:
    pass

# --- ШАГ 1: ДАННЫЕ ПАЦИЕНТА (ТЕПЕРЬ СВЕРХУ) ---
st.markdown("### 📝 Шаг 1. Данные пациента")

col1, col2, col3 = st.columns(3)
with col1:
    gender = st.selectbox("Пол", ["Не указан", "Мужской", "Женский"])
with col2:
    weight = st.number_input("Вес (кг)", min_value=0.0, step=0.1, format="%.1f")
with col3:
    dob = st.date_input(
        "Дата рождения", 
        min_value=datetime.date(1900, 1, 1),
        max_value=datetime.date.today(),
        value=datetime.date(1980, 1, 1)
    )

col4, col5 = st.columns(2)
with col4:
    biopsy_method = st.selectbox("Метод биопсии:", ["Неизвестно", "Эксцизионная", "Пункция", "Мазок", "Операция"])
with col5:
    smoking = st.selectbox("Курение:", ["Не курит", "Курит сейчас", "В прошлом", "Неизвестно"])

tissue_type = st.selectbox("Тип ткани:", ["Неизвестно", "Кожа", "Слизистая", "Лимфоузел", "Молочная железа", "Печень", "Легкое", "Другое"])
anamnesis = st.text_area("Анамнез:", placeholder="Жалобы, динамика роста, особенности течения...")

st.markdown("---")

# --- ШАГ 2: ЗАГРУЗКА ФОТО (ТЕПЕРЬ СНИЗУ) ---
st.markdown("### 📷 Шаг 2. Загрузка снимка")
uploaded_file = st.file_uploader("Выберите файл (JPEG, PNG)", type=["jpg", "png", "jpeg"])

image = None
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Загруженный образец", use_column_width=True)

# --- КНОПКА ЗАПУСКА ---
if st.button("🚀 Начать анализ", type="primary"):
    # Проверка: загрузил ли пользователь фото?
    if not uploaded_file:
        st.warning("⚠️ Пожалуйста, сначала загрузите снимок (Шаг 2), чтобы начать анализ.")
    elif not valid_model_name:
        st.error("Ошибка подключения к AI. Проверьте ключ.")
    else:
        # Если всё ок — запускаем ИИ
        model = genai.GenerativeModel(valid_model_name)
        with st.spinner('Анализ данных и снимка...'):
            try:
                prompt_text = "Ты эксперт-патологоанатом. Проанализируй снимок.\n"
                prompt_text += f"Пациент: {gender}, вес {weight}, д.р. {dob}, курение: {smoking}.\n"
                prompt_text += f"Образец: {tissue_type}, метод: {biopsy_method}.\n"
                prompt_text += f"Анамнез: {anamnesis}.\n"
                prompt_text += "Дай описание: соответствие ткани, микроскопия, патология и заключение. В конце добавь дисклеймер."

                response = model.generate_content([prompt_text, image])
                st.markdown("### 📋 Заключение PathanAI")
                st.write(response.text)
            except Exception as e:
                st.error(f"Ошибка: {e}")
