const root = document.documentElement;
const os = document.getElementById('os');
const state = {
    gestureLocked: false,
    gestureAxis: '',
    unlocked: false,
    controlOpen: false,
    appOpen: false,
    appId: '',
    pageIndex: 0,
    startX: 0,
    startY: 0,
    currentY: 0,
    startTime: 0,
    draggingPanel: false,
    draggingUnlock: false,
    gestureMode: '',
    lastPanelTranslate: -1,
    sleeping: false,
    idleTimeoutMs: 45000,
    idleTimer: null,
    lastActivitySentAt: 0,
    cameraPoll: null,
    browser: null,
    recentApps: [],
    appSwitcherOpen: false,
    homeEditMode: false,
    homeEditTimer: null,
    selectedHomeApp: null
};

const lockscreen = document.getElementById('lockscreen');
const homeScreen = document.getElementById('homeScreen');
const homeShell = document.getElementById('homeShell');
const pages = document.getElementById('pages');
const dots = Array.from(document.querySelectorAll('.dot'));
const controlCenter = document.getElementById('controlCenter');
const ccSheet = document.getElementById('ccSheet');
const ccBackdrop = document.getElementById('ccBackdrop');
const appView = document.getElementById('appView');
const appBody = document.getElementById('appBody');
const appTitle = document.getElementById('appTitle');
const closeAppBtn = document.getElementById('closeAppBtn');
const brightnessRange = document.getElementById('brightnessRange');
const brightnessValue = document.getElementById('brightnessValue');
const sleepButton = document.getElementById('sleepButton');
const sleepScreen = document.getElementById('sleepScreen');
const sleepTime = document.getElementById('sleepTime');
const toggles = Array.from(document.querySelectorAll('.toggle'));

closeAppBtn.textContent = 'x';

const appTitles = {
    phone: 'Phone',
    messages: 'Messages',
    browser: 'Browser',
    camera: 'Camera',
    gallery: 'Gallery',
    music: 'Music',
    maps: 'Maps',
    mail: 'Mail',
    notes: 'Notes',
    clock: 'Clock',
    files: 'Files',
    store: 'Store',
    settings: 'Settings'
};

const appTop = document.querySelector('.app-top');

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function saveHomeLayout() {
    const pagesData = Array.from(document.querySelectorAll('.page')).map((page) =>
        Array.from(page.querySelectorAll('.app')).map((app) => app.dataset.app)
    );
    try {
        localStorage.setItem('unlim8ted.home.layout', JSON.stringify(pagesData));
    } catch (_error) {
    }
}

function restoreHomeLayout() {
    try {
        const raw = localStorage.getItem('unlim8ted.home.layout');
        if (!raw) return;
        const layout = JSON.parse(raw);
        if (!Array.isArray(layout)) return;
        const pageNodes = Array.from(document.querySelectorAll('.page'));
        const appNodes = new Map(Array.from(document.querySelectorAll('.app')).map((node) => [node.dataset.app, node]));
        layout.forEach((pageLayout, index) => {
            const page = pageNodes[index];
            if (!page || !Array.isArray(pageLayout)) return;
            pageLayout.forEach((appId) => {
                const node = appNodes.get(appId);
                if (node) page.appendChild(node);
            });
        });
    } catch (_error) {
    }
}

function enterHomeEditMode(appNode = null) {
    state.homeEditMode = true;
    os.classList.add('home-edit');
    state.selectedHomeApp = appNode || null;
    document.querySelectorAll('.app').forEach((item) => item.classList.toggle('selected-edit', item === appNode));
}

function exitHomeEditMode() {
    state.homeEditMode = false;
    state.selectedHomeApp = null;
    os.classList.remove('home-edit');
    document.querySelectorAll('.app').forEach((item) => item.classList.remove('selected-edit'));
    if (state.homeEditTimer) {
        clearTimeout(state.homeEditTimer);
        state.homeEditTimer = null;
    }
}

function swapHomeApps(first, second) {
    if (!first || !second || first === second) return;
    const firstMarker = document.createElement('div');
    const secondMarker = document.createElement('div');
    first.parentNode.insertBefore(firstMarker, first);
    second.parentNode.insertBefore(secondMarker, second);
    firstMarker.parentNode.replaceChild(second, firstMarker);
    secondMarker.parentNode.replaceChild(first, secondMarker);
    saveHomeLayout();
}

function rememberRecentApp(appId, payload = null) {
    const title = payload?.title || appTitles[appId] || 'App';
    state.recentApps = state.recentApps.filter((item) => item.id !== appId);
    state.recentApps.unshift({ id: appId, title });
    state.recentApps = state.recentApps.slice(0, 8);
}

function renderAppSwitcher() {
    if (!state.appOpen) return '';
    const items = state.recentApps.length ? state.recentApps : [{ id: state.appId, title: appTitles[state.appId] || 'App' }];
    const cards = items.map((item) => `
        <button type="button" data-switch-app="${escapeHtml(item.id)}" style="display:grid;gap:6px;width:100%;text-align:left;padding:14px;border-radius:20px;border:1px solid rgba(140,186,255,.12);background:${item.id === state.appId ? 'rgba(155,205,255,.16)' : 'rgba(255,255,255,.04)'};color:#eef3ff;">
            <span style="font-size:15px;font-weight:800;">${escapeHtml(item.title)}</span>
            <span style="font-size:11px;color:#91a8ca;text-transform:uppercase;letter-spacing:.12em;">${escapeHtml(item.id)}</span>
        </button>
    `).join('');
    return `
        <div id="appSwitcherSheet" style="position:absolute;inset:0;display:none;align-items:flex-end;justify-content:center;padding:24px 16px calc(var(--safe-bottom) + 20px);background:rgba(5,9,16,.52);backdrop-filter:blur(14px);z-index:12;">
            <div style="width:min(560px,100%);display:grid;gap:12px;">
                <div style="display:flex;justify-content:space-between;align-items:center;padding:0 4px;">
                    <div style="font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#93a9ca;">Open Apps</div>
                    <button type="button" id="appSwitcherExit" style="height:34px;padding:0 14px;border-radius:17px;border:1px solid rgba(140,186,255,.12);background:rgba(100,145,255,.08);color:#eef3ff;">Exit App</button>
                </div>
                <div style="display:grid;gap:10px;">${cards}</div>
            </div>
        </div>
    `;
}

function ensureAppSwitcher() {
    let node = document.getElementById('appSwitcherSheet');
    if (!node) {
        appView.insertAdjacentHTML('beforeend', renderAppSwitcher());
        node = document.getElementById('appSwitcherSheet');
    } else {
        node.outerHTML = renderAppSwitcher();
        node = document.getElementById('appSwitcherSheet');
    }
    document.querySelectorAll('[data-switch-app]').forEach((button) => {
        button.addEventListener('click', async () => {
            closeAppSwitcher();
            await openApp(button.dataset.switchApp || '');
        });
    });
    document.getElementById('appSwitcherExit')?.addEventListener('click', () => {
        closeAppSwitcher();
        closeApp();
    });
    node?.addEventListener('click', (event) => {
        if (event.target?.id === 'appSwitcherSheet') closeAppSwitcher();
    });
    return node;
}

function openAppSwitcher() {
    if (!state.appOpen) return;
    state.appSwitcherOpen = true;
    const node = ensureAppSwitcher();
    if (node) node.style.display = 'flex';
}

function closeAppSwitcher() {
    state.appSwitcherOpen = false;
    const node = document.getElementById('appSwitcherSheet');
    if (node) node.style.display = 'none';
}

async function requestJson(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
            ...options
        });
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) return await response.json();
    } catch (error) {
        return null;
    }
    return null;
}

function updateTime() {
    const now = new Date();
    const time = now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    const date = now.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
    document.getElementById('sbTime').textContent = time;
    document.getElementById('lockClock').textContent = time;
    document.getElementById('lockDate').textContent = date;
    document.getElementById('ccTime').textContent = time;
    sleepTime.textContent = time;
}

function setPanelProgress(progress) {
    const clamped = Math.max(0, Math.min(1, progress));
    root.style.setProperty('--panel-progress', clamped.toFixed(4));
    homeShell.style.transform = `translateY(${clamped * 18}px) scale(${1 - clamped * 0.035})`;
    homeShell.style.filter = `blur(${clamped * 1.4}px)`;
}

function setPanelTranslate(translatePercent) {
    const value = Math.max(-100, Math.min(0, translatePercent));
    state.lastPanelTranslate = value;
    ccSheet.style.transform = `translateY(${value}%)`;
    setPanelProgress((100 + value) / 100);
}

function unlock() {
    if (state.unlocked) return;
    state.unlocked = true;
    lockscreen.classList.add('unlocked');
    homeScreen.classList.add('unlocked');
    lockscreen.style.transform = '';
    homeScreen.style.transform = '';
}

function lockDevice() {
    if (state.appOpen) closeApp();
    closeControlCenter();
    state.unlocked = false;
    lockscreen.classList.remove('unlocked');
    homeScreen.classList.remove('unlocked');
    lockscreen.style.transition = '';
    homeScreen.style.transition = '';
    lockscreen.style.transform = 'translateY(0)';
    homeScreen.style.transform = 'translateY(100%)';
}

function openControlCenter() {
    if (!state.unlocked || state.appOpen || state.sleeping) return;
    state.controlOpen = true;
    controlCenter.classList.add('visible');
    controlCenter.setAttribute('aria-hidden', 'false');
    ccSheet.style.transition = 'transform 520ms cubic-bezier(.22,1,.36,1)';
    setPanelTranslate(0);
}

function closeControlCenter() {
    if (!state.controlOpen && !controlCenter.classList.contains('visible')) return;
    state.controlOpen = false;
    ccSheet.style.transition = 'transform 420ms cubic-bezier(.32,.72,0,1)';
    setPanelTranslate(-100);
    setTimeout(() => {
        if (!state.controlOpen) {
            controlCenter.classList.remove('visible');
            controlCenter.setAttribute('aria-hidden', 'true');
            setPanelProgress(0);
            homeShell.style.transform = '';
            homeShell.style.filter = '';
        }
    }, 220);
}

function setActivePage(index) {
    state.pageIndex = index;
    dots.forEach((dot, i) => dot.classList.toggle('active', i === index));
}

function applySystemState(system) {
    if (!system) return;
    state.sleeping = !!system.sleeping;
    state.idleTimeoutMs = Math.max(10000, (system.idle_timeout_sec || 45) * 1000);
    const percent = Math.round((system.brightness || 0.68) * 100);
    brightnessRange.value = percent;
    brightnessValue.textContent = `${percent}%`;
    toggles.forEach((toggle) => {
        const action = toggle.dataset.action;
        toggle.classList.toggle('active', !!system.toggles?.[action]);
    });
    document.querySelectorAll('.app').forEach((app) => {
        const appId = app.dataset.app;
        const count = Number(system.badges?.[appId] || 0);
        let badge = app.querySelector('.app-badge');
        if (count > 0) {
            if (!badge) {
                badge = document.createElement('div');
                badge.className = 'app-badge';
                badge.style.position = 'absolute';
                badge.style.top = '-4px';
                badge.style.right = '10px';
                badge.style.minWidth = '18px';
                badge.style.height = '18px';
                badge.style.padding = '0 6px';
                badge.style.borderRadius = '999px';
                badge.style.background = '#ff564f';
                badge.style.color = '#fff';
                badge.style.fontSize = '11px';
                badge.style.fontWeight = '800';
                badge.style.display = 'grid';
                badge.style.placeItems = 'center';
                app.appendChild(badge);
            }
            badge.textContent = String(count);
        } else if (badge) {
            badge.remove();
        }
    });
    os.classList.toggle('sleeping', state.sleeping);
    sleepScreen.classList.toggle('visible', state.sleeping);
    sleepScreen.setAttribute('aria-hidden', String(!state.sleeping));
}

async function syncSystemState() {
    const payload = await requestJson('/api/state');
    if (payload?.system) applySystemState(payload.system);
}

function scheduleIdleSleep() {
    if (state.idleTimer) clearTimeout(state.idleTimer);
    if (state.sleeping) return;
    state.idleTimer = window.setTimeout(() => sleepSystem('idle'), state.idleTimeoutMs);
}

async function reportActivity(force = false) {
    const now = Date.now();
    if (!force && now - state.lastActivitySentAt < 1200) return;
    state.lastActivitySentAt = now;
    const payload = await requestJson('/api/system/activity', { method: 'POST', body: '{}' });
    if (payload?.system) applySystemState(payload.system);
}

function noteActivity(force = false) {
    if (state.sleeping && !force) return;
    scheduleIdleSleep();
    reportActivity(force);
}

async function sendSystemCommand(action, extra = {}) {
    const payload = await requestJson('/cmd', {
        method: 'POST',
        body: JSON.stringify({ action, ...extra })
    });
    if (payload?.system) applySystemState(payload.system);
    return payload;
}

async function setBrightness(percent) {
    brightnessValue.textContent = `${percent}%`;
    const payload = await requestJson('/api/system/brightness', {
        method: 'POST',
        body: JSON.stringify({ brightness: percent / 100 })
    });
    if (payload?.system) applySystemState(payload.system);
}

async function sleepSystem(reason = 'manual') {
    if (state.sleeping) return;
    stopCameraPreview(true);
    lockDevice();
    closeControlCenter();
    const payload = await requestJson('/api/system/sleep', {
        method: 'POST',
        body: JSON.stringify({ reason })
    });
    if (payload?.system) applySystemState(payload.system);
}

async function wakeSystem(reason = 'tap') {
    const payload = await requestJson('/api/system/wake', {
        method: 'POST',
        body: JSON.stringify({ reason })
    });
    if (payload?.system) applySystemState(payload.system);
    lockDevice();
    noteActivity(true);
}

async function runAppAction(action, payload = {}) {
    if (!state.appId || state.appId === 'camera') return;
    noteActivity(true);
    const response = await requestJson(`/api/apps/${encodeURIComponent(state.appId)}/action`, {
        method: 'POST',
        body: JSON.stringify({ action, payload })
    });
    if (response?.system) applySystemState(response.system);
    if (response?.app) {
        renderAppPayload(response.app, state.appId);
    }
}

function renderHtmlApp(payload, appId) {
    const html = payload?.html || `
        <div class="content-card">
            <div class="content-title">${escapeHtml(appTitles[appId] || 'App')}</div>
            <div class="content-text">No app content is available for this module yet.</div>
        </div>
    `;
    appBody.innerHTML = html;
}

function renderStructuredSection(section) {
    if (section.type === 'hero') {
        const actions = (section.actions || []).map((item) =>
            `<button type="button" data-app-action="${escapeHtml(item.action || '')}" data-app-value="${escapeHtml(item.value || '')}" style="padding:10px 14px;margin-right:8px;">${escapeHtml(item.label || 'Action')}</button>`
        ).join('');
        return `<div class="content-card"><div class="content-title">${escapeHtml(section.title || '')}</div><div class="content-text">${escapeHtml(section.body || '')}</div><div style="margin-top:12px;">${actions}</div></div>`;
    }
    if (section.type === 'form') {
        const fields = (section.fields || []).map((field) =>
            `<input name="${escapeHtml(field.name || '')}" placeholder="${escapeHtml(field.placeholder || '')}" style="width:100%;padding:12px;margin-top:12px;background:#0d1320;color:#eef3ff;border:1px solid rgba(140,186,255,.16);" />`
        ).join('');
        return `<div class="content-card"><div class="content-title">${escapeHtml(section.title || '')}</div><form data-app-form="${escapeHtml(section.action || '')}">${fields}<button type="submit" style="margin-top:12px;padding:10px 14px;">${escapeHtml(section.submit_label || 'Submit')}</button></form></div>`;
    }
    if (section.type === 'chips') {
        const items = (section.items || []).map((item) =>
            `<button type="button" data-app-action="${escapeHtml(item.action || '')}" data-app-value="${escapeHtml(item.value || '')}" style="padding:10px 14px;margin:6px 6px 0 0;">${escapeHtml(item.label || '')}</button>`
        ).join('');
        return `<div class="content-card"><div class="content-title">${escapeHtml(section.title || '')}</div><div style="margin-top:12px;">${items}</div></div>`;
    }
    if (section.type === 'kv') {
        const rows = (section.rows || []).map((row) =>
            `<div style="display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid rgba(140,186,255,.08);"><strong>${escapeHtml(row.label || '')}</strong><span>${escapeHtml(row.value || '')}</span></div>`
        ).join('');
        return `<div class="content-card"><div class="content-title">${escapeHtml(section.title || '')}</div><div style="margin-top:8px;">${rows}</div></div>`;
    }
    if (section.type === 'grid') {
        const items = (section.items || []).map((item) => `
            <div class="content-card" style="padding:10px;">
                ${item.image_url ? `<img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.title || '')}" style="width:100%;height:120px;object-fit:cover;margin-bottom:10px;" />` : ''}
                <div class="content-title">${escapeHtml(item.title || '')}</div>
                <div class="content-text">${escapeHtml(item.subtitle || '')}</div>
            </div>
        `).join('');
        return `<div><div class="content-title" style="margin:0 0 12px 4px;">${escapeHtml(section.title || '')}</div><div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;">${items}</div></div>`;
    }
    if (section.type === 'text') {
        return `<div class="content-card"><div class="content-title">${escapeHtml(section.title || '')}</div><div class="content-text">${escapeHtml(section.body || '')}</div></div>`;
    }
    const items = (section.items || []).map((item) =>
        `<button type="button" ${item.action ? `data-app-action="${escapeHtml(item.action)}" data-app-value="${escapeHtml(item.value || '')}"` : ''} style="display:block;width:100%;text-align:left;padding:12px 0;border:0;background:transparent;color:inherit;border-bottom:1px solid rgba(140,186,255,.08);">
            <div style="font-weight:700;">${escapeHtml(item.title || '')}</div>
            <div class="content-text">${escapeHtml(item.subtitle || '')}</div>
        </button>`
    ).join('');
    return `<div class="content-card"><div class="content-title">${escapeHtml(section.title || '')}</div><div style="margin-top:8px;">${items || `<div class="content-text">No items</div>`}</div></div>`;
}

function renderStructuredApp(payload) {
    const sections = (payload?.sections || []).map(renderStructuredSection).join('');
    appBody.innerHTML = sections || `<div class="content-card"><div class="content-title">${escapeHtml(payload?.title || 'App')}</div><div class="content-text">No content available.</div></div>`;
}

const appTemplateCache = new Map();
const appClientLoaderCache = new Map();

async function ensureAppClient(appId, scriptUrl) {
    if (!appId || !scriptUrl) return null;
    if (window.Unlim8tedAppClients?.[appId]) return window.Unlim8tedAppClients[appId];
    if (!appClientLoaderCache.has(appId)) {
        appClientLoaderCache.set(appId, (async () => {
            const response = await fetch(scriptUrl, { cache: 'no-store' });
            if (!response.ok) throw new Error(`Failed to load app client: ${appId}`);
            const code = await response.text();
            const script = document.createElement('script');
            script.type = 'text/javascript';
            script.text = code + `\n//# sourceURL=${scriptUrl}`;
            document.head.appendChild(script);
            script.remove();
            return window.Unlim8tedAppClients?.[appId] || null;
        })());
    }
    try {
        return await appClientLoaderCache.get(appId);
    } catch (_error) {
        appClientLoaderCache.delete(appId);
        return null;
    }
}

function buildAppClientContext(appId, payload) {
    return {
        appId,
        payload,
        state,
        root,
        os,
        appView,
        appBody,
        appTop,
        appTitle,
        requestJson,
        noteActivity,
        closeApp,
        escapeHtml,
        syncSystemState,
        rememberRecentApp,
        fetchAppTemplate,
        renderStructuredSectionsMarkup,
        renderStructuredApp,
        renderHtmlApp
    };
}

async function renderAppClient(payload, appId) {
    const client = await ensureAppClient(appId, payload?.client_script_url || '');
    if (!client || typeof client.render !== 'function') return false;
    await client.render(payload || {}, buildAppClientContext(appId, payload || {}));
    return true;
}

async function fetchAppTemplate(url) {
    if (!url) return '';
    if (appTemplateCache.has(url)) return appTemplateCache.get(url);
    try {
        const response = await fetch(url, { cache: 'no-store' });
        const html = response.ok ? await response.text() : '';
        appTemplateCache.set(url, html);
        return html;
    } catch (_error) {
        return '';
    }
}

function renderStructuredSectionsMarkup(payload) {
    return (payload?.sections || []).map(renderStructuredSection).join('');
}

async function renderTemplateApp(payload, appId) {
    const templateHtml = await fetchAppTemplate(payload?.template_url || '');
    if (!templateHtml) {
        if (await renderAppClient(payload || {}, appId)) {
            return;
        }
        if (payload?.view === 'structured') {
            renderStructuredApp(payload || {});
            return;
        }
        renderHtmlApp(payload, appId);
        return;
    }
    appBody.innerHTML = templateHtml;
    if (await renderAppClient(payload || {}, appId)) {
        return;
    }
    const slot = appBody.querySelector('[data-app-slot="content"]');
    if (!slot) return;
    if (payload?.view === 'structured') {
        slot.innerHTML = renderStructuredSectionsMarkup(payload || {});
        return;
    }
    slot.innerHTML = payload?.html || '';
}

async function renderAppPayload(payload, appId) {
    appTitle.textContent = payload?.title || appTitles[appId] || 'App';
    if (appTop) appTop.style.display = '';
    appView.classList.remove('browser-chrome-only');
    appBody.style.padding = '';
    appBody.style.gap = '';
    appBody.style.alignContent = '';
    if (payload?.view === 'camera' || appId === 'camera') {
        renderCameraApp();
        startCameraPreview();
        return;
    }
    if (payload?.template_url || payload?.client_script_url) {
        await renderTemplateApp(payload || {}, appId);
        return;
    }
    if (payload?.view === 'structured') {
        renderStructuredApp(payload || {});
        return;
    }
    renderHtmlApp(payload, appId);
}

async function openApp(appId) {
    if (state.sleeping) return;
    noteActivity(true);
    const response = await requestJson(`/api/apps/${encodeURIComponent(appId)}`);
    const payload = response?.app || null;
    if (response?.system) applySystemState(response.system);
    rememberRecentApp(appId, payload || {});
    state.appOpen = true;
    state.appId = appId;
    await renderAppPayload(payload || {}, appId);
    appView.classList.add('open');
}

