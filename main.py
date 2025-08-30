import os
import io
import traceback
import google.generativeai as genai
import docx 
from docx.document import Document as DocxDocument
import PyPDF2
from PIL import Image
from pptx import Presentation
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

# --- إعداد التطبيق ---
# Initialize the Flask application.
# The static_folder is set to the root directory to serve files like index.html.
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app) # Enable Cross-Origin Resource Sharing for the app.

# --- تهيئة نموذج Gemini ---
model = None
api_key_error = None
try:
    # Attempt to get the API key from environment variables. This is a secure way to handle keys.
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        # If the key is not found, raise a clear error.
        raise ValueError("خطأ فادح: متغير البيئة GEMINI_API_KEY غير موجود أو فارغ. يرجى إضافته إلى إعدادات الخادم.")
    
    # Configure the generative AI model with the API key.
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro-latest') 
    print("✅ تم إعداد Gemini API بنجاح باستخدام نموذج gemini-1.5-pro-latest.")

except Exception as e:
    # Catch any exception during setup and store the error message.
    api_key_error = str(e)
    print(f"!!!!!! خطأ فادح أثناء إعداد Gemini API: {api_key_error}")
    # This print statement is crucial for debugging deployment issues.

# --- دوال الترجمة الأساسية ---

def translate_text_api(text_to_translate, target_lang):
    """
    Translates a given text chunk using the Gemini API.
    Args:
        text_to_translate (str): The text to be translated.
        target_lang (str): The target language for translation.
    Returns:
        str: The translated text, or the original text if an error occurs.
    """
    if not text_to_translate or not text_to_translate.strip():
        return "" # Return empty if input is empty.
    try:
        # Construct a professional prompt for the model.
        prompt = f"You are an expert multilingual translator. Translate the following text to {target_lang}. Understand the context professionally. Provide only the translated text, nothing else:\n\n{text_to_translate}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"--- خطأ في ترجمة جزء من النص عبر الـ API: {e}")
        return text_to_translate # Fallback to original text on error.

def translate_docx_in_place(doc: DocxDocument, target_lang: str):
    """
    Translates the text within a DOCX document object paragraph by paragraph and table by table.
    Args:
        doc (DocxDocument): The python-docx document object.
        target_lang (str): The target language.
    Returns:
        DocxDocument: The same document object with translated text.
    """
    print("بدء الترجمة المباشرة لملف DOCX (فقرة بفقرة)...")
    
    # Translate paragraphs
    for para in doc.paragraphs:
        if para.text.strip(): # Only translate non-empty paragraphs.
            original_text = para.text
            print(f"  ترجمة فقرة: '{original_text[:50]}...'")
            translated_text = translate_text_api(original_text, target_lang)
            para.text = translated_text

    # Translate tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                # Recursively translate text within each cell.
                for para in cell.paragraphs:
                    if para.text.strip():
                        original_text = para.text
                        print(f"  ترجمة خلية في جدول: '{original_text[:50]}...'")
                        translated_text = translate_text_api(original_text, target_lang)
                        para.text = translated_text
                        
    print("انتهت الترجمة المباشرة لملف DOCX.")
    return doc

# --- دوال قراءة الملفات ---

def read_text_from_pdf(stream):
    """Extracts text from a PDF file stream."""
    reader = PyPDF2.PdfReader(stream)
    return '\n'.join([page.extract_text() for page in reader.pages if page.extract_text()])

def read_text_from_pptx(stream):
    """Extracts text from a PPTX file stream."""
    prs = Presentation(stream)
    text_runs = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        text_runs.append(run.text)
    return '\n'.join(text_runs)

def create_docx_from_text(text):
    """Creates a new DOCX document in memory from a string of text."""
    mem_file = io.BytesIO()
    doc = docx.Document()
    doc.add_paragraph(text)
    doc.save(mem_file)
    mem_file.seek(0) # Rewind the buffer to the beginning.
    return mem_file

# --- مسارات التطبيق (API Endpoints) ---

@app.route('/')
def serve_index():
    """Serves the main index.html file."""
    return app.send_static_file('index.html')

@app.route('/translate-file', methods=['POST'])
def translate_file_handler():
    """Handles file translation requests."""
    if not model:
        # If the model failed to initialize, return a server error.
        return jsonify({"error": f"خدمة الـ API غير مهيأة بشكل صحيح. السبب: {api_key_error}"}), 500
    if 'file' not in request.files:
        return jsonify({"error": "لم يتم العثور على ملف في الطلب."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "لم يتم تحديد أي ملف."}), 400
    
    filename = secure_filename(file.filename)
    target_lang = request.form.get('target_lang', 'English')
    # The output will always be a .docx file for consistency.
    new_filename = f"translated_{os.path.splitext(filename)[0]}.docx"
    
    try:
        # --- Logic for handling different file types ---
        if filename.lower().endswith('.docx'):
            original_doc = docx.Document(file.stream)
            translated_doc = translate_docx_in_place(original_doc, target_lang)
            mem_file = io.BytesIO()
            translated_doc.save(mem_file)
            mem_file.seek(0)
            return send_file(mem_file, as_attachment=True, download_name=new_filename, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

        text_to_translate = ""
        if filename.lower().endswith('.pdf'):
            text_to_translate = read_text_from_pdf(file.stream)
        elif filename.lower().endswith('.pptx'):
            text_to_translate = read_text_from_pptx(file.stream)
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            # For images, use the multimodal capabilities of the Gemini model.
            image = Image.open(file.stream)
            prompt_parts = [f"Extract and translate the text in this image to {target_lang}. Provide only the translation.", image]
            response = model.generate_content(prompt_parts)
            text_to_translate = response.text
        else:
            return jsonify({"error": "نوع الملف غير مدعوم."}), 400

        if not text_to_translate.strip():
            return jsonify({"error": "لم يتمكن النظام من استخلاص أي نص من الملف."}), 400

        # Translate the extracted text and create a new DOCX file.
        translated_doc_stream = create_docx_from_text(translate_text_api(text_to_translate, target_lang))
        return send_file(translated_doc_stream, as_attachment=True, download_name=new_filename, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    except Exception as e:
        print(f"!!!!!! خطأ فادح أثناء معالجة الملف {filename}: {e}")
        traceback.print_exc() # Print full traceback for detailed debugging.
        return jsonify({"error": "حدث خطأ داخلي في الخادم أثناء معالجة الملف."}), 500

@app.route('/translate-text', methods=['POST'])
def translate_text_handler():
    """Handles instant text translation requests."""
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
    # This block runs when the script is executed directly.
    # It's used for local development. For deployment, a WSGI server like Gunicorn is used.
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
