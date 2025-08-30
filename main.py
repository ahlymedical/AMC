import os
import io
import traceback
import time
import uuid
import threading
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
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# --- نظام تتبع المهام غير المتزامن ---
jobs = {}

# --- تهيئة نموذج Gemini ---
model = None
api_key_error = None
try:
    print("Attempting to configure Gemini API...")
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        # هذا هو الخطأ الأكثر شيوعاً الذي يسبب "Service Unavailable"
        raise ValueError("FATAL: GEMINI_API_KEY environment variable not set or found. The application cannot start.")
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro-latest') 
    print("✅ Gemini API configured successfully.")
except Exception as e:
    api_key_error = str(e)
    # طباعة الخطأ الفادح في سجلات الخادم
    print(f"!!!!!! FATAL ERROR during Gemini API setup: {api_key_error}")
    # هذا سيمنع التطبيق من العمل، ولكنه سيوضح المشكلة في السجلات
    
# --- دوال الترجمة (تعمل في الخلفية) ---

def translate_text_api(text_to_translate, target_lang):
    if not text_to_translate or not text_to_translate.strip(): return ""
    # التحقق من تهيئة النموذج قبل استخدامه
    if not model:
        print("API model not available for translation.")
        return f"[Error: API model not configured]"
    try:
        prompt = f"As a master translator, provide a professional and context-aware translation of the following text into {target_lang}. Your output must be ONLY the translated text. Original Text: \"\"\"{text_to_translate}\"\"\""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"      - !!!!! [API Error] {e}")
        return f"[Translation Error: {text_to_translate}]"

def translate_docx_in_place(doc: DocxDocument, target_lang: str):
    for para in doc.paragraphs:
        for run in para.runs:
            if run.text.strip(): run.text = translate_text_api(run.text, target_lang)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        if run.text.strip(): run.text = translate_text_api(run.text, target_lang)
    return doc

def translate_pptx_in_place(prs: Presentation, target_lang: str):
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.text.strip(): run.text = translate_text_api(run.text, target_lang)
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        for paragraph in cell.text_frame.paragraphs:
                            for run in paragraph.runs:
                                if run.text.strip(): run.text = translate_text_api(run.text, target_lang)
    return prs

def read_text_from_pdf(stream):
    return '\n'.join([page.extract_text() for page in PyPDF2.PdfReader(stream).pages if page.extract_text()])

def create_docx_from_text(text):
    mem_file = io.BytesIO()
    doc = docx.Document()
    doc.add_paragraph(text)
    doc.save(mem_file)
    mem_file.seek(0)
    return mem_file

# --- الدالة الرئيسية التي تعمل في الخلفية ---
def process_translation_job(job_id, file_bytes, filename, target_lang):
    print(f"[Job {job_id}] Starting background processing for {filename}.")
    try:
        jobs[job_id]['status'] = 'processing'
        file_stream = io.BytesIO(file_bytes)
        
        mem_file = io.BytesIO()
        new_filename = f"translated_{os.path.splitext(filename)[0]}"
        mimetype = ''
        
        if filename.lower().endswith('.docx'):
            doc = translate_docx_in_place(docx.Document(file_stream), target_lang)
            doc.save(mem_file)
            new_filename += ".docx"
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif filename.lower().endswith('.pptx'):
            prs = translate_pptx_in_place(Presentation(file_stream), target_lang)
            prs.save(mem_file)
            new_filename += ".pptx"
            mimetype = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        else:
            text_to_translate = ""
            if filename.lower().endswith('.pdf'):
                text_to_translate = read_text_from_pdf(file_stream)
            elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                if not model: raise ValueError("Cannot process image, API model not configured.")
                response = model.generate_content([f"Extract and translate the text in this image to {target_lang}. Provide only the translation.", Image.open(file_stream)])
                text_to_translate = response.text
            
            if not text_to_translate.strip(): raise ValueError("Could not extract text from file.")
            
            translated_text = translate_text_api(text_to_translate, target_lang)
            mem_file = create_docx_from_text(translated_text)
            new_filename += ".docx"
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        jobs[job_id]['result'] = mem_file.getvalue()
        jobs[job_id]['filename'] = new_filename
        jobs[job_id]['mimetype'] = mimetype
        jobs[job_id]['status'] = 'complete'
        print(f"[Job {job_id}] Processing complete.")

    except Exception as e:
        print(f"!!!!!! [Job {job_id}] Error during background processing: {e}")
        traceback.print_exc()
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error_message'] = str(e)

# --- مسارات التطبيق (API Endpoints) ---

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/translate-file', methods=['POST'])
def upload_and_start_translation():
    if api_key_error: return jsonify({"error": f"API service is not configured: {api_key_error}"}), 503
    if 'file' not in request.files: return jsonify({"error": "No file part."}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "No selected file."}), 400
    
    job_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    target_lang = request.form.get('target_lang', 'English')
    file_bytes = file.read()

    jobs[job_id] = {'status': 'pending'}
    
    thread = threading.Thread(target=process_translation_job, args=(job_id, file_bytes, filename, target_lang))
    thread.start()
    
    print(f"[Job {job_id}] Created for file {filename}. Returning job ID to client.")
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    job = jobs.get(job_id)
    if not job: return jsonify({'status': 'not_found'}), 404
    
    response = {'status': job['status']}
    if job['status'] == 'error':
        response['error'] = job.get('error_message', 'An unknown error occurred.')
    
    return jsonify(response)

@app.route('/download/<job_id>', methods=['GET'])
def download_translated_file(job_id):
    job = jobs.get(job_id)
    if not job or job['status'] != 'complete':
        return "Job not found or not complete.", 404
    
    file_bytes = job['result']
    filename = job['filename']
    mimetype = job['mimetype']
    
    # لا تقم بحذف المهمة مباشرة للسماح بإعادة التحميل، يمكن إضافة آلية تنظيف لاحقاً
    # del jobs[job_id] 
    
    return send_file(io.BytesIO(file_bytes), as_attachment=True, download_name=filename, mimetype=mimetype)

@app.route('/translate-text', methods=['POST'])
def translate_text_handler():
    if api_key_error: return jsonify({"error": f"API service is not configured: {api_key_error}"}), 503
    data = request.get_json()
    text = data.get('text')
    if not text: return jsonify({"error": "No text provided."}), 400
    target_lang = data.get('target_lang', 'English')
    translated_text = translate_text_api(text, target_lang)
    return jsonify({"translated_text": translated_text})

if __name__ == "__main__":
    # هذا الجزء يعمل فقط عند التشغيل المحلي، وليس على الخادم
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
