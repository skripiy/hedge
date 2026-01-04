import React, { useCallback, useState } from 'react';
import StatCard, { StatusCard } from '../components/StatCard';
import PositionsTable from '../components/PositionsTable';
import LogsPanel from '../components/LogsPanel';
import ControlPanel from '../components/ControlPanel';
import EquityChart from '../components/EquityChart';
import { usePolling, useAsync } from '../hooks';
import * as api from '../api';

export default function Dashboard() {
    const [actionLoading, setActionLoading] = useState(false);

    // Poll status every 3 seconds
    const { data: status, loading: statusLoading, refetch: refetchStatus } = usePolling(
        useCallback(() => api.getStatus(1), []),
        3000
    );

    // Poll positions every 5 seconds
    const { data: positions, loading: positionsLoading, refetch: refetchPositions } = usePolling(
        useCallback(() => api.getPositions(1), []),
        5000
    );

    // Poll logs every 10 seconds
    const { data: logs, loading: logsLoading } = usePolling(
        useCallback(() => api.getLogs({ configId: 1, limit: 50 }), []),
        10000
    );

    // Poll equity curve every 30 seconds
    const { data: equity, loading: equityLoading } = usePolling(
        useCallback(() => api.getEquityCurve(1, 30), []),
        30000
    );

    // Handle bot actions
    const handleStart = async () => {
        setActionLoading(true);
        try {
            await api.startBot(1);
            refetchStatus();
        } catch (error) {
            alert(`Failed to start: ${error.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    const handleStop = async () => {
        setActionLoading(true);
        try {
            await api.stopBot(1, false);
            refetchStatus();
        } catch (error) {
            alert(`Failed to stop: ${error.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    const handlePanic = async () => {
        if (!confirm('⚠️ PANIC CLOSE: This will immediately close ALL open positions. Are you sure?')) {
            return;
        }

        setActionLoading(true);
        try {
            const result = await api.panicClose(1);
            alert(`Closed ${result.data?.closed_count || 0} positions`);
            refetchStatus();
            refetchPositions();
        } catch (error) {
            alert(`Panic close failed: ${error.message}`);
        } finally {
            setActionLoading(false);
        }
    };

    const handleClosePosition = async (tradeId) => {
        if (!confirm('Close this position?')) return;

        try {
            await api.closePosition(tradeId, 'manual');
            refetchPositions();
        } catch (error) {
            alert(`Failed to close position: ${error.message}`);
        }
    };

    // Calculate display values
    const currentBalance = status?.current_balance || 10000;
    const unrealizedPnl = status?.unrealized_pnl || 0;
    const todayPnl = status?.total_pnl_today || 0;
    const openPositions = status?.open_positions_count || 0;
    const botStatus = status?.status || 'stopped';

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Dashboard</h1>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                        Mode: <strong style={{ color: 'var(--accent-primary)' }}>
                            {status?.mode?.toUpperCase() || 'SIMULATION'}
                        </strong>
                    </span>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid">
                <StatCard
                    label="Current Balance"
                    value={currentBalance}
                    prefix="$"
                    loading={statusLoading}
                />
                <StatCard
                    label="Unrealized PnL"
                    value={unrealizedPnl}
                    prefix="$"
                    change={unrealizedPnl}
                    changeLabel=" USDT"
                    loading={statusLoading}
                />
                <StatCard
                    label="Today's PnL"
                    value={todayPnl}
                    prefix="$"
                    change={todayPnl}
                    changeLabel=" USDT"
                    loading={statusLoading}
                />
                <StatCard
                    label="Open Positions"
                    value={openPositions}
                    variant={openPositions > 0 ? 'success' : 'default'}
                    loading={statusLoading}
                />
            </div>

            {/* Control Panel + Connection Status */}
            <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
                <ControlPanel
                    status={botStatus}
                    onStart={handleStart}
                    onStop={handleStop}
                    onPanic={handlePanic}
                    loading={actionLoading}
                />

                <div className="card">
                    <div className="card-header">
                        <h3 className="card-title">Connection Status</h3>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '0.5rem' }}>
                        <StatusCard
                            label="Exchange A"
                            status={status?.exchange_a_connected ? 'connected' : 'disconnected'}
                            subtitle="Binance"
                        />
                        <StatusCard
                            label="Exchange B"
                            status={status?.exchange_b_connected ? 'connected' : 'disconnected'}
                            subtitle="Bybit"
                        />
                    </div>
                </div>
            </div>

            {/* Equity Chart */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <div className="card-header">
                    <h3 className="card-title">Equity Curve</h3>
                    {equity && (
                        <span style={{ fontSize: '0.875rem' }}>
                            Total PnL:
                            <strong className={equity.total_pnl >= 0 ? 'positive' : 'negative'} style={{ marginLeft: '0.5rem' }}>
                                ${equity.total_pnl?.toFixed(2) || '0.00'}
                            </strong>
                        </span>
                    )}
                </div>
                <EquityChart data={equity?.data || []} loading={equityLoading} />
            </div>

            {/* Positions + Logs */}
            <div className="grid-2">
                <PositionsTable
                    positions={positions || []}
                    loading={positionsLoading}
                    onClose={handleClosePosition}
                />
                <LogsPanel
                    logs={logs || []}
                    loading={logsLoading}
                    maxHeight="350px"
                />
            </div>
        </div>
    );
}
