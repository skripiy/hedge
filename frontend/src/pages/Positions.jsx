import React, { useCallback } from 'react';
import PositionsTable from '../components/PositionsTable';
import { usePolling } from '../hooks';
import * as api from '../api';

export default function Positions() {
    const { data: positions, loading, refetch } = usePolling(
        useCallback(() => api.getPositions(1), []),
        3000
    );

    const handleClosePosition = async (tradeId) => {
        if (!confirm('Close this position?')) return;

        try {
            await api.closePosition(tradeId, 'manual');
            refetch();
        } catch (error) {
            alert(`Failed to close: ${error.message}`);
        }
    };

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Positions</h1>
                <span style={{ color: 'var(--text-muted)' }}>
                    {positions?.length || 0} open position(s)
                </span>
            </div>

            <PositionsTable
                positions={positions || []}
                loading={loading}
                onClose={handleClosePosition}
            />
        </div>
    );
}
