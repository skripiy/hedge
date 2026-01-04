import React from 'react';

export default function LogsPanel({ logs = [], loading = false, maxHeight = '400px' }) {
    if (loading) {
        return (
            <div className="card">
                <div className="card-header">
                    <h3 className="card-title">Activity Log</h3>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                    <div className="spinner"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div className="card-header" style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border-color)' }}>
                <h3 className="card-title">Activity Log</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {logs.length} entries
                </span>
            </div>
            <div className="log-container" style={{ maxHeight }}>
                {logs.length === 0 ? (
                    <div className="empty-state">
                        <p>No logs yet</p>
                    </div>
                ) : (
                    logs.map((log, index) => (
                        <LogEntry key={log.id || index} log={log} />
                    ))
                )}
            </div>
        </div>
    );
}

function LogEntry({ log }) {
    const formatTime = (timestamp) => {
        if (!timestamp) return '--:--:--';
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { hour12: false });
    };

    const levelClass = log.level?.toLowerCase() || 'info';

    return (
        <div className="log-entry">
            <span className="log-time">{formatTime(log.created_at)}</span>
            <span className={`log-level ${levelClass}`}>{log.level || 'INFO'}</span>
            <span className="log-message">{log.message}</span>
        </div>
    );
}

export function SimpleLog({ entries = [] }) {
    return (
        <div className="log-container" style={{ maxHeight: '300px' }}>
            {entries.map((entry, index) => (
                <div key={index} className="log-entry">
                    <span className="log-time">{entry.time}</span>
                    <span className={`log-level ${entry.level || 'info'}`}>
                        {(entry.level || 'INFO').toUpperCase()}
                    </span>
                    <span className="log-message">{entry.message}</span>
                </div>
            ))}
        </div>
    );
}
