window.Unlim8tedAppClients = window.Unlim8tedAppClients || {};
window.Unlim8tedAppClients.settings = (() => {
    let currentCtx = null;

    function settingsState(payload = {}) {
        return payload.settings || currentCtx?.payload?.settings || {
            brightness: 68,
            idle_timeout_sec: 45,
            sleeping: false,
            toggles: [],
            badges: [],
            device: []
        };
    }

    async function sendAction(action, value) {
        if (!currentCtx) return;
        const response = await currentCtx.requestJson('/api/apps/settings/action', {
            method: 'POST',
            body: JSON.stringify({ action, payload: { value } })
        });
        if (response?.app) {
            currentCtx.payload = response.app;
            render(response.app, currentCtx);
        }
        if (response?.system) {
            currentCtx.syncSystemState?.();
        }
    }

    function profileMarkup(owner, sleeping) {
        const initial = String(owner || 'U').trim().charAt(0).toUpperCase() || 'U';
        return `
            <div class="settings-profile">
                <div class="settings-avatar">${initial}</div>
                <div>
                    <div class="settings-profile-name">${currentCtx.escapeHtml(owner || 'Unknown Owner')}</div>
                    <div class="settings-profile-copy">${sleeping ? 'Device is sleeping right now.' : 'Everything is synced and running locally.'}</div>
                </div>
            </div>
        `;
    }

    function deviceMarkup(device) {
        return device.map((item) => `
            <div class="settings-stat">
                <div class="settings-stat-label">${currentCtx.escapeHtml(item.label || '')}</div>
                <div class="settings-stat-value">${currentCtx.escapeHtml(item.value || '')}</div>
            </div>
        `).join('');
    }

    function togglesMarkup(toggles) {
        return toggles.map((item) => `
            <button type="button" class="settings-toggle ${item.enabled ? 'active' : ''}" data-settings-toggle="${currentCtx.escapeHtml(item.id)}">
                <div>
                    <div class="settings-toggle-name">${currentCtx.escapeHtml(item.label || item.id || '')}</div>
                    <div class="settings-toggle-state">${item.enabled ? 'Enabled' : 'Disabled'}</div>
                </div>
                <div class="settings-toggle-pill"></div>
            </button>
        `).join('');
    }

    function displayMarkup(brightness, idleTimeout) {
        const timeoutOptions = [15, 30, 60, 120, 300, 600];
        return `
            <div class="settings-display-stack">
                <div class="settings-display-card">
                    <div>
                        <div class="settings-section-kicker">Brightness</div>
                        <div class="settings-sub">Tune panel output without leaving the app.</div>
                    </div>
                    <div class="settings-slider-row">
                        <input class="settings-slider" id="settingsBrightnessRange" type="range" min="5" max="100" value="${brightness}" />
                        <div class="settings-slider-value" id="settingsBrightnessValue">${brightness}%</div>
                    </div>
                </div>
                <div class="settings-display-card">
                    <div>
                        <div class="settings-section-kicker">Idle timeout</div>
                        <div class="settings-sub">Choose how long the device waits before sleeping.</div>
                    </div>
                    <div class="settings-timeout-grid">
                        ${timeoutOptions.map((seconds) => `
                            <button type="button" class="settings-chip ${seconds === idleTimeout ? 'active' : ''}" data-timeout-value="${seconds}">${seconds}s</button>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    }

    function badgesMarkup(badges) {
        if (!badges.length) {
            return '<div class="settings-empty">No apps are asking for attention right now. Badge counts will show up here when notifications start stacking.</div>';
        }
        return `<div class="settings-badge-list">${badges.map((item) => `
            <div class="settings-badge-card">
                <div class="settings-badge-id">${currentCtx.escapeHtml(item.id || '')}</div>
                <div class="settings-badge-count">${currentCtx.escapeHtml(String(item.count || 0))}</div>
            </div>
        `).join('')}</div>`;
    }

    function bindEvents(state) {
        currentCtx.appBody.querySelectorAll('[data-settings-toggle]').forEach((button) => {
            button.addEventListener('click', () => sendAction('toggle_connectivity', button.dataset.settingsToggle || ''));
        });

        currentCtx.appBody.querySelectorAll('[data-timeout-value]').forEach((button) => {
            button.addEventListener('click', () => sendAction('set_idle_timeout', button.dataset.timeoutValue || ''));
        });

        const range = currentCtx.appBody.querySelector('#settingsBrightnessRange');
        const value = currentCtx.appBody.querySelector('#settingsBrightnessValue');
        range?.addEventListener('input', () => {
            if (value) value.textContent = `${range.value}%`;
        });
        range?.addEventListener('change', () => {
            sendAction('set_brightness', range.value || String(state.brightness || 68));
        });
    }

    async function render(payload, ctx) {
        currentCtx = ctx;
        currentCtx.payload = payload || {};
        const state = settingsState(payload || {});
        const owner = payload?.owner || 'Owner';

        const ownerLine = currentCtx.appBody.querySelector('#settingsOwnerLine');
        const profile = currentCtx.appBody.querySelector('#settingsProfileCard');
        const stats = currentCtx.appBody.querySelector('#settingsDeviceStats');
        const toggles = currentCtx.appBody.querySelector('#settingsToggleGrid');
        const display = currentCtx.appBody.querySelector('#settingsDisplayControls');
        const badges = currentCtx.appBody.querySelector('#settingsBadges');

        if (ownerLine) ownerLine.textContent = `${owner}'s device, controls, and status.`;
        if (profile) profile.innerHTML = profileMarkup(owner, state.sleeping);
        if (stats) stats.innerHTML = deviceMarkup(state.device || []);
        if (toggles) toggles.innerHTML = togglesMarkup(state.toggles || []);
        if (display) display.innerHTML = displayMarkup(state.brightness || 68, state.idle_timeout_sec || 45);
        if (badges) badges.innerHTML = badgesMarkup(state.badges || []);

        bindEvents(state);
    }

    return { render };
})();
