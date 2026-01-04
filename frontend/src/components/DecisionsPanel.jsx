import React, { useCallback } from 'react';
import { Brain, TrendingUp, TrendingDown, XCircle, CheckCircle, AlertTriangle, Search } from 'lucide-react';
import { usePolling } from '../hooks';
import * as api from '../api';

export default function DecisionsPanel({ configId = 1, symbol = null, limit = 30 }) {
    const { data: decisions, loading } = usePolling(
        useCallback(() => api.getDecisions({ configId, symbol, limit }), [configId, symbol, limit]),
        3000 // Update every 3 seconds
    );

    if (loading && !decisions) {
        return (
            <div className="card">
                <div className="card-header">
                    <h3 className="card-title">🧠 Bot Thinking</h3>
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
                <h3 className="card-title">
                    <Brain size={18} style={{ marginRight: '0.5rem' }} />
                    Bot Thinking
                </h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Real-time decision log
                </span>
            </div>

            <div className="log-container" style={{ maxHeight: '400px' }}>
                {(!decisions || decisions.length === 0) ? (
                    <div className="empty-state" style={{ padding: '2rem' }}>
                        <Search size={32} />
                        <p>No decisions yet. Bot will log its thinking here.</p>
                    </div>
                ) : (
                    decisions.map((decision) => (
                        <DecisionEntry key={decision.id} decision={decision} />
                    ))
                )}
            </div>
        </div>
    );
}

function DecisionEntry({ decision }) {
    const typeConfig = {
        scan: { icon: Search, color: 'var(--text-muted)', label: 'SCAN' },
        opportunity: { icon: AlertTriangle, color: 'var(--warning)', label: 'OPPORTUNITY' },
        entry: { icon: TrendingUp, color: 'var(--success)', label: 'ENTRY' },
        skip: { icon: XCircle, color: 'var(--text-secondary)', label: 'SKIP' },
        exit: { icon: TrendingDown, color: 'var(--accent-primary)', label: 'EXIT' },
        risk: { icon: AlertTriangle, color: 'var(--danger)', label: 'RISK' },
        error: { icon: XCircle, color: 'var(--danger)', label: 'ERROR' },
    };

    const config = typeConfig[decision.type] || typeConfig.scan;
    const Icon = config.icon;

    const formatTime = (timestamp) => {
        if (!timestamp) return '--:--:--';
        return new Date(timestamp).toLocaleTimeString('en-US', { hour12: false });
    };

    return (
        <div
            className="log-entry"
            style={{
                borderLeft: `3px solid ${config.color}`,
                paddingLeft: '1rem'
            }}
        >
            <span className="log-time">{formatTime(decision.timestamp)}</span>

            <span style={{
                color: config.color,
                fontWeight: 600,
                width: '90px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px'
            }}>
                <Icon size={12} />
                {config.label}
            </span>

            <span style={{ color: 'var(--accent-primary)', fontWeight: 500, marginRight: '0.5rem' }}>
                {decision.symbol}
            </span>

            <span className="log-message" style={{ flex: 1 }}>
                {decision.reason || formatDecisionDetails(decision)}
            </span>

            {decision.pnl !== null && decision.pnl !== undefined && (
                <span className={decision.pnl >= 0 ? 'positive' : 'negative'} style={{ fontWeight: 600, marginLeft: '0.5rem' }}>
                    {decision.pnl >= 0 ? '+' : ''}${decision.pnl.toFixed(2)}
                </span>
            )}
        </div>
    );
}

function formatDecisionDetails(decision) {
    const parts = [];

    if (decision.price_a && decision.price_b) {
        parts.push(`A: $${decision.price_a.toFixed(2)} | B: $${decision.price_b.toFixed(2)}`);
    }

    if (decision.spread !== null && decision.spread !== undefined) {
        const spreadSign = decision.spread >= 0 ? '+' : '';
        parts.push(`Spread: ${spreadSign}${decision.spread.toFixed(4)}%`);

        if (decision.spread_threshold) {
            parts.push(`(need: ${decision.spread_threshold}%)`);
        }
    }

    if (decision.action) {
        parts.push(`→ ${decision.action}`);
    }

    return parts.join(' | ') || 'Checking market conditions...';
}
