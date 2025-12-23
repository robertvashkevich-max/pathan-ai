# --- ФУНКЦИЯ ГЕНЕРАЦИИ PDF (ИСПРАВЛЕННАЯ) ---
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

    # 4. Изображение (ИСПРАВЛЕНИЕ ОШИБКИ ЗДЕСЬ)
    if image_obj:
        try:
            # Если картинка в режиме RGBA (с прозрачностью), конвертируем в RGB
            if image_obj.mode == 'RGBA':
                image_obj = image_obj.convert('RGB')
                
            # Сохраняем временно
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                image_obj.save(tmp.name)
                pdf.image(tmp.name, x=55, w=100) 
                pdf.ln(5)
        except Exception as e:
            pdf.cell(0, 10, f'[Ошибка добавления фото: {str(e)}]', ln=True)

    # 5. Результаты
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, 'ЗАКЛЮЧЕНИЕ ИИ:', ln=True, fill=True)
    pdf.ln(2)
    
    clean_text = analysis_text.replace('**', '').replace('##', '').replace('* ', '- ')
    pdf.multi_cell(0, 6, clean_text)
    
    # 6. Подвал
    pdf.ln(10)
    pdf.set_font('DejaVu', '', 8)
    pdf.cell(0, 10, 'Дисклеймер: Данный отчет создан ИИ-прототипом PathanAI. Требует верификации врачом.', ln=True, align='C')

    return pdf.output(dest='S').encode('latin-1')
