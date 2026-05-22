const API_BASE = '';

async function _fetch(url, options = {}) {
    const res = await fetch(API_BASE + url, options);
    if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try {
            const err = await res.json();
            msg = err.detail || JSON.stringify(err);
        } catch {
            msg = await res.text() || msg;
        }
        throw new Error(msg);
    }
    if (res.status === 204) return null;
    return res.json();
}

async function uploadSpec(file) {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(API_BASE + '/api/upload', {
        method: 'POST',
        body: form,
    });
    if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { msg = (await res.json()).detail || msg; } catch {}
        throw new Error(msg);
    }
    return res.json();
}

async function generate(config) {
    return _fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
    });
}

async function getStatus(jobId) {
    return _fetch(`/api/status/${jobId}`);
}

function createEventSource(jobId) {
    return new EventSource(API_BASE + `/api/stream/${jobId}`);
}

function downloadAll(jobId) {
    window.location.href = API_BASE + `/api/download/${jobId}/all`;
}

function downloadDomain(jobId, domain) {
    window.location.href = API_BASE + `/api/download/${jobId}/${domain}`;
}

async function getHistory(limit = 50, offset = 0) {
    return _fetch(`/api/history?limit=${limit}&offset=${offset}`);
}

async function deleteHistory(recordId) {
    return _fetch(`/api/history/${recordId}`, { method: 'DELETE' });
}
