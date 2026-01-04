import React, { useCallback, useState } from 'react';
import { RefreshCw, Filter } from 'lucide-react';
import LogsPanel from '../components/LogsPanel';
import { usePolling } from '../hooks';
import * as api from '../api';

export default function Logs() {
    const [filter, setFilter] = useState({ level: '', category: '' });

    const { data: logs, loading, refetch } = usePolling(
        useCallback(() => api.getLogs({
            configId: 1,
            level: filter.level || undefined,
            category: filter.category || undefined,
            limit: 200
        }), [filter]),
        5000
    );

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Activity Logs</h1>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <select
                        className="form-input form-select"
                        style={{ width: 'auto' }}
                        value={filter.level}
                        onChange={(e) => setFilter(f => ({ ...f, level: e.target.value }))}
                    >
                        <option value="">All Levels</option>
                        <option value="INFO">INFO</option>
                        <option value="WARNING">WARNING</option>
                        <option value="ERROR">ERROR</option>
                    </select>
                    <select
                        className="form-input form-select"
                        style={{ width: 'auto' }}
                        value={filter.category}
                        onChange={(e) => setFilter(f => ({ ...f, category: e.target.value }))}
                    >
                        <option value="">All Categories</option>
                        <option value="system">System</option>
                        <option value="trade">Trade</option>
                        <option value="risk">Risk</option>
                    </select>
                    <button className="btn btn-outline" onClick={refetch}>
                        <RefreshCw size={16} />
                        Refresh
                    </button>
                </div>
            </div>

            <LogsPanel
                logs={logs || []}
                loading={loading}
                maxHeight="calc(100vh - 200px)"
            />
        </div>
    );
}
