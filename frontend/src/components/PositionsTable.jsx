import React from 'react';
import { X } from 'lucide-react';

export default function PositionsTable({ positions = [], onClose, loading = false }) {
    if (loading) {
        return (
            <div className="card">
                <div className="card-header">
                    <h3 className="card-title">Active Positions</h3>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                    <div className="spinner"></div>
                </div>
            </div>
        );
    }

    if (positions.length === 0) {
        return (
            <div className="card">
                <div className="card-header">
                    <h3 className="card-title">Active Positions</h3>
                </div>
                <div className="empty-state">
                    <p>No open positions</p>
                </div>
            </div>
        );
    }

    return (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div className="card-header" style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border-color)' }}>
                <h3 className="card-title">Active Positions ({positions.length})</h3>
            </div>
            <div className="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Exchange A (Long)</th>
                            <th>Exchange B (Short)</th>
                            <th>Entry A</th>
                            <th>Entry B</th>
                            <th>Current A</th>
                            <th>Current B</th>
                            <th>Size (USDT)</th>
                            <th>Duration</th>
                            <th>PnL</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {positions.map((position) => (
                            <PositionRow
                                key={position.trade_id}
                                position={position}
                                onClose={onClose}
                            />
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function PositionRow({ position, onClose }) {
    const pnl = position.total_pnl || 0;
    const pnlClass = pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : '';

    const formatPrice = (price) => price ? price.toFixed(2) : '-';
    const formatPnl = (value) => {
        if (!value) return '$0.00';
        const sign = value > 0 ? '+' : '';
        return `${sign}$${value.toFixed(2)}`;
    };

    // Calculate duration
    const formatDuration = (openTime) => {
        if (!openTime) return '-';
        const now = new Date();
        const opened = new Date(openTime);
        const diffMs = now - opened;
        const diffMins = Math.floor(diffMs / 60000);
        const hours = Math.floor(diffMins / 60);
        const mins = diffMins % 60;
        if (hours > 0) return `${hours}h ${mins}m`;
        return `${mins}m`;
    };

    const duration = formatDuration(position.open_time);

    return (
        <tr>
            <td>
                <strong>{position.symbol}</strong>
            </td>
            <td>
                <span className="badge badge-success">{position.exchange_a}</span>
            </td>
            <td>
                <span className="badge badge-danger">{position.exchange_b}</span>
            </td>
            <td>${formatPrice(position.entry_price_a)}</td>
            <td>${formatPrice(position.entry_price_b)}</td>
            <td>${formatPrice(position.current_price_a)}</td>
            <td>${formatPrice(position.current_price_b)}</td>
            <td>${position.amount_usdt?.toFixed(2) || '0.00'}</td>
            <td>
                <span style={{ color: 'var(--text-muted)' }}>{duration}</span>
            </td>
            <td>
                <span className={`stat-value ${pnlClass}`} style={{ fontSize: '0.875rem' }}>
                    {formatPnl(pnl)}
                </span>
            </td>
            <td>
                <button
                    className="btn btn-outline"
                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                    onClick={() => onClose && onClose(position.trade_id)}
                >
                    <X size={14} />
                    Close
                </button>
            </td>
        </tr>
    );
}
