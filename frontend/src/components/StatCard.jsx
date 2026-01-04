import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function StatCard({
    label,
    value,
    change,
    changeLabel,
    variant = 'default', // default, success, warning, danger
    prefix = '',
    suffix = '',
    loading = false
}) {
    const isPositive = typeof change === 'number' && change > 0;
    const isNegative = typeof change === 'number' && change < 0;

    const valueClass = isPositive ? 'positive' : isNegative ? 'negative' : '';

    return (
        <div className={`stat-card ${variant}`}>
            <div className="stat-label">{label}</div>

            {loading ? (
                <div className="spinner" style={{ marginTop: '0.5rem' }}></div>
            ) : (
                <>
                    <div className={`stat-value ${valueClass}`}>
                        {prefix}{typeof value === 'number' ? value.toLocaleString() : value}{suffix}
                    </div>

                    {change !== undefined && (
                        <div className={`stat-change ${isPositive ? 'positive' : isNegative ? 'negative' : ''}`}>
                            {isPositive ? <TrendingUp size={12} /> :
                                isNegative ? <TrendingDown size={12} /> :
                                    <Minus size={12} />}
                            {isPositive && '+'}{change}{changeLabel || '%'}
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

export function StatusCard({ label, status, subtitle }) {
    const statusConfig = {
        running: { dot: 'running', text: 'Running', color: 'var(--success)' },
        stopped: { dot: 'stopped', text: 'Stopped', color: 'var(--text-muted)' },
        error: { dot: 'error', text: 'Error', color: 'var(--danger)' },
        connected: { dot: 'running', text: 'Connected', color: 'var(--success)' },
        disconnected: { dot: 'stopped', text: 'Disconnected', color: 'var(--text-muted)' },
    };

    const config = statusConfig[status] || statusConfig.stopped;

    return (
        <div className="stat-card">
            <div className="stat-label">{label}</div>
            <div className="status-indicator" style={{ marginTop: '0.5rem' }}>
                <span className={`status-dot ${config.dot}`}></span>
                <span style={{ color: config.color, fontWeight: 500 }}>{config.text}</span>
            </div>
            {subtitle && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    {subtitle}
                </div>
            )}
        </div>
    );
}
