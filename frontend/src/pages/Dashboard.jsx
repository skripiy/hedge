import React, { useCallback, useState } from 'react';
import StatCard, { StatusCard } from '../components/StatCard';
import PositionsTable from '../components/PositionsTable';
import ControlPanel from '../components/ControlPanel';
import RatesPanel from '../components/RatesPanel';
import DecisionsPanel from '../components/DecisionsPanel';
import { usePolling } from '../hooks';
import * as api from '../api';
import { Activity, TrendingUp, TrendingDown, Zap, Clock, BarChart2, Wifi, WifiOff } from 'lucide-react';

export default function Dashboard() {
    const [actionLoading, setActionLoading] = useState(false);

    // Poll status every 2 seconds (faster updates)
    const { data: status, loading: statusLoading, refetch: refetchStatus } = usePolling(
        useCallback(() => api.getStatus(1), []),
        2000
    );

    // Poll positions every 3 seconds (faster updates)
    const { data: positions, loading: positionsLoading, refetch: refetchPositions } = usePolling(
        useCallback(() => api.getPositions(1), []),
        3000
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

    // Calculate display values from status
    const botStatus = status?.status || 'stopped';
    const isRunning = botStatus === 'running';

    // Poll analytics for volume metrics every 5 seconds
    const { data: analytics } = usePolling(
        useCallback(() => api.getAnalyticsSummary(1), []),
        5000
    );

    // Use analytics for metrics
    const todayVolume = analytics?.today_volume || 0;
    const winRate = analytics?.win_rate || 0;
    const avgHoldMinutes = analytics?.avg_hold_minutes || 0;
    const openPositions = analytics?.open_positions || positions?.length || 0;
    const unrealizedPnl = analytics?.unrealized_pnl || 0;
    const todayPnl = analytics?.total_pnl || 0;
    const totalTrades = analytics?.total_trades || 0;

    // Exchange balances from status
    const exchangeA = status?.exchange_a?.toUpperCase() || 'BINANCE';
    const exchangeB = status?.exchange_b?.toUpperCase() || 'BYBIT';
    const balanceA = status?.balance_a || 5000;
    const balanceB = status?.balance_b || 5000;
    const totalBalance = balanceA + balanceB;

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

            {/* Exchange Balances Row */}
            <div className="grid-3" style={{ marginBottom: '1rem' }}>
                <div className="card" style={{
                    background: 'linear-gradient(135deg, var(--bg-secondary) 0%, rgba(0,200,83,0.1) 100%)',
                    borderColor: 'rgba(0,200,83,0.3)'
                }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                        {exchangeA} Balance
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--success)' }}>
                        ${balanceA.toLocaleString()}
                    </div>
                </div>
                <div className="card" style={{
                    background: 'linear-gradient(135deg, var(--bg-secondary) 0%, rgba(255,170,0,0.1) 100%)',
                    borderColor: 'rgba(255,170,0,0.3)'
                }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                        {exchangeB} Balance
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--warning)' }}>
                        ${balanceB.toLocaleString()}
                    </div>
                </div>
                <div className="card" style={{
                    background: 'linear-gradient(135deg, var(--bg-secondary) 0%, rgba(0,136,255,0.1) 100%)',
                    borderColor: 'rgba(0,136,255,0.3)'
                }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                        Total Balance
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                        ${totalBalance.toLocaleString()}
                    </div>
                </div>
            </div>

            {/* Stats Grid - Row 1: PnL Metrics */}
            <div className="stats-grid">
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
                    label="Today's Volume"
                    value={todayVolume}
                    prefix="$"
                    variant="primary"
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
                    value={totalTrades}
                />
                <StatCard
                    label="Total Fees"
                    value={analytics?.total_fees || 0}
                    prefix="$"
                    variant="danger"
                />
            </div>

            {/* Control Panel + Connection Status */}
            <div className="grid-2" style={{ marginTop: '1.5rem', marginBottom: '1.5rem' }}>
                <ControlPanel
                    status={botStatus}
                    onStart={handleStart}
                    onStop={handleStop}
                    onPanic={handlePanic}
                    loading={actionLoading}
                />

                {/* Improved Connection Status */}
                <div className="card">
                    <div className="card-header">
                        <h3 className="card-title">Connection Status</h3>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '0.5rem' }}>
                        <div style={{
                            padding: '1rem',
                            borderRadius: '8px',
                            background: isRunning ? 'rgba(0,200,83,0.1)' : 'rgba(255,82,82,0.1)',
                            border: `1px solid ${isRunning ? 'rgba(0,200,83,0.3)' : 'rgba(255,82,82,0.3)'}`
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                {isRunning ? <Wifi size={16} color="var(--success)" /> : <WifiOff size={16} color="var(--danger)" />}
                                <span style={{ fontWeight: 600, color: isRunning ? 'var(--success)' : 'var(--danger)' }}>
                                    {exchangeA}
                                </span>
                            </div>
                            <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                                {isRunning ? '● Connected' : '○ Disconnected'}
                            </div>
                        </div>
                        <div style={{
                            padding: '1rem',
                            borderRadius: '8px',
                            background: isRunning ? 'rgba(0,200,83,0.1)' : 'rgba(255,82,82,0.1)',
                            border: `1px solid ${isRunning ? 'rgba(0,200,83,0.3)' : 'rgba(255,82,82,0.3)'}`
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                                {isRunning ? <Wifi size={16} color="var(--success)" /> : <WifiOff size={16} color="var(--danger)" />}
                                <span style={{ fontWeight: 600, color: isRunning ? 'var(--success)' : 'var(--danger)' }}>
                                    {exchangeB}
                                </span>
                            </div>
                            <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                                {isRunning ? '● Connected' : '○ Disconnected'}
                            </div>
                        </div>
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
