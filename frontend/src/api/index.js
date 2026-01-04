/**
 * API service for HedgeBot frontend
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Generic fetch wrapper with error handling
 */
async function fetchAPI(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;

    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const response = await fetch(url, { ...defaultOptions, ...options });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
}

// ============ Bot Control ============

export async function startBot(configId = 1) {
    return fetchAPI('/start', {
        method: 'POST',
        body: JSON.stringify({ config_id: configId }),
    });
}

export async function stopBot(configId = 1, closePositions = false) {
    return fetchAPI('/stop', {
        method: 'POST',
        body: JSON.stringify({ config_id: configId, close_positions: closePositions }),
    });
}

export async function panicClose(configId = 1) {
    return fetchAPI('/panic', {
        method: 'POST',
        body: JSON.stringify({ config_id: configId }),
    });
}

// ============ Status ============

export async function getStatus(configId = 1) {
    return fetchAPI(`/status?config_id=${configId}`);
}

export async function getPositions(configId = 1) {
    return fetchAPI(`/positions?config_id=${configId}`);
}

export async function closePosition(tradeId, reason = 'manual') {
    return fetchAPI(`/positions/${tradeId}/close`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
    });
}

// ============ Trades ============

export async function getTrades(configId = 1, status = null, limit = 50) {
    let url = `/trades?config_id=${configId}&limit=${limit}`;
    if (status) url += `&status=${status}`;
    return fetchAPI(url);
}

export async function getTrade(tradeId) {
    return fetchAPI(`/trades/${tradeId}`);
}

// ============ Config ============

export async function getConfig(configId = 1) {
    return fetchAPI(`/config?config_id=${configId}`);
}

export async function updateConfig(configId = 1, data) {
    return fetchAPI(`/config?config_id=${configId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

// ============ Logs ============

export async function getLogs(options = {}) {
    const { configId, level, category, limit = 100 } = options;
    let url = `/logs?limit=${limit}`;
    if (configId) url += `&config_id=${configId}`;
    if (level) url += `&level=${level}`;
    if (category) url += `&category=${category}`;
    return fetchAPI(url);
}

// ============ Analytics ============

export async function getEquityCurve(configId = 1, days = 30) {
    return fetchAPI(`/analytics/equity?config_id=${configId}&days=${days}`);
}

export async function getAnalyticsSummary(configId = 1) {
    return fetchAPI(`/analytics/summary?config_id=${configId}`);
}

// ============ Health ============

export async function healthCheck() {
    return fetchAPI('/health');
}
