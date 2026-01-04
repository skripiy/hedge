import React, { useCallback, useState } from 'react';
import { TrendingUp, TrendingDown, Zap, RefreshCw } from 'lucide-react';
import { usePolling } from '../hooks';
import * as api from '../api';

export default function RatesPanel({ configId = 1 }) {
    const [refreshing, setRefreshing] = useState(false);

    const { data, loading, refetch } = usePolling(
        useCallback(() => api.getRates(configId), [configId]),
        10000 // Update every 10 seconds
    );

    const handleRefresh = async () => {
        setRefreshing(true);
        await refetch();
        setRefreshing(false);
    };

    if (loading && !data) {
        return (
            <div className="card">
                <div className="card-header">
                    <h3 className="card-title">Live Rates</h3>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                    <div className="spinner"></div>
                </div>
            </div>
        );
    }

    const rates = data?.rates || [];

    return (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div className="card-header" style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border-color)' }}>
                <h3 className="card-title">
                    Live Rates
                    <span style={{ marginLeft: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {data?.exchange_a} / {data?.exchange_b}
                    </span>
                </h3>
                <button
                    className="btn btn-outline"
                    onClick={handleRefresh}
                    disabled={refreshing}
                    style={{ padding: '0.25rem 0.5rem' }}
                >
                    <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
                </button>
            </div>

            {rates.length === 0 ? (
                <div className="empty-state" style={{ padding: '2rem' }}>
                    <p>No symbols configured. Add symbols in Settings.</p>
                </div>
            ) : (
                <div className="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Symbol</th>
                                <th>{data?.exchange_a}</th>
                                <th>{data?.exchange_b}</th>
                                <th>Spread</th>
                                <th>Volume 24h</th>
                                <th>Signal</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rates.map((rate) => (
                                <RateRow key={rate.symbol} rate={rate} />
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {data?.timestamp && (
                <div style={{ padding: '0.5rem 1rem', fontSize: '0.7rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)' }}>
                    Updated: {new Date(data.timestamp).toLocaleTimeString()}
                </div>
            )}
        </div>
    );
}

function RateRow({ rate }) {
    if (rate.error) {
        return (
            <tr>
                <td><strong>{rate.symbol}</strong></td>
                <td colSpan={5} style={{ color: 'var(--danger)' }}>{rate.error}</td>
            </tr>
        );
    }

    const spreadClass = rate.spread > 0 ? 'positive' : rate.spread < 0 ? 'negative' : '';
    const isOpportunity = rate.is_opportunity;

    return (
        <tr style={{ background: isOpportunity ? 'var(--success-bg)' : 'transparent' }}>
            <td>
                <strong>{rate.symbol}</strong>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    ${rate.position_size_usdt} size
                </div>
            </td>
            <td>
                <span style={{ fontFamily: 'monospace' }}>${rate.price_a?.toLocaleString()}</span>
            </td>
            <td>
                <span style={{ fontFamily: 'monospace' }}>${rate.price_b?.toLocaleString()}</span>
            </td>
            <td>
                <span className={spreadClass} style={{ fontWeight: 600, fontFamily: 'monospace' }}>
                    {rate.spread > 0 ? '+' : ''}{rate.spread?.toFixed(4)}%
                </span>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                    threshold: {rate.spread_threshold}%
                </div>
            </td>
            <td>
                <span style={{ fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                    {rate.volume_24h ? `$${(rate.volume_24h / 1000000).toFixed(1)}M` : '-'}
                </span>
            </td>
            <td>
                {isOpportunity ? (
                    <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <Zap size={12} />
                        ENTRY
                    </span>
                ) : (
                    <span className="badge badge-info">Watching</span>
                )}
            </td>
        </tr>
    );
}
