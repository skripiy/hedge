import React, { useCallback } from 'react';
import { TrendingUp, TrendingDown, BarChart2, Award } from 'lucide-react';
import StatCard from '../components/StatCard';
import EquityChart from '../components/EquityChart';
import { usePolling } from '../hooks';
import * as api from '../api';

export default function Analytics() {
    // Poll data
    const { data: summary, loading: summaryLoading } = usePolling(
        useCallback(() => api.getAnalyticsSummary(1), []),
        30000
    );

    const { data: equity, loading: equityLoading } = usePolling(
        useCallback(() => api.getEquityCurve(1, 30), []),
        30000
    );

    const { data: trades, loading: tradesLoading } = usePolling(
        useCallback(() => api.getTrades(1, 'closed', 100), []),
        30000
    );

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Analytics</h1>
            </div>

            {/* Summary Stats */}
            <div className="stats-grid">
                <StatCard
                    label="Total Trades"
                    value={summary?.total_trades || 0}
                    loading={summaryLoading}
                />
                <StatCard
                    label="Win Rate"
                    value={summary?.win_rate || 0}
                    suffix="%"
                    variant={summary?.win_rate >= 50 ? 'success' : 'warning'}
                    loading={summaryLoading}
                />
                <StatCard
                    label="Net PnL"
                    value={summary?.net_pnl || 0}
                    prefix="$"
                    change={summary?.net_pnl || 0}
                    changeLabel=" USDT"
                    loading={summaryLoading}
                />
                <StatCard
                    label="Total Fees Paid"
                    value={summary?.total_fees || 0}
                    prefix="$"
                    variant="warning"
                    loading={summaryLoading}
                />
            </div>

            {/* Win/Loss Stats */}
            <div className="grid-3" style={{ marginBottom: '1.5rem' }}>
                <div className="card" style={{ textAlign: 'center' }}>
                    <TrendingUp size={32} style={{ color: 'var(--success)', marginBottom: '0.5rem' }} />
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--success)' }}>
                        {summary?.winning_trades || 0}
                    </div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Winning Trades</div>
                </div>
                <div className="card" style={{ textAlign: 'center' }}>
                    <TrendingDown size={32} style={{ color: 'var(--danger)', marginBottom: '0.5rem' }} />
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--danger)' }}>
                        {summary?.losing_trades || 0}
                    </div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Losing Trades</div>
                </div>
                <div className="card" style={{ textAlign: 'center' }}>
                    <Award size={32} style={{ color: 'var(--accent-primary)', marginBottom: '0.5rem' }} />
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                        {summary?.total_pnl?.toFixed(2) || '0.00'}
                    </div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Total PnL (USDT)</div>
                </div>
            </div>

            {/* Equity Chart */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <div className="card-header">
                    <h3 className="card-title">Equity Curve (30 Days)</h3>
                    {equity && (
                        <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.875rem' }}>
                            <div>
                                Initial: <strong>${equity.initial_balance?.toLocaleString()}</strong>
                            </div>
                            <div>
                                Current: <strong>${equity.current_balance?.toLocaleString()}</strong>
                            </div>
                            <div>
                                Trades: <strong>{equity.total_trades}</strong>
                            </div>
                        </div>
                    )}
                </div>
                <EquityChart data={equity?.data || []} loading={equityLoading} />
            </div>

            {/* Trade History */}
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div className="card-header" style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border-color)' }}>
                    <h3 className="card-title">Trade History</h3>
                    <button
                        className="btn btn-outline"
                        onClick={() => exportTrades(trades)}
                        disabled={!trades?.length}
                    >
                        Export CSV
                    </button>
                </div>

                {tradesLoading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                        <div className="spinner"></div>
                    </div>
                ) : trades?.length > 0 ? (
                    <div className="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Date</th>
                                    <th>Symbol</th>
                                    <th>Entry A</th>
                                    <th>Exit A</th>
                                    <th>Entry B</th>
                                    <th>Exit B</th>
                                    <th>Size</th>
                                    <th>PnL</th>
                                    <th>Reason</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trades.map((trade) => (
                                    <TradeRow key={trade.trade_id} trade={trade} />
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="empty-state">
                        <BarChart2 size={48} />
                        <p>No closed trades yet</p>
                    </div>
                )}
            </div>
        </div>
    );
}

function TradeRow({ trade }) {
    const pnl = trade.pnl_net || 0;
    const pnlClass = pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : '';

    const formatDate = (dateStr) => {
        if (!dateStr) return '-';
        return new Date(dateStr).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    return (
        <tr>
            <td>{formatDate(trade.close_time)}</td>
            <td><strong>{trade.symbol}</strong></td>
            <td>${trade.entry_price_a?.toFixed(2)}</td>
            <td>${trade.exit_price_a?.toFixed(2) || '-'}</td>
            <td>${trade.entry_price_b?.toFixed(2)}</td>
            <td>${trade.exit_price_b?.toFixed(2) || '-'}</td>
            <td>${trade.entry_amount_usdt?.toFixed(2)}</td>
            <td className={pnlClass} style={{ fontWeight: 600 }}>
                {pnl > 0 ? '+' : ''}${pnl.toFixed(2)}
            </td>
            <td>
                <span className={`badge badge-${trade.close_reason === 'take_profit' ? 'success' : trade.close_reason === 'stop_loss' ? 'danger' : 'info'}`}>
                    {trade.close_reason || 'manual'}
                </span>
            </td>
        </tr>
    );
}

function exportTrades(trades) {
    if (!trades?.length) return;

    const headers = ['Date', 'Symbol', 'Entry A', 'Exit A', 'Entry B', 'Exit B', 'Size USDT', 'PnL', 'Reason'];
    const rows = trades.map(t => [
        t.close_time,
        t.symbol,
        t.entry_price_a,
        t.exit_price_a,
        t.entry_price_b,
        t.exit_price_b,
        t.entry_amount_usdt,
        t.pnl_net,
        t.close_reason
    ]);

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `hedgebot_trades_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
