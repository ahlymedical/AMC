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
# This dictionary will store the status and results of translation jobs.
jobs = {}

# --- تهيئة نموذج Gemini ---
model = None
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro-latest') 
    print("✅ Gemini API configured successfully.")
except Exception as e:
    print(f"!!!!!! FATAL ERROR during Gemini API setup: {e}")

# --- دوال الترجمة (تعمل في الخلفية) ---

def translate_text_api(text_to_translate, target_lang):
    if not text_to_translate or not text_to_translate.strip(): return ""
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
    """This function runs in a separate thread to perform the long translation task."""
    print(f"[Job {job_id}] Starting background processing for {filename}.")
    try:
        jobs[job_id]['status'] = 'processing'
        file_stream = io.BytesIO(file_bytes)
        
        mem_file = io.BytesIO()
        new_filename = f"translated_{os.path.splitext(filename)[0]}"
        
        if filename.lower().endswith('.docx'):
            doc = translate_docx_in_place(docx.Document(file_stream), target_lang)
            doc.save(mem_file)
            new_filename += ".docx"
        elif filename.lower().endswith('.pptx'):
            prs = translate_pptx_in_place(Presentation(file_stream), target_lang)
            prs.save(mem_file)
            new_filename += ".pptx"
        else:
            text_to_translate = ""
            if filename.lower().endswith('.pdf'):
                text_to_translate = read_text_from_pdf(file_stream)
            elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                response = model.generate_content([f"Extract and translate the text in this image to {target_lang}. Provide only the translation.", Image.open(file_stream)])
                text_to_translate = response.text
            
            if not text_to_translate.strip(): raise ValueError("Could not extract text from file.")
            
            translated_text = translate_text_api(text_to_translate, target_lang)
            mem_file = create_docx_from_text(translated_text)
            new_filename += ".docx"

        # Store the result and mark as complete
        jobs[job_id]['result'] = mem_file.getvalue()
        jobs[job_id]['filename'] = new_filename
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
    """Step 1: Receives the file, starts a background job, and returns a job ID immediately."""
    if not model: return jsonify({"error": "API service is not configured."}), 500
    if 'file' not in request.files: return jsonify({"error": "No file part."}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "No selected file."}), 400
    
    job_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    target_lang = request.form.get('target_lang', 'English')
    file_bytes = file.read()

    jobs[job_id] = {'status': 'pending'}
    
    # Start the background thread
    thread = threading.Thread(target=process_translation_job, args=(job_id, file_bytes, filename, target_lang))
    thread.start()
    
    print(f"[Job {job_id}] Created for file {filename}. Returning job ID to client.")
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Step 2: Client polls this endpoint to check the job status."""
    job = jobs.get(job_id)
    if not job: return jsonify({'status': 'not_found'}), 404
    
    response = {'status': job['status']}
    if job['status'] == 'error':
        response['error'] = job.get('error_message', 'An unknown error occurred.')
    
    return jsonify(response)

@app.route('/download/<job_id>', methods=['GET'])
def download_translated_file(job_id):
    """Step 3: Client calls this endpoint to download the final file."""
    job = jobs.get(job_id)
    if not job or job['status'] != 'complete':
        return "Job not found or not complete.", 404
    
    file_bytes = job['result']
    filename = job['filename']
    
    # Clean up the job from memory after download
    del jobs[job_id]
    
    return send_file(io.BytesIO(file_bytes), as_attachment=True, download_name=filename)

@app.route('/translate-text', methods=['POST'])
def translate_text_handler():
    # This remains synchronous as it's a very fast operation.
    if not model: return jsonify({"error": "API service is not configured."}), 500
    data = request.get_json()
    text = data.get('text')
    if not text: return jsonify({"error": "No text provided."}), 400
    target_lang = data.get('target_lang', 'English')
    translated_text = translate_text_api(text, target_lang)
    return jsonify({"translated_text": translated_text})

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)
