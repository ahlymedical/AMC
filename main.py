import os
import io
import traceback
import google.generativeai as genai
import docx 
from docx.document import Document as DocxDocument
from docx.text.paragraph import Paragraph
from docx.table import _Cell
import PyPDF2
from PIL import Image
from pptx import Presentation
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# --- إعداد التطبيق ---
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# --- تهيئة نموذج Gemini ---
model = None
api_key_error = None
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("خطأ فادح: متغير البيئة GEMINI_API_KEY غير موجود أو فارغ. يرجى إضافته إلى إعدادات الخادم.")
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro-latest') 
    print("✅ تم إعداد Gemini API بنجاح باستخدام نموذج gemini-1.5-pro-latest.")

except Exception as e:
    api_key_error = str(e)
    print(f"!!!!!! خطأ فادح أثناء إعداد Gemini API: {api_key_error}")

# --- دوال الترجمة الأساسية ---

def translate_text_api(text_to_translate, target_lang):
    """
    Translates a given text chunk using the Gemini API with an improved prompt.
    """
    if not text_to_translate or not text_to_translate.strip():
        return ""
    try:
        # Prompt محسن لضمان فهم السياق والاحتفاظ بالنبرة الاحترافية
        prompt = f"""As a master translator, provide a professional and context-aware translation of the following text into {target_lang}. 
Your output must be ONLY the translated text, preserving the original tone and meaning. 
Do not add any extra explanations or introductory phrases.

Original Text:
\"\"\"{text_to_translate}\"\"\""""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"--- خطأ في ترجمة جزء من النص عبر الـ API: {e}")
        return text_to_translate

def translate_docx_in_place(doc: DocxDocument, target_lang: str):
    """
    Translates DOCX text run-by-run to preserve intra-paragraph formatting (bold, color, etc.).
    """
    print("بدء الترجمة المباشرة لملف DOCX (مع الحفاظ على التنسيق الدقيق)...")
    
    # Translate paragraphs by iterating through runs
    for para in doc.paragraphs:
        for run in para.runs:
            if run.text.strip():
                original_text = run.text
                print(f"  ترجمة جزء من النص في Word: '{original_text[:50]}...'")
                translated_text = translate_text_api(original_text, target_lang)
                run.text = translated_text

    # Translate tables by iterating through cells and then runs
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        if run.text.strip():
                            original_text = run.text
                            print(f"  ترجمة جزء من نص في جدول Word: '{original_text[:50]}...'")
                            translated_text = translate_text_api(original_text, target_lang)
                            run.text = translated_text
                        
    print("انتهت الترجمة المباشرة لملف DOCX.")
    return doc

def translate_pptx_in_place(prs: Presentation, target_lang: str):
    """
    [ميزة جديدة]
    Translates PPTX text run-by-run to preserve all formatting, layout, and images.
    """
    print("بدء الترجمة المباشرة لملف PowerPoint (مع الحفاظ على التصميم)...")
    
    # Iterate through slides, shapes, and text runs
    for slide in prs.slides:
        for shape in slide.shapes:
            # Handle regular text boxes and shapes
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.text.strip():
                            original_text = run.text
                            print(f"  ترجمة نص في شريحة PowerPoint: '{original_text[:50]}...'")
                            translated_text = translate_text_api(original_text, target_lang)
                            run.text = translated_text
            
            # Handle tables
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        for paragraph in cell.text_frame.paragraphs:
                            for run in paragraph.runs:
                                if run.text.strip():
                                    original_text = run.text
                                    print(f"  ترجمة نص في جدول PowerPoint: '{original_text[:50]}...'")
                                    translated_text = translate_text_api(original_text, target_lang)
                                    run.text = translated_text

    print("انتهت الترجمة المباشرة لملف PowerPoint.")
    return prs

# --- دوال قراءة الملفات ---

def read_text_from_pdf(stream):
    """Extracts plain text from a PDF. NOTE: All formatting is lost."""
    reader = PyPDF2.PdfReader(stream)
    return '\n'.join([page.extract_text() for page in reader.pages if page.extract_text()])

def create_docx_from_text(text):
    """Creates a new DOCX document in memory from a string of text."""
    mem_file = io.BytesIO()
    doc = docx.Document()
    doc.add_paragraph(text)
    doc.save(mem_file)
    mem_file.seek(0)
    return mem_file

# --- مسارات التطبيق (API Endpoints) ---

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/translate-file', methods=['POST'])
def translate_file_handler():
    if not model:
        return jsonify({"error": f"خدمة الـ API غير مهيأة بشكل صحيح. السبب: {api_key_error}"}), 500
    if 'file' not in request.files:
        return jsonify({"error": "لم يتم العثور على ملف في الطلب."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "لم يتم تحديد أي ملف."}), 400
    
    filename = secure_filename(file.filename)
    target_lang = request.form.get('target_lang', 'English')
    
    try:
        # --- Logic for handling different file types ---
        if filename.lower().endswith('.docx'):
            original_doc = docx.Document(file.stream)
            translated_doc = translate_docx_in_place(original_doc, target_lang)
            mem_file = io.BytesIO()
            translated_doc.save(mem_file)
            mem_file.seek(0)
            new_filename = f"translated_{os.path.splitext(filename)[0]}.docx"
            return send_file(mem_file, as_attachment=True, download_name=new_filename, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

        elif filename.lower().endswith('.pptx'):
            original_prs = Presentation(file.stream)
            translated_prs = translate_pptx_in_place(original_prs, target_lang)
            mem_file = io.BytesIO()
            translated_prs.save(mem_file)
            mem_file.seek(0)
            new_filename = f"translated_{os.path.splitext(filename)[0]}.pptx"
            return send_file(mem_file, as_attachment=True, download_name=new_filename, mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')

        # Fallback for non-editable formats (PDF, Images)
        text_to_translate = ""
        if filename.lower().endswith('.pdf'):
            text_to_translate = read_text_from_pdf(file.stream)
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            image = Image.open(file.stream)
            prompt_parts = [f"Extract and translate the text in this image to {target_lang}. Provide only the translation.", image]
            response = model.generate_content(prompt_parts)
            text_to_translate = response.text
        else:
            return jsonify({"error": "نوع الملف غير مدعوم."}), 400

        if not text_to_translate.strip():
            return jsonify({"error": "لم يتمكن النظام من استخلاص أي نص من الملف."}), 400

        translated_doc_stream = create_docx_from_text(translate_text_api(text_to_translate, target_lang))
        new_filename = f"translated_{os.path.splitext(filename)[0]}.docx"
        return send_file(translated_doc_stream, as_attachment=True, download_name=new_filename, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    except Exception as e:
        print(f"!!!!!! خطأ فادح أثناء معالجة الملف {filename}: {e}")
        traceback.print_exc()
        return jsonify({"error": "حدث خطأ داخلي في الخادم أثناء معالجة الملف."}), 500

@app.route('/translate-text', methods=['POST'])
def translate_text_handler():
    if not model:
        return jsonify({"error": f"خدمة الـ API غير مهيأة بشكل صحيح. السبب: {api_key_error}"}), 500
    data = request.get_json()
    text = data.get('text')
    if not text:
        return jsonify({"error": "لم يتم توفير أي نص للترجمة."}), 400
    target_lang = data.get('target_lang', 'English')
    try:
        translated_text = translate_text_api(text, target_lang)
        return jsonify({"translated_text": translated_text})
    except Exception as e:
        print(f"!!!!!! حدث خطأ أثناء ترجمة النص: {e}")
        return jsonify({"error": "حدث خطأ داخلي أثناء عملية الترجمة."}), 500

# --- تشغيل التطبيق ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
