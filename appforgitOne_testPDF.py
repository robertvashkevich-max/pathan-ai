import streamlit as st
import google.generativeai as genai
from PIL import Image
import datetime
from fpdf import FPDF
import tempfile
from pyairtable import Api

st.set_page_config(page_title="PathanAI Diagnostic", page_icon="🛠")

# --- ПОДКЛЮЧЕНИЕ ---
try:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_key)
    
    # Airtable (оставляем, чтобы не было ошибок инициализации)
    airtable_token = st.secrets["airtable"]["API_TOKEN"]
    base_id = st.secrets["airtable"]["BASE_ID"]
    api = Api(airtable_token)
except Exception as e:
    st.error(f"Ошибка ключей: {e}")
    st.stop()

# --- ИНТЕРФЕЙС ---
st.title("🛠 Диагностика Доступа Google AI")
st.write(f"Библиотека GenAI Lib: **{genai.__version__}** (Это отлично!)")

st.markdown("---")
st.header("🔍 Какие модели видит ваш Ключ?")

if st.button("Сканировать доступные модели", type="primary"):
    with st.spinner("Спрашиваю у Google..."):
        try:
            available_models = []
            # Запрашиваем список всех моделей
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            
            if available_models:
                st.success(f"Найдено моделей: {len(available_models)}")
                st.write("Ваш ключ имеет доступ к:")
                
                # Выводим список красивым кодом
                st.code("\n".join(available_models))
                
                st.info("👇 Скопируйте одно из названий выше (например models/gemini-pro) и пришлите мне, я вставлю его в код.")
            else:
                st.error("Список моделей ПУСТ!")
                st.warning("Это значит, что API ключ валидный, но у него нет прав ни на одну модель. Возможно, в Google Cloud Console не включен 'Generative Language API'.")
                
        except Exception as e:
            st.error(f"КРИТИЧЕСКАЯ ОШИБКА КЛЮЧА: {e}")
            st.markdown("Скорее всего, ключ неверный или заблокирован.")

st.markdown("---")
st.write("Попробуйте нажать кнопку выше и скажите, что появилось в списке.")
