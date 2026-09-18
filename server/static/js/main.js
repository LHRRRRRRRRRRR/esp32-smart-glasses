// ===== State =====
let photos = [];
let lastUploadTime = 0;
let pollTimer = null;
let eventSource = null;

// ===== Init =====
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    loadConfig();
    loadPrompt();
    loadPhotos();
    connectSSE();
    startPolling();
});

// ===== Dark Mode =====
function initTheme() {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.body.classList.add('dark');
        updateThemeIcon();
    }
}

function toggleTheme() {
    document.body.classList.toggle('dark');
    localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
    updateThemeIcon();
}

function updateThemeIcon() {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    const isDark = document.body.classList.contains('dark');
    btn.querySelector('.icon').textContent = isDark ? '\u2600' : '\uD83C\uDF19';
    btn.querySelector('.label').textContent = isDark ? 'Light' : 'Dark';
}

// ===== SSE =====
function connectSSE() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource('/stream');
    
    eventSource.addEventListener('new_photo', (e) => {
        const ts = parseInt(e.data);
        if (ts > lastUploadTime) {
            lastUploadTime = ts;
            loadPhotos();
        }
    });
    
    eventSource.addEventListener('photo_deleted', (e) => {
        loadPhotos();
    });
    
    eventSource.onerror = () => {
        setTimeout(() => {
            if (eventSource.readyState === EventSource.CLOSED) {
                connectSSE();
            }
        }, 5000);
    };
}

// ===== Polling (fallback) =====
function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(checkNewPhoto, 5000);
}

function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function checkNewPhoto() {
    try {
        const resp = await fetch('/has_new_photo?time=' + lastUploadTime);
        const data = await resp.json();
        if (data.has_new) {
            lastUploadTime = data.last_upload;
            loadPhotos();
        }
    } catch (e) {
        // silent fail
    }
}

// ===== Load Photos =====
async function loadPhotos() {
    try {
        const resp = await fetch('/photos');
        const data = await resp.json();
        photos = data.photos;
        lastUploadTime = data.last_upload;
        renderPhotos();
    } catch (e) {
        showToast('Failed to load photos', 'error');
    }
}

function renderPhotos() {
    const container = document.getElementById('photosContainer');
    if (!photos || photos.length === 0) {
        container.innerHTML = '' +
            '<div class="empty-state">' +
                '<div class="icon">\uD83D\uDCF7</div>' +
                '<div class="title">No Photos Yet</div>' +
                '<div class="desc">Press the BOOT button on your ESP32 to capture and identify.</div>' +
            '</div>';
        return;
    }
    
    container.innerHTML = '<div class="photos-grid">' + photos.map((p, i) => {
        const isNew = p.timestamp >= lastUploadTime - 2000;
        const modeLabel = p.mode === 'ocr' ? 'OCR' : 'Scene';
        const copyBtn = p.mode === 'ocr'
            ? '<button class="btn-icon" title="Copy text" onclick="copyText(\'' + esc(p.text) + '\')">\uD83D\uDCCB</button>'
            : '';
        return '' +
            '<div class="photo-card' + (isNew ? ' new-highlight' : '') + '" data-filename="' + p.filename + '">' +
                '<div class="photo-header">' +
                    '<div class="photo-header-left">' +
                        '<span class="photo-index">#' + (i + 1) + '</span>' +
                        '<span class="photo-mode-badge ' + p.mode + '">' + modeLabel + '</span>' +
                    '</div>' +
                    '<span class="photo-time">' + p.time + '</span>' +
                '</div>' +
                '<img class="photo-image" src="/photo/' + p.filename + '" ' +
                     'alt="Photo" loading="lazy" ' +
                     'onclick="openLightbox(\'/photo/' + p.filename + '\')">' +
                '<div class="photo-content">' +
                    '<div class="photo-text">' + escapeHtml(p.text) + '</div>' +
                '</div>' +
                '<div class="photo-actions">' +
                    copyBtn +
                    '<button class="btn-icon" title="Delete photo" onclick="deletePhoto(\'' + esc(p.filename) + '\')">\uD83D\uDDD1</button>' +
                '</div>' +
            '</div>';
    }).join('') + '</div>';
}

function esc(s) {
    return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ===== Copy Text =====
async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard', 'success');
    } catch (e) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast('Copied to clipboard', 'success');
    }
}

// ===== Delete Photo =====
async function deletePhoto(filename) {
    if (!confirm('Delete this photo?')) return;
    try {
        const resp = await fetch('/photo/' + encodeURIComponent(filename), { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            showToast('Deleted', 'success');
            loadPhotos();
        } else {
            showToast(data.error || 'Delete failed', 'error');
        }
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

// ===== Lightbox =====
function openLightbox(src) {
    const lb = document.getElementById('lightbox');
    const img = document.getElementById('lightboxImg');
    img.src = src;
    lb.classList.add('show');
}

function closeLightbox(e) {
    if (e && e.target !== e.currentTarget) return;
    const lb = document.getElementById('lightbox');
    lb.classList.remove('show');
}

// ===== Config =====
async function loadConfig() {
    try {
        const resp = await fetch('/get_config');
        const data = await resp.json();
        document.getElementById('apiKeyInput').placeholder = data.api_key_set ? 'API Key (set)' : 'Enter API Key';
        document.getElementById('modelSelect').value = data.model;
        if (data.available_models) {
            const sel = document.getElementById('modelSelect');
            sel.innerHTML = data.available_models.map(m => 
                '<option value="' + m.name + '">' + m.name + ' (' + m.description + ')</option>'
            ).join('');
        }
    } catch (e) {
        console.error('Load config failed:', e);
    }
}

async function saveConfig() {
    const apiKey = document.getElementById('apiKeyInput').value.trim();
    const model = document.getElementById('modelSelect').value;
    try {
        const resp = await fetch('/set_config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey || undefined, model })
        });
        const data = await resp.json();
        if (data.success) {
            showStatus('configStatus', 'Saved', 'success');
            document.getElementById('apiKeyInput').value = '';
            document.getElementById('apiKeyInput').placeholder = 'API Key (set)';
        } else {
            showStatus('configStatus', data.error || 'Save failed', 'error');
        }
    } catch (e) {
        showStatus('configStatus', 'Save failed: ' + e.message, 'error');
    }
}

async function resetConfig() {
    try {
        const resp = await fetch('/reset_config');
        const data = await resp.json();
        if (data.success) {
            document.getElementById('modelSelect').value = data.model;
            document.getElementById('apiKeyInput').value = '';
            document.getElementById('apiKeyInput').placeholder = 'Enter API Key';
            showStatus('configStatus', 'Reset to defaults', 'info');
        }
    } catch (e) {
        showStatus('configStatus', 'Reset failed', 'error');
    }
}

// ===== Prompt =====
async function loadPrompt() {
    try {
        const resp = await fetch('/get_prompt');
        const data = await resp.json();
        document.getElementById('promptInput').value = data.prompt;
    } catch (e) {
        console.error('Load prompt failed:', e);
    }
}

async function savePrompt() {
    const prompt = document.getElementById('promptInput').value;
    try {
        const resp = await fetch('/set_prompt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt })
        });
        const data = await resp.json();
        if (data.success) {
            showStatus('promptStatus', 'Prompt saved', 'success');
        } else {
            showStatus('promptStatus', data.error || 'Save failed', 'error');
        }
    } catch (e) {
        showStatus('promptStatus', 'Save failed', 'error');
    }
}

async function resetPrompt() {
    try {
        const resp = await fetch('/reset_prompt');
        const data = await resp.json();
        if (data.success) {
            document.getElementById('promptInput').value = data.prompt;
            showStatus('promptStatus', 'Reset to default', 'info');
        }
    } catch (e) {
        showStatus('promptStatus', 'Reset failed', 'error');
    }
}

// ===== Presets =====
const PROMPT_PRESETS = {
    ocr: 'You are a smart glasses assistant. If there is text in the image, return: OCR:<content>. If no text, return: SCENE:<one sentence description (under 20 words)>. Do not explain, output directly.',
    scene: 'You are a smart glasses assistant. Describe the scene in one short sentence (under 20 words). Format: SCENE:<description>. Do not explain.',
    describe: 'You are a smart glasses assistant. Describe everything you see in detail: objects, people, text, colors, environment. Be thorough but concise.',
    qa: 'You are a smart glasses assistant. Answer questions about what you see in the image. Be helpful and concise.'
};

function loadPreset(type) {
    const prompt = PROMPT_PRESETS[type];
    if (prompt) {
        document.getElementById('promptInput').value = prompt;
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.preset-btn').forEach(b => {
            if (b.getAttribute('onclick').indexOf("'" + type + "'") >= 0) {
                b.classList.add('active');
            }
        });
    }
}

// ===== Helpers =====
function showStatus(id, msg, type) {
    const el = document.getElementById(id);
    el.textContent = msg;
    el.className = 'status-message show status-' + type;
    setTimeout(() => { el.classList.remove('show'); }, 3000);
}

function showToast(msg, type) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

// ===== Keyboard Shortcuts =====
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
});
