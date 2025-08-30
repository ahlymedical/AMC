document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selections ---
    const selectionScreen = document.getElementById('selection-screen');
    const fileWorkspace = document.getElementById('file-translation');
    const textWorkspace = document.getElementById('text-translation');
    const openDocButton = document.getElementById('open-doc-workspace');
    const openTextButton = document.getElementById('open-text-workspace');
    const backButtons = document.querySelectorAll('.back-btn');

    // --- Navigation Logic ---
    function openWorkspace(workspaceId) {
        selectionScreen.style.display = 'none';
        fileWorkspace.classList.add('hidden');
        textWorkspace.classList.add('hidden');
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

    // --- API Endpoints ---
    const FILE_TRANSLATE_URL = '/translate-file';
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
    
    let progressInterval = null;
    let translatedFileBlob = null;
    let translatedFileName = '';

    // --- Text Translation Elements ---
    const sourceTextArea = document.getElementById('source-text');
    const targetTextArea = document.getElementById('target-text');
    const copyBtn = document.getElementById('copy-btn');
    
    // --- Language Population ---
    const languages = { 'Arabic': 'ar', 'English': 'en', 'French': 'fr', 'German': 'de', 'Spanish': 'es', 'Italian': 'it', 'Portuguese': 'pt', 'Dutch': 'nl', 'Russian': 'ru', 'Turkish': 'tr', 'Japanese': 'ja', 'Korean': 'ko', 'Chinese (Simplified)': 'zh-CN', 'Hindi': 'hi', 'Indonesian': 'id', 'Polish': 'pl', 'Swedish': 'sv', 'Vietnamese': 'vi' };
    
    function populateLanguageSelectors() {
        document.querySelectorAll('select').forEach(selector => {
            const isSource = selector.id.includes('source');
            selector.innerHTML = isSource ? '<option value="auto">Auto-Detect</option>' : '';
            for (const name in languages) { selector.add(new Option(name, name)); }
        });
        document.getElementById('file-target-lang').value = 'Arabic';
        document.getElementById('text-target-lang').value = 'Arabic';
    }
    
    // --- File Translation UI Management ---
    function startProgressSimulation(fileSize) {
        const estimatedDuration = 10 + (fileSize / 1024 / 1024) * 15;
        let progress = 0;
        let elapsed = 0;
        progressContainer.classList.remove('hidden');
        progressBar.style.width = '0%';
        progressBar.style.background = '';
        progressText.textContent = `Processing... 0%`;
        timeEstimate.textContent = `~${Math.round(estimatedDuration)}s remaining`;
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
        clearInterval(progressInterval);
        progressBar.style.width = '100%';
        progressText.textContent = 'Success!';
        timeEstimate.textContent = 'Ready to download.';
        translateFileBtn.classList.add('hidden');
        downloadFileBtn.classList.remove('hidden');
    }
    
    function failProgress(errorMessage) {
        clearInterval(progressInterval);
        progressBar.style.background = 'var(--amc-orange)';
        progressText.textContent = `Error: ${errorMessage}`;
        timeEstimate.textContent = 'Please try again.';
        translateFileBtn.disabled = false;
        translateFileBtn.classList.remove('hidden');
        downloadFileBtn.classList.add('hidden');
    }
    
    function resetFileUI() {
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
        translatedFileBlob = null;
        translatedFileName = '';
    }

    // --- Event Handlers ---
    async function handleFileSubmit(e) {
        e.preventDefault();
        fileErrorMsg.classList.add('hidden');
        uploadArea.classList.remove('error');

        if (fileInput.files.length === 0) {
            fileErrorMsg.classList.remove('hidden');
            uploadArea.classList.add('error');
            setTimeout(() => { uploadArea.classList.remove('error'); }, 500);
            return;
        }

        const file = fileInput.files[0];
        const formData = new FormData(fileForm);
        
        translateFileBtn.disabled = true;
        downloadFileBtn.classList.add('hidden');
        startProgressSimulation(file.size);

        try {
            const response = await fetch(FILE_TRANSLATE_URL, { method: 'POST', body: formData });
            if (!response.ok) {
                let errorMsg = 'An unknown server error occurred.';
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || `HTTP error! status: ${response.status}`;
                } catch (jsonError) {
                    errorMsg = 'Server returned an invalid response. Please try again.';
                }
                throw new Error(errorMsg);
            }
            
            translatedFileBlob = await response.blob();
            const contentDisposition = response.headers.get('content-disposition');
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
                translatedFileName = (filenameMatch && filenameMatch.length > 1) ? filenameMatch[1] : `translated_${file.name}`;
            } else {
                translatedFileName = `translated_${file.name}`;
            }
            completeProgress();
        } catch (error) {
            failProgress(error.message);
        }
    }

    function handleFileDownload() {
        if (!translatedFileBlob || !translatedFileName) return;
        const downloadUrl = window.URL.createObjectURL(translatedFileBlob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = downloadUrl;
        a.download = translatedFileName;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
        a.remove();
        setTimeout(resetFileUI, 1500);
    }

    async function handleTextTranslation() {
        const text = sourceTextArea.value.trim();
        if (!text) {
            targetTextArea.value = '';
            return;
        }
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
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Server error');
            }
            const data = await response.json();
            targetTextArea.value = data.translated_text;
        } catch (error) {
            targetTextArea.value = `Error: ${error.message}`;
        }
    }

    // --- THE FIX IS HERE ---
    fileInput.addEventListener('change', () => {
        // This function now ONLY handles updating the UI when a file is selected.
        // The incorrect call to resetFileUI() has been removed.
        if (fileInput.files.length > 0) {
            // Hide any previous error messages when a new file is chosen.
            fileErrorMsg.classList.add('hidden');
            uploadArea.classList.remove('error');
            
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
    downloadFileBtn.addEventListener('click', handleFileDownload);
    
    let debounceTimer;
    sourceTextArea.addEventListener('input', () => { 
        clearTimeout(debounceTimer); 
        debounceTimer = setTimeout(handleTextTranslation, 500); 
    });
    copyBtn.addEventListener('click', () => { 
        navigator.clipboard.writeText(targetTextArea.value);
    });
    
    // --- Initial Setup ---
    populateLanguageSelectors();
    showSelectionScreen();
});
