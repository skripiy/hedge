import React, { useCallback, useState } from 'react';
import StatCard, { StatusCard } from '../components/StatCard';
import PositionsTable from '../components/PositionsTable';
import ControlPanel from '../components/ControlPanel';
import RatesPanel from '../components/RatesPanel';
import DecisionsPanel from '../components/DecisionsPanel';
import { usePolling } from '../hooks';
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

    // Poll analytics for volume metrics every 10 seconds
    const { data: analytics } = usePolling(
        useCallback(() => api.getAnalyticsSummary(1), []),
        10000
    );

    const todayVolume = analytics?.today_volume || 0;
    const winRate = analytics?.win_rate || 0;
    const avgHoldMinutes = analytics?.avg_hold_minutes || 0;

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

            {/* Stats Grid - Row 1: Core Metrics */}
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

            {/* Stats Grid - Row 2: Volume Farming Metrics */}
            <div className="stats-grid" style={{ marginTop: '1rem' }}>
                <StatCard
                    label="Today's Volume"
                    value={todayVolume}
                    prefix="$"
                    variant="primary"
                />
                <StatCard
                    label="Win Rate"
                    value={winRate}
                    suffix="%"
                    variant={winRate >= 80 ? 'success' : winRate >= 50 ? 'default' : 'danger'}
                />
                <StatCard
                    label="Avg Hold Time"
                    value={avgHoldMinutes}
                    suffix=" min"
                    variant={avgHoldMinutes >= 60 ? 'success' : 'default'}
                />
                <StatCard
                    label="Total Trades"
                    value={analytics?.total_trades || 0}
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
                            subtitle={status?.exchange_a || 'Binance'}
                        />
                        <StatusCard
                            label="Exchange B"
                            status={status?.exchange_b_connected ? 'connected' : 'disconnected'}
                            subtitle={status?.exchange_b || 'Bybit'}
                        />
                    </div>
                </div>
            </div>

            {/* Live Rates */}
            <div style={{ marginBottom: '1.5rem' }}>
                <RatesPanel configId={1} />
            </div>

            {/* Positions + Bot Thinking */}
            <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
                <PositionsTable
                    positions={positions || []}
                    loading={positionsLoading}
                    onClose={handleClosePosition}
                />
                <DecisionsPanel configId={1} limit={30} />
            </div>
        </div>
    );
}
