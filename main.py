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

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

model = None
api_key_error = None
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set or found.")
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-pro-latest') 
    print("✅ Gemini API configured successfully with gemini-1.5-pro-latest model.")
except Exception as e:
    api_key_error = str(e)
    print(f"!!!!!! FATAL ERROR during Gemini API setup: {api_key_error}")

def translate_text_api(text_to_translate, target_lang):
    if not text_to_translate or not text_to_translate.strip():
        return ""
    try:
        prompt = f"You are an expert multilingual translator. Translate the following text to {target_lang}. Understand the context professionally. Provide only the translated text, nothing else:\n\n{text_to_translate}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"--- API translation error for a chunk: {e}")
        return text_to_translate

def translate_docx_in_place(doc: DocxDocument, target_lang: str):
    print("Starting in-place DOCX translation (paragraph by paragraph)...")
    
    for para in doc.paragraphs:
        if para.text.strip():
            original_text = para.text
            print(f"  Translating paragraph: '{original_text[:50]}...'")
            translated_text = translate_text_api(original_text, target_lang)
            para.text = translated_text

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if para.text.strip():
                        original_text = para.text
                        print(f"  Translating table cell: '{original_text[:50]}...'")
                        translated_text = translate_text_api(original_text, target_lang)
                        para.text = translated_text
                        
    print("In-place DOCX translation finished.")
    return doc

def read_text_from_pdf(stream):
    reader = PyPDF2.PdfReader(stream)
    return '\n'.join([page.extract_text() for page in reader.pages if page.extract_text()])

def read_text_from_pptx(stream):
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
    mem_file = io.BytesIO()
    doc = docx.Document()
    doc.add_paragraph(text)
    doc.save(mem_file)
    mem_file.seek(0)
    return mem_file

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/translate-file', methods=['POST'])
def translate_file_handler():
    if not model: return jsonify({"error": "API service is not configured."}), 500
    if 'file' not in request.files: return jsonify({"error": "No file part in the request."}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"error": "No file selected."}), 400
    
    filename = secure_filename(file.filename)
    target_lang = request.form.get('target_lang', 'English')
    new_filename = f"translated_{os.path.splitext(filename)[0]}.docx"
    
    try:
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
            image = Image.open(file.stream)
            prompt_parts = [f"Extract and translate the text in this image to {target_lang}. Provide only the translation.", image]
            response = model.generate_content(prompt_parts)
            text_to_translate = response.text
        else:
            return jsonify({"error": "Unsupported file type."}), 400

        if not text_to_translate.strip():
            return jsonify({"error": "Could not extract text from the file."}), 400

        translated_doc_stream = create_docx_from_text(translate_text_api(text_to_translate, target_lang))
        return send_file(translated_doc_stream, as_attachment=True, download_name=new_filename, mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    except Exception as e:
        print(f"!!!!!! CRITICAL ERROR during file processing for {filename}: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred during file processing."}), 500

@app.route('/translate-text', methods=['POST'])
def translate_text_handler():
    if not model: return jsonify({"error": "API service is not configured."}), 500
    data = request.get_json()
    text = data.get('text')
    if not text: return jsonify({"error": "No text provided."}), 400
    target_lang = data.get('target_lang', 'English')
    try:
        prompt = (f"Translate the following text to '{target_lang}'. Provide only the professional translated text.\n\n{text}")
        response = model.generate_content(prompt)
        return jsonify({"translated_text": response.text})
    except Exception as e:
        print(f"!!!!!! An error occurred during text translation: {e}")
        return jsonify({"error": "An internal error occurred during translation."}), 500

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=False, host='0.0.0.0', port=port)```

---

#### الملف الرابع: `index.html` (الهيكل النهائي)
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AMC GlobalTranslate | AI Translation Suite</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="app-container">
        <header class="app-header">
            <img src="https://i.ibb.co/p91wYFv/AMC-LOGO-02.png" alt="AMC Logo" class="logo">
        </header>
        <main class="app-main">
            <div id="selection-screen" class="selection-container">
                <div class="title-container">
                    <h1><span class="en">AMC GlobalTranslate</span><span class="ar">الترجمة العالمية من شركة الأهلي للخدمات الطبية</span></h1>
                    <p><span class="en">Professional AI Translation to Empower Your Business</span><span class="ar">ترجمة احترافية بالذكاء الاصطناعي لتمكين أعمالك</span></p>
                </div>
                <div class="action-buttons-container">
                    <button id="open-doc-workspace" class="action-btn">
                        <div class="btn-icon document-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20,2H8A2,2,0,0,0,6,4V16a2,2,0,0,0,2,2H20a2,2,0,0,0,2-2V4A2,2,0,0,0,20,2ZM14.1,15.5H12.9V12.42l-1.6,1.6L10.5,13.2l2-2a.54.54,0,0,1,.76,0l2,2-0.8.82-1.6-1.6ZM4,6H2V20a2,2,0,0,0,2,2H16V20H4Z"></path></svg>
                        </div>
                        <div class="btn-text">
                            <h3><span class="en">Document Translation</span><span class="ar">ترجمة المستندات</span></h3>
                        </div>
                    </button>
                    <button id="open-text-workspace" class="action-btn">
                        <div class="btn-icon instant-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20.67,15.08l-3.39-3.39a1,1,0,0,0-1.41,0l-1.3,1.3a1,1,0,0,0,0,1.41l3.39,3.39a1,1,0,0,0,1.41,0l1.3-1.3A1,1,0,0,0,20.67,15.08ZM8.92,3.33a1,1,0,0,0,0,1.41l1.3,1.3a1,1,0,0,0,1.41,0l3.39-3.39a1,1,0,0,0,0-1.41l-1.3-1.3a1,1,0,0,0-1.41,0Zm1.41,10.34a1,1,0,0,0-1.41,0L2.29,20.29a1,1,0,0,0,0,1.41l.59.59a1,1,0,0,0,1.41,0L10.92,15.7a1,1,0,0,0,0-1.41Z"></path></svg>
                        </div>
                        <div class="btn-text">
                            <h3><span class="en">Instant Text</span><span class="ar">الترجمة الفورية</span></h3>
                        </div>
                    </button>
                </div>
            </div>
            <div id="file-translation" class="workspace">
                <button class="back-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M7.82843 10.9999H20V12.9999H7.82843L13.1924 18.3638L11.7782 19.778L4 11.9999L11.7782 4.22168L13.1924 5.63589L7.82843 10.9999Z"></path></svg>
                    <span>Back / عودة</span>
                </button>
                <h2 class="workspace-title"><span class="en">Document Translation</span><span class="ar">ترجمة المستندات</span></h2>
                <form id="file-upload-form" class="translation-form">
                    <div class="language-selectors">
                        <select id="file-source-lang" name="source_lang"></select>
                        <select id="file-target-lang" name="target_lang"></select>
                    </div>
                    <div class="upload-area" id="upload-area">
                        <input type="file" id="file-input" name="file" accept=".docx,.pdf,.png,.jpg,.jpeg,.pptx" hidden>
                        <label for="file-input" class="upload-label">
                            <div class="upload-icon-wrapper">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                            </div>
                            <span id="file-name-display" class="upload-text">
                                <span class="en"><b>Click to upload</b> or drag & drop a file</span>
                                <span class="ar"><b>انقر للرفع</b> أو قم بسحب وإفلات الملف</span>
                                <small>(docx, pptx, pdf, png, jpg)</small>
                            </span>
                        </label>
                    </div>
                    <div id="progress-container" class="progress-container">
                        <div class="progress-info"><span id="progress-text"></span><span id="time-estimate"></span></div>
                        <div class="progress-bar-background"><div id="progress-bar"></div></div>
                    </div>
                    <div class="form-actions">
                        <button type="submit" class="submit-btn" id="translate-file-btn"><span><span class="en">Translate & Download</span><span class="ar">ترجم وحمّل</span></span></button>
                    </div>
                </form>
            </div>
            <div id="text-translation" class="workspace">
                 <button class="back-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M7.82843 10.9999H20V12.9999H7.82843L13.1924 18.3638L11.7782 19.778L4 11.9999L11.7782 4.22168L13.1924 5.63589L7.82843 10.9999Z"></path></svg>
                    <span>Back / عودة</span>
                </button>
                <h2 class="workspace-title"><span class="en">Instant Text</span><span class="ar">الترجمة الفورية</span></h2>
                <div class="translation-form">
                     <div class="language-selectors">
                        <select id="text-source-lang"></select>
                        <select id="text-target-lang"></select>
                    </div>
                    <div class="text-areas">
                        <textarea id="source-text" placeholder="Enter text... / أدخل النص..."></textarea>
                        <div class="target-text-container">
                            <textarea id="target-text" placeholder="Translation... / الترجمة..." readonly></textarea>
                            <button id="copy-btn" type="button" title="Copy text">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </main>
        <footer class="app-footer">
             <p><span class="en">Developed by <b>Al Ahly Medical Company Marketing Team</b></span><span class="ar">تم التطوير بواسطة <b>فريق شركة الاهلي للخدمات الطبية</b></span></p>
        </footer>
    </div>
    <script src="script.js"></script>
</body>
</html>
