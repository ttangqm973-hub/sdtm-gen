/* State */
const state = {
    currentView: 'upload',
    uploadId: null,
    jobId: null,
    detectedDomains: [],
    selectedDomains: new Set(),
    statusTimer: null,
    eventSource: null,
    jobResult: null,
};

/* DOM refs */
const views = {
    upload: document.getElementById('view-upload'),
    progress: document.getElementById('view-progress'),
    history: document.getElementById('view-history'),
};
const tabs = document.querySelectorAll('.nav-tab');
const toastContainer = document.getElementById('toast-container');

/* Navigation */
tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const view = tab.dataset.view;
        switchView(view);
    });
});

function switchView(viewName) {
    state.currentView = viewName;
    Object.values(views).forEach(el => el.classList.remove('active'));
    views[viewName].classList.add('active');
    tabs.forEach(t => t.classList.toggle('active', t.dataset.view === viewName));

    if (viewName === 'history') renderHistoryView();
    if (viewName === 'progress' && state.jobId) renderProgressView();
}

/* Toast */
function showToast(message, type = 'success') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    toastContainer.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

/* Upload view */
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadInfo = document.getElementById('upload-info');
const uploadFilename = document.getElementById('upload-filename');
const uploadDomains = document.getElementById('upload-domains');
const configCard = document.getElementById('config-card');
const domainList = document.getElementById('domain-list');
const btnSelectAll = document.getElementById('btn-select-all');
const btnSelectNone = document.getElementById('btn-select-none');
const btnGenerate = document.getElementById('btn-generate');

dropZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
    if (fileInput.files.length) handleFile(fileInput.files[0]);
});

dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});

async function handleFile(file) {
    try {
        const data = await uploadSpec(file);
        state.uploadId = data.upload_id;
        state.detectedDomains = data.domains_detected || [];
        state.selectedDomains = new Set(state.detectedDomains);

        uploadFilename.textContent = data.filename;
        uploadDomains.textContent = state.detectedDomains.join(', ') || '无';
        uploadInfo.classList.remove('hidden');
        configCard.classList.remove('hidden');

        renderDomainList();
        btnGenerate.disabled = state.selectedDomains.size === 0;
        showToast('上传成功');
    } catch (err) {
        showToast('上传失败: ' + err.message, 'error');
    }
}

function renderDomainList() {
    domainList.innerHTML = '';
    state.detectedDomains.forEach(domain => {
        const tag = document.createElement('span');
        tag.className = 'domain-tag' + (state.selectedDomains.has(domain) ? ' selected' : '');
        tag.textContent = domain;
        tag.addEventListener('click', () => {
            if (state.selectedDomains.has(domain)) {
                state.selectedDomains.delete(domain);
                tag.classList.remove('selected');
            } else {
                state.selectedDomains.add(domain);
                tag.classList.add('selected');
            }
            btnGenerate.disabled = state.selectedDomains.size === 0;
        });
        domainList.appendChild(tag);
    });
}

btnSelectAll.addEventListener('click', () => {
    state.detectedDomains.forEach(d => state.selectedDomains.add(d));
    renderDomainList();
    btnGenerate.disabled = false;
});

btnSelectNone.addEventListener('click', () => {
    state.selectedDomains.clear();
    renderDomainList();
    btnGenerate.disabled = true;
});

btnGenerate.addEventListener('click', async () => {
    if (!state.uploadId || state.selectedDomains.size === 0) return;

    const macroRefs = document.getElementById('global-macro-refs').value;
    const config = {
        upload_id: state.uploadId,
        domains: Array.from(state.selectedDomains),
        study_name: document.getElementById('study-name').value || 'STUDY',
        rag_enabled: document.getElementById('rag-enabled').checked,
        rag_mock: document.getElementById('rag-mock').checked,
        lint_enabled: document.getElementById('lint-enabled').checked,
        kb_path: document.getElementById('kb-path').value || undefined,
        global_macro_refs: macroRefs ? macroRefs.split(',').map(s => s.trim()).filter(Boolean) : [],
    };

    try {
        btnGenerate.disabled = true;
        btnGenerate.textContent = '提交中...';
        const res = await generate(config);
        state.jobId = res.job_id;
        state.jobResult = null;
        showToast('任务已提交: ' + res.job_id);
        switchView('progress');
    } catch (err) {
        showToast('提交失败: ' + err.message, 'error');
    } finally {
        btnGenerate.disabled = false;
        btnGenerate.textContent = '开始生成';
    }
});

/* Progress view */
const progressStatus = document.getElementById('progress-status');
const progressText = document.getElementById('progress-text');
const progressFill = document.getElementById('progress-fill');
const progressTime = document.getElementById('progress-time');
const domainStatusBody = document.getElementById('domain-status-body');
const downloadCard = document.getElementById('download-card');
const btnDownloadAll = document.getElementById('btn-download-all');
const downloadLinks = document.getElementById('download-links');

function renderProgressView() {
    if (!state.jobId) {
        progressStatus.textContent = '无任务';
        progressStatus.className = 'status-badge status-pending';
        progressText.textContent = '-';
        progressFill.style.width = '0%';
        domainStatusBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9ca3af">请先提交生成任务</td></tr>';
        downloadCard.classList.add('hidden');
        return;
    }

    // cleanup old timers
    if (state.statusTimer) { clearInterval(state.statusTimer); state.statusTimer = null; }
    if (state.eventSource) { state.eventSource.close(); state.eventSource = null; }

    pollStatus();
    state.statusTimer = setInterval(pollStatus, 2000);

    // SSE as supplementary
    try {
        const es = createEventSource(state.jobId);
        state.eventSource = es;
        es.onmessage = e => {
            try {
                const ev = JSON.parse(e.data);
                if (ev.event === 'start') {
                    progressStatus.textContent = 'running';
                    progressStatus.className = 'status-badge status-running';
                } else if (ev.event === 'progress') {
                    progressText.textContent = `${ev.completed} / ${ev.total}`;
                    const pct = ev.total > 0 ? Math.round((ev.completed / ev.total) * 100) : 0;
                    progressFill.style.width = pct + '%';
                } else if (ev.event === 'complete' || ev.event === 'error') {
                    pollStatus();
                }
            } catch {}
        };
        es.onerror = () => { if (state.eventSource) state.eventSource.close(); };
    } catch {}
}

async function pollStatus() {
    if (!state.jobId) return;
    try {
        const data = await getStatus(state.jobId);
        updateProgressUI(data);
        if (data.status === 'success' || data.status === 'failed') {
            if (state.statusTimer) { clearInterval(state.statusTimer); state.statusTimer = null; }
            if (state.eventSource) { state.eventSource.close(); state.eventSource = null; }
        }
    } catch (err) {
        showToast('获取状态失败: ' + err.message, 'error');
    }
}

function updateProgressUI(data) {
    progressStatus.textContent = data.status;
    progressStatus.className = 'status-badge status-' + data.status;
    progressText.textContent = `${data.completed_domains || 0} / ${data.total_domains || 0}`;
    const pct = data.progress !== undefined ? Math.round(data.progress * 100) : 0;
    progressFill.style.width = pct + '%';
    progressTime.textContent = data.elapsed_seconds != null ? `耗时: ${data.elapsed_seconds.toFixed(1)}s` : '';

    domainStatusBody.innerHTML = '';
    if (data.details && data.details.length) {
        data.details.forEach(d => {
            const tr = document.createElement('tr');
            const errCell = d.error ? `<span style="color:#dc2626;font-size:0.75rem">${escapeHtml(d.error)}</span>` : '-';
            const actions = d.status === 'success' && d.output_file
                ? `<a href="#" class="download-link" data-domain="${escapeHtml(d.domain)}">下载</a>`
                : '-';
            tr.innerHTML = `
                <td>${escapeHtml(d.domain)}</td>
                <td><span class="status-badge status-${d.status}">${d.status}</span></td>
                <td>-</td>
                <td>${errCell}</td>
                <td>${actions}</td>
            `;
            domainStatusBody.appendChild(tr);
        });

        // bind download clicks
        domainStatusBody.querySelectorAll('a[data-domain]').forEach(a => {
            a.addEventListener('click', e => {
                e.preventDefault();
                downloadDomain(state.jobId, a.dataset.domain);
            });
        });
    } else if (data.status === 'failed' && data.error) {
        domainStatusBody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#dc2626">${escapeHtml(data.error)}</td></tr>`;
    } else if (data.status === 'success' || data.status === 'failed') {
        domainStatusBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#dc2626">未生成任何 Domain，请检查 SPEC 文件格式</td></tr>';
    } else {
        domainStatusBody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9ca3af">等待中...</td></tr>';
    }

    if (data.status === 'success' || data.status === 'failed') {
        downloadCard.classList.remove('hidden');
        if (data.status === 'success') {
            downloadLinks.innerHTML = '';
            (data.details || []).forEach(d => {
                if (d.status !== 'success') return;
                const a = document.createElement('a');
                a.className = 'download-link';
                a.textContent = d.domain + '.sas';
                a.href = '#';
                a.addEventListener('click', e => {
                    e.preventDefault();
                    downloadDomain(state.jobId, d.domain);
                });
                downloadLinks.appendChild(a);
            });
        }
    } else {
        downloadCard.classList.add('hidden');
    }
}

btnDownloadAll.addEventListener('click', () => {
    if (state.jobId) downloadAll(state.jobId);
});

/* History view */
const historyBody = document.getElementById('history-body');
const historyEmpty = document.getElementById('history-empty');

async function renderHistoryView() {
    try {
        const data = await getHistory();
        historyBody.innerHTML = '';
        if (!data.items || data.items.length === 0) {
            historyEmpty.classList.remove('hidden');
            return;
        }
        historyEmpty.classList.add('hidden');

        data.items.forEach(item => {
            const tr = document.createElement('tr');
            const domains = (item.domains || []).join(', ');
            tr.innerHTML = `
                <td>${escapeHtml(item.study_name)}</td>
                <td>${escapeHtml(domains)}</td>
                <td><span class="status-badge status-${item.status}">${item.status}</span></td>
                <td>${formatTime(item.generated_at)}</td>
                <td>
                    <button class="btn-sm btn-delete" data-id="${item.id}">删除</button>
                </td>
            `;
            historyBody.appendChild(tr);
        });

        historyBody.querySelectorAll('.btn-delete').forEach(btn => {
            btn.addEventListener('click', async () => {
                try {
                    await deleteHistory(btn.dataset.id);
                    showToast('已删除');
                    renderHistoryView();
                } catch (err) {
                    showToast('删除失败: ' + err.message, 'error');
                }
            });
        });
    } catch (err) {
        showToast('加载历史记录失败: ' + err.message, 'error');
    }
}

/* Utils */
function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function formatTime(iso) {
    if (!iso) return '-';
    try {
        const d = new Date(iso);
        return d.toLocaleString('zh-CN');
    } catch {
        return iso;
    }
}
