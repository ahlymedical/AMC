document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selections ---
    const selectionScreen = document.getElementById('selection-screen');
    const fileWorkspace = document.getElementById('file-translation');
    const textWorkspace = document.getElementById('text-translation');
    const openDocButton = document.getElementById('open-doc-workspace');
    const openTextButton = document.getElementById('open-text-workspace');
    const backButtons = document.querySelectorAll('.back-btn');

    // --- API Endpoints ---
    const FILE_UPLOAD_URL = '/translate-file';
    const STATUS_URL = '/status/';
    const DOWNLOAD_URL = '/download/';
    const TEXT_TRANSLATE_URL = '/translate-text';

    // --- File Translation Elements & State ---
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
    
    let statusInterval = null;

    // --- Text Translation Elements ---
    const sourceTextArea = document.getElementById('source-text');
    const targetTextArea = document.getElementById('target-text');
    const copyBtn = document.getElementById('copy-btn');

    // --- THE DEFINITIVE FIX for Language Dropdowns ---
    function populateLanguageSelectors() {
        const languages = { 'Arabic': 'ar', 'English': 'en', 'French': 'fr', 'German': 'de', 'Spanish': 'es', 'Italian': 'it', 'Portuguese': 'pt', 'Dutch': 'nl', 'Russian': 'ru', 'Turkish': 'tr', 'Japanese': 'ja', 'Korean': 'ko', 'Chinese (Simplified)': 'zh-CN', 'Hindi': 'hi', 'Indonesian': 'id', 'Polish': 'pl', 'Swedish': 'sv', 'Vietnamese': 'vi' };
        
        document.querySelectorAll('select').forEach(selector => {
            // Preserve the current value to re-select it after populating
            const currentValue = selector.value;
            
            // Clear existing options
            selector.innerHTML = '';

            // Add Auto-Detect for source languages
            if (selector.id.includes('source')) {
                selector.add(new Option('Auto-Detect', 'auto'));
            }

            // Add all languages
            for (const name in languages) {
                selector.add(new Option(name, name));
            }
            
            // Restore previous value or set default
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

        // Populate selectors every time a workspace is opened to ensure they are correct
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
    function showProgressUI() {
        progressContainer.classList.remove('hidden');
        progressBar.style.width = '0%';
        progressText.textContent = 'Uploading...';
        timeEstimate.textContent = 'Please wait';
        let progress = 0;
        statusInterval = setInterval(() => {
            progress = (progress + 5) % 100;
            progressBar.style.width = `${progress}%`;
        }, 500);
    }

    function completeProgress() {
        clearInterval(statusInterval);
        progressBar.style.width = '100%';
        progressText.textContent = 'Success!';
        timeEstimate.textContent = 'Ready to download.';
        translateFileBtn.classList.add('hidden');
        downloadFileBtn.classList.remove('hidden');
    }
    
    function failProgress(errorMessage) {
        clearInterval(statusInterval);
        progressBar.style.background = 'var(--amc-orange)';
        progressText.textContent = `Error: ${errorMessage}`;
        timeEstimate.textContent = 'Please try again.';
        translateFileBtn.disabled = false;
        translateFileBtn.classList.remove('hidden');
        downloadFileBtn.classList.add('hidden');
    }
    
    function resetFileUI() {
        clearInterval(statusInterval);
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
        progressBar.style.background = '';
    }

    // --- Asynchronous Job Handling ---
    async function checkJobStatus(jobId) {
        try {
            const response = await fetch(STATUS_URL + jobId);
            const data = await response.json();

            if (data.status === 'complete') {
                clearInterval(statusInterval);
                downloadFileBtn.onclick = () => { window.location.href = DOWNLOAD_URL + jobId; setTimeout(resetFileUI, 1500); };
                completeProgress();
            } else if (data.status === 'error') {
                clearInterval(statusInterval);
                failProgress(data.error || 'An unknown error occurred during processing.');
            } else {
                progressText.textContent = 'Processing in background...';
            }
        } catch (error) {
            clearInterval(statusInterval);
            failProgress('Failed to get status from server.');
        }
    }

    async function handleFileSubmit(e) {
        e.preventDefault();
        if (fileInput.files.length === 0) {
            fileErrorMsg.classList.remove('hidden');
            uploadArea.classList.add('error');
            setTimeout(() => { uploadArea.classList.remove('error'); }, 500);
            return;
        }

        translateFileBtn.disabled = true;
        showProgressUI();

        try {
            const formData = new FormData(fileForm);
            const response = await fetch(FILE_UPLOAD_URL, { method: 'POST', body: formData });
            
            if (!response.ok) { throw new Error('Server failed to start the job.'); }
            
            const data = await response.json();
            const jobId = data.job_id;
            
            clearInterval(statusInterval);
            progressBar.style.width = '50%';
            progressText.textContent = 'Processing in background...';
            statusInterval = setInterval(() => checkJobStatus(jobId), 5000);

        } catch (error) {
            failProgress(error.message);
        }
    }

    async function handleTextTranslation() {
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
            progressContainer.classList.add('hidden');
            fileErrorMsg.classList.add('hidden');
            uploadArea.classList.remove('error');
            translateFileBtn.classList.remove('hidden');
            translateFileBtn.disabled = false;
            downloadFileBtn.classList.add('hidden');
            progressBar.style.background = '';

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
