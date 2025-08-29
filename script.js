document.addEventListener('DOMContentLoaded', () => {
    const selectionScreen = document.getElementById('selection-screen');
    const fileWorkspace = document.getElementById('file-translation');
    const textWorkspace = document.getElementById('text-translation');
    const openDocButton = document.getElementById('open-doc-workspace');
    const openTextButton = document.getElementById('open-text-workspace');
    const backButtons = document.querySelectorAll('.back-btn');

    function openWorkspace(workspaceId) {
        selectionScreen.style.display = 'none';
        fileWorkspace.style.display = 'none';
        textWorkspace.style.display = 'none';
        if (workspaceId === 'file-translation') {
            fileWorkspace.style.display = 'flex';
        } else {
            textWorkspace.style.display = 'flex';
        }
    }

    function showSelectionScreen() {
        fileWorkspace.style.display = 'none';
        textWorkspace.style.display = 'none';
        selectionScreen.style.display = 'flex';
    }

    openDocButton.addEventListener('click', () => openWorkspace('file-translation'));
    openTextButton.addEventListener('click', () => openWorkspace('text-translation'));
    backButtons.forEach(button => button.addEventListener('click', showSelectionScreen));

    const FILE_TRANSLATE_URL = '/translate-file';
    const TEXT_TRANSLATE_URL = '/translate-text';

    const fileForm = document.getElementById('file-upload-form');
    const fileInput = document.getElementById('file-input');
    const fileNameDisplay = document.getElementById('file-name-display');
    const uploadArea = document.getElementById('upload-area');
    const translateFileBtn = document.getElementById('translate-file-btn');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const timeEstimate = document.getElementById('time-estimate');
    const sourceTextArea = document.getElementById('source-text');
    const targetTextArea = document.getElementById('target-text');
    const copyBtn = document.getElementById('copy-btn');
    
    let progressInterval = null;

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
    
    function startProgressSimulation(fileSize) {
        const estimatedDuration = 10 + (fileSize / 1024 / 1024) * 15;
        let progress = 0;
        let elapsed = 0;
        progressContainer.style.display = 'block';
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
        timeEstimate.textContent = 'Download starting...';
    }
    
    function failProgress(errorMessage) {
        clearInterval(progressInterval);
        progressBar.style.background = 'var(--amc-orange)';
        progressText.textContent = `Error: ${errorMessage}`;
        timeEstimate.textContent = 'Please try again.';
    }
    
    function resetFileUI() {
        fileInput.value = ''; 
        const enText = fileNameDisplay.querySelector('.en b');
        const arText = fileNameDisplay.querySelector('.ar b');
        if(enText) enText.textContent = 'Click to upload';
        if(arText) arText.textContent = 'انقر للرفع';
        progressContainer.style.display = 'none';
    }

    async function handleFileSubmit(e) {
        e.preventDefault();
        if (fileInput.files.length === 0) { alert('Please select a file first.'); return; }
        const file = fileInput.files[0];
        const formData = new FormData(fileForm);
        translateFileBtn.disabled = true;
        startProgressSimulation(file.size);
        try {
            const response = await fetch(FILE_TRANSLATE_URL, { method: 'POST', body: formData });
            if (!response.ok) {
                // Try to parse error JSON, but have a fallback
                let errorMsg = 'An unknown server error occurred.';
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || `HTTP error! status: ${response.status}`;
                } catch (jsonError) {
                    // This catches the "Unexpected token '<'" error
                    errorMsg = 'Server returned an invalid response. Please try again.';
                }
                throw new Error(errorMsg);
            }
            completeProgress();
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            const contentDisposition = response.headers.get('content-disposition');
            let filename = `translated_${file.name}`;
             if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
                if (filenameMatch && filenameMatch.length > 1) {
                    filename = filenameMatch[1];
                }
            }
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(downloadUrl);
            setTimeout(resetFileUI, 2000);
        } catch (error) {
            failProgress(error.message);
        } finally {
            translateFileBtn.disabled = false;
        }
    }

    async function handleTextTranslation() {
        const text = sourceTextArea.value.trim();
        if (!text) return;
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
                let errorMsg = 'An unknown server error occurred.';
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || `HTTP error! status: ${response.status}`;
                } catch (jsonError) {
                    errorMsg = 'Server returned an invalid response. Please try again.';
                }
                throw new Error(errorMsg);
            }
            const data = await response.json();
            targetTextArea.value = data.translated_text;
        } catch (error) {
            targetTextArea.value = `Error: ${error.message}`;
        }
    }

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const enText = fileNameDisplay.querySelector('.en b');
            const arText = fileNameDisplay.querySelector('.ar b');
            if(enText) enText.textContent = file.name;
            if(arText) arText.textContent = '';
            progressContainer.style.display = 'none';
        }
    });

    uploadArea.addEventListener('dragenter', (e) => { e.preventDefault(); e.stopPropagation(); uploadArea.classList.add('dragover'); });
    uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); e.stopPropagation(); uploadArea.classList.add('dragover'); });
    uploadArea.addEventListener('dragleave', (e) => { e.preventDefault(); e.stopPropagation(); uploadArea.classList.remove('dragover'); });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault(); e.stopPropagation();
        uploadArea.classList.remove('dragover');
        fileInput.files = e.dataTransfer.files;
        fileInput.dispatchEvent(new Event('change'));
    });

    fileForm.addEventListener('submit', handleFileSubmit);
    let debounceTimer;
    sourceTextArea.addEventListener('input', () => { clearTimeout(debounceTimer); debounceTimer = setTimeout(handleTextTranslation, 500); });
    copyBtn.addEventListener('click', () => { navigator.clipboard.writeText(targetTextArea.value); });
    
    populateLanguageSelectors();
    
    showSelectionScreen();
});
