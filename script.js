document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selections ---
    const selectionScreen = document.getElementById('selection-screen');
    const fileWorkspace = document.getElementById('file-translation');
    const textWorkspace = document.getElementById('text-translation');
    const openDocButton = document.getElementById('open-doc-workspace');
    const openTextButton = document.getElementById('open-text-workspace');
    const backButtons = document.querySelectorAll('.back-btn');

    // --- API Endpoints ---
    const FILE_TRANSLATE_URL = '/translate-file';
    const TEXT_TRANSLATE_URL = '/translate-text';

    // --- File Translation Elements ---
    const fileForm = document.getElementById('file-upload-form');
    const fileInput = document.getElementById('file-input');
    const fileNameDisplay = document.getElementById('file-name-display');
    const uploadArea = document.getElementById('upload-area');
    const fileErrorMsg = document.getElementById('file-error-msg');
    const translateFileBtn = document.getElementById('translate-file-btn');
    const downloadFileBtn = document.getElementById('download-file-btn');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const timeEstimate = document.getElementById('time-estimate');
    
    let progressInterval = null;

    // --- Text Translation Elements ---
    const sourceTextArea = document.getElementById('source-text');
    const targetTextArea = document.getElementById('target-text');
    const copyBtn = document.getElementById('copy-btn');

    // --- Language Population ---
    function populateLanguageSelectors() {
        const languages = { 'Arabic': 'ar', 'English': 'en', 'French': 'fr', 'German': 'de', 'Spanish': 'es', 'Italian': 'it', 'Portuguese': 'pt', 'Dutch': 'nl', 'Russian': 'ru', 'Turkish': 'tr', 'Japanese': 'ja', 'Korean': 'ko', 'Chinese (Simplified)': 'zh-CN', 'Hindi': 'hi', 'Indonesian': 'id', 'Polish': 'pl', 'Swedish': 'sv', 'Vietnamese': 'vi' };
        
        document.querySelectorAll('select').forEach(selector => {
            const currentValue = selector.value;
            selector.innerHTML = '';
            if (selector.id.includes('source')) {
                selector.add(new Option('Auto-Detect', 'auto'));
            }
            for (const name in languages) {
                selector.add(new Option(name, name));
            }
            if (currentValue && selector.querySelector(`option[value="${currentValue}"]`)) {
                 selector.value = currentValue;
            } else {
                 if (selector.id.includes('target')) {
                    selector.value = 'Arabic';
                 }
            }
        });
    }

    // --- Navigation Logic ---
    function openWorkspace(workspaceId) {
        selectionScreen.style.display = 'none';
        fileWorkspace.classList.add('hidden');
        textWorkspace.classList.add('hidden');
        populateLanguageSelectors();
        if (workspaceId === 'file-translation') {
            fileWorkspace.classList.remove('hidden');
            fileWorkspace.style.display = 'flex';
        } else {
            textWorkspace.classList.remove('hidden');
            textWorkspace.style.display = 'flex';
        }
    }

    function showSelectionScreen() {
        fileWorkspace.style.display = 'none';
        textWorkspace.style.display = 'none';
        selectionScreen.style.display = 'flex';
        resetFileUI();
    }

    openDocButton.addEventListener('click', () => openWorkspace('file-translation'));
    openTextButton.addEventListener('click', () => openWorkspace('text-translation'));
    backButtons.forEach(button => button.addEventListener('click', showSelectionScreen));
    
    // --- UI Management ---
    function startProgressSimulation(fileSize) {
        // (هذه الدالة تظهر شريط التقدم وتحاكي عملية التحميل)
        const estimatedDuration = 10 + (fileSize / 1024 / 1024) * 15; // Base 10s + 15s per MB
        let progress = 0;
        let elapsed = 0;
        progressContainer.classList.remove('hidden');
        progressBar.style.width = '0%';
        progressBar.style.background = '';
        progressText.textContent = `Processing... 0%`;
        timeEstimate.textContent = `~${Math.round(estimatedDuration)}s remaining`;
        translateFileBtn.classList.add('hidden');
        downloadFileBtn.classList.add('hidden');

        progressInterval = setInterval(() => {
            elapsed++;
            progress = Math.min(95, (elapsed / estimatedDuration) * 100);
            progressBar.style.width = `${progress.toFixed(2)}%`;
            progressText.textContent = `Processing... ${Math.round(progress)}%`;
            const remaining = Math.round(estimatedDuration - elapsed);
            timeEstimate.textContent = remaining > 0 ? `~${remaining}s remaining` : 'Finalizing...';
            if (progress >= 95) { clearInterval(progressInterval); }
        }, 1000);
    }

    function completeProgress() {
        // (هذه الدالة تظهر عند اكتمال الترجمة بنجاح)
        clearInterval(progressInterval);
        progressBar.style.width = '100%';
        progressText.textContent = 'Success!';
        timeEstimate.textContent = 'Download will start automatically.';
        translateFileBtn.classList.add('hidden');
        downloadFileBtn.classList.remove('hidden');
    }
    
    function failProgress(errorMessage) {
        // (هذه الدالة تظهر عند حدوث خطأ)
        clearInterval(progressInterval);
        progressContainer.classList.remove('hidden');
        progressBar.style.background = 'var(--amc-orange)';
        progressText.textContent = `Error: ${errorMessage}`;
        timeEstimate.textContent = 'Please try again.';
        translateFileBtn.disabled = false;
        translateFileBtn.classList.remove('hidden');
        downloadFileBtn.classList.add('hidden');
    }
    
    function resetFileUI() {
        clearInterval(progressInterval);
        fileInput.value = ''; 
        const enText = fileNameDisplay.querySelector('.en b');
        const arText = fileNameDisplay.querySelector('.ar b');
        if(enText) enText.textContent = 'Click to upload';
        if(arText) arText.textContent = 'انقر للرفع';
        progressContainer.classList.add('hidden');
        translateFileBtn.classList.remove('hidden');
        translateFileBtn.disabled = false;
        downloadFileBtn.classList.add('hidden');
        fileErrorMsg.classList.add('hidden');
        uploadArea.classList.remove('error');
    }

    // --- Synchronous File Handling ---
    async function handleFileSubmit(e) {
        e.preventDefault();
        if (fileInput.files.length === 0) {
            fileErrorMsg.classList.remove('hidden');
            uploadArea.classList.add('error');
            setTimeout(() => { uploadArea.classList.remove('error'); }, 500);
            return;
        }

        const file = fileInput.files[0];
        translateFileBtn.disabled = true;
        startProgressSimulation(file.size);

        try {
            const formData = new FormData(fileForm);
            const response = await fetch(FILE_TRANSLATE_URL, { method: 'POST', body: formData });

            if (!response.ok) {
                // إذا فشل الطلب، حاول قراءة رسالة الخطأ كـ JSON
                let errorMsg = 'An unknown server error occurred.';
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || `HTTP error! status: ${response.status}`;
                } catch (jsonError) {
                    errorMsg = 'Server returned an invalid response. Please try again.';
                }
                throw new Error(errorMsg);
            }

            // --- إذا نجح الطلب، فالاستجابة هي الملف نفسه ---
            completeProgress();
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = downloadUrl;
            
            const contentDisposition = response.headers.get('content-disposition');
            let filename = `translated_${file.name.replace(/\.[^/.]+$/, "")}.docx`; // Default filename
             if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                if (filenameMatch && filenameMatch.length > 1) {
                    filename = filenameMatch[1];
                }
            }
            a.download = filename;
            document.body.appendChild(a);
            a.click(); // بدء التحميل تلقائياً
            
            // جعل الزر الأخضر قابلاً للضغط لإعادة التحميل
            downloadFileBtn.onclick = () => { a.click(); }; 

            setTimeout(() => {
                a.remove();
                window.URL.revokeObjectURL(downloadUrl);
            }, 10000); // تنظيف الرابط بعد 10 ثوان

        } catch (error) {
            failProgress(error.message);
        }
    }

    async function handleTextTranslation() {
        // (هذه الدالة للترجمة الفورية للنصوص)
        const text = sourceTextArea.value.trim();
        if (!text) { targetTextArea.value = ''; return; }
        targetTextArea.placeholder = "Translating...";
        try {
            const response = await fetch(TEXT_TRANSLATE_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: text,
                    source_lang: document.getElementById('text-source-lang').value,
                    target_lang: document.getElementById('text-target-lang').value
                })
            });
            if (!response.ok) { throw new Error('Server error'); }
            const data = await response.json();
            targetTextArea.value = data.translated_text;
        } catch (error) {
            targetTextArea.value = `Error: ${error.message}`;
        }
    }

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            resetFileUI(); 
            const file = fileInput.files[0];
            const enText = fileNameDisplay.querySelector('.en b');
            const arText = fileNameDisplay.querySelector('.ar b');
            if(enText) enText.textContent = file.name;
            if(arText) arText.textContent = '';
        }
    });

    // --- Event Listeners ---
    uploadArea.addEventListener('dragenter', (e) => { e.preventDefault(); e.stopPropagation(); uploadArea.classList.add('dragover'); });
    uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); e.stopPropagation(); uploadArea.classList.add('dragover'); });
    uploadArea.addEventListener('dragleave', (e) => { e.preventDefault(); e.stopPropagation(); uploadArea.classList.remove('dragover'); });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault(); e.stopPropagation();
        uploadArea.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            fileInput.dispatchEvent(new Event('change'));
        }
    });

    fileForm.addEventListener('submit', handleFileSubmit);
    
    let debounceTimer;
    sourceTextArea.addEventListener('input', () => { 
        clearTimeout(debounceTimer); 
        debounceTimer = setTimeout(handleTextTranslation, 500); 
    });
    copyBtn.addEventListener('click', () => { 
        navigator.clipboard.writeText(targetTextArea.value);
    });
    
    // --- Initial Setup ---
    showSelectionScreen();
});
