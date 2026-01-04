import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Trash2, Save, Search, ToggleLeft, ToggleRight } from 'lucide-react';
import { usePolling } from '../hooks';
import * as api from '../api';

export default function Symbols() {
    const [markets, setMarkets] = useState([]);
    const [marketInfo, setMarketInfo] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [loadingMarkets, setLoadingMarkets] = useState(false);
    const [message, setMessage] = useState(null);

    // Get configured symbols
    const { data: symbols, loading, refetch } = usePolling(
        useCallback(() => api.getSymbols(1), []),
        10000
    );

    // Load available markets (common to both exchanges)
    const loadMarkets = async () => {
        setLoadingMarkets(true);
        try {
            const data = await api.getMarkets(1);
            setMarkets(data.markets || []);
            setMarketInfo({
                exchange_a: data.exchange_a,
                exchange_b: data.exchange_b,
                total_a: data.total_a,
                total_b: data.total_b,
                common: data.count
            });
        } catch (error) {
            setMessage({ type: 'error', text: `Failed to load markets: ${error.message}` });
        } finally {
            setLoadingMarkets(false);
        }
    };

    useEffect(() => {
        loadMarkets();
    }, []);

    // Filter markets by search
    const filteredMarkets = markets.filter(m =>
        m.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
        m.base.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Get already configured symbol names
    const configuredSymbolNames = new Set((symbols || []).map(s => s.symbol));

    const handleAddSymbol = async (symbol) => {
        try {
            await api.addSymbol(symbol);
            setMessage({ type: 'success', text: `Added ${symbol}` });
            refetch();
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        }
    };

    const handleDeleteSymbol = async (symbolId, symbolName) => {
        if (!confirm(`Remove ${symbolName} from monitoring?`)) return;

        try {
            await api.deleteSymbol(symbolId);
            setMessage({ type: 'success', text: `Removed ${symbolName}` });
            refetch();
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        }
    };

    const handleToggleSymbol = async (symbolId, currentEnabled) => {
        try {
            await api.updateSymbol(symbolId, { enabled: !currentEnabled });
            refetch();
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        }
    };

    const handleUpdateSymbol = async (symbolId, field, value) => {
        try {
            await api.updateSymbol(symbolId, { [field]: value });
            refetch();
        } catch (error) {
            setMessage({ type: 'error', text: error.message });
        }
    };

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Symbols</h1>
                <span style={{ color: 'var(--text-muted)' }}>
                    {symbols?.length || 0} configured
                </span>
            </div>

            {message && (
                <div className={`card ${message.type === 'error' ? 'danger' : 'success'}`}
                    style={{ marginBottom: '1rem', padding: '0.75rem' }}>
                    {message.text}
                    <button
                        onClick={() => setMessage(null)}
                        style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
                    >×</button>
                </div>
            )}

            <div className="grid-2">
                {/* Configured Symbols */}
                <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                    <div className="card-header" style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border-color)' }}>
                        <h3 className="card-title">Configured Symbols</h3>
                    </div>

                    {loading ? (
                        <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                            <div className="spinner"></div>
                        </div>
                    ) : symbols?.length === 0 ? (
                        <div className="empty-state" style={{ padding: '2rem' }}>
                            <p>No symbols configured yet</p>
                            <p style={{ fontSize: '0.75rem' }}>Add symbols from the list on the right</p>
                        </div>
                    ) : (
                        <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
                            {symbols.map((symbol) => (
                                <SymbolRow
                                    key={symbol.id}
                                    symbol={symbol}
                                    onToggle={() => handleToggleSymbol(symbol.id, symbol.enabled)}
                                    onDelete={() => handleDeleteSymbol(symbol.id, symbol.symbol)}
                                    onUpdate={(field, value) => handleUpdateSymbol(symbol.id, field, value)}
                                />
                            ))}
                        </div>
                    )}
                </div>

                {/* Available Markets */}
                <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                    <div className="card-header" style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border-color)' }}>
                        <h3 className="card-title">Available Markets</h3>
                        {marketInfo && (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                {marketInfo.common} common ({marketInfo.exchange_a} ∩ {marketInfo.exchange_b})
                            </span>
                        )}
                    </div>

                    <div style={{ padding: '0.5rem 1rem', borderBottom: '1px solid var(--border-color)' }}>
                        <div style={{ position: 'relative' }}>
                            <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                            <input
                                type="text"
                                className="form-input"
                                placeholder="Search symbols..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                style={{ paddingLeft: '2.5rem' }}
                            />
                        </div>
                    </div>

                    {loadingMarkets ? (
                        <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
                            <div className="spinner"></div>
                        </div>
                    ) : (
                        <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
                            {filteredMarkets.map((market) => (
                                <div
                                    key={market.symbol}
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                        padding: '0.5rem 1rem',
                                        borderBottom: '1px solid var(--border-color)',
                                        opacity: configuredSymbolNames.has(market.symbol) ? 0.5 : 1
                                    }}
                                >
                                    <div>
                                        <strong>{market.symbol}</strong>
                                        <span style={{ marginLeft: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                            {market.type}
                                        </span>
                                    </div>
                                    <button
                                        className="btn btn-outline"
                                        style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                                        onClick={() => handleAddSymbol(market.symbol)}
                                        disabled={configuredSymbolNames.has(market.symbol)}
                                    >
                                        <Plus size={14} />
                                        Add
                                    </button>
                                </div>
                            ))}
                            {filteredMarkets.length === 0 && searchTerm && (
                                <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                                    No results for "{searchTerm}"
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function SymbolRow({ symbol, onToggle, onDelete, onUpdate }) {
    const [editing, setEditing] = useState(false);
    const [values, setValues] = useState({
        position_size_usdt: symbol.position_size_usdt,
        spread_threshold: symbol.spread_threshold,
        stop_loss_percent: symbol.stop_loss_percent,
        take_profit_percent: symbol.take_profit_percent,
    });

    const handleSave = () => {
        Object.entries(values).forEach(([key, value]) => {
            if (value !== symbol[key]) {
                onUpdate(key, value);
            }
        });
        setEditing(false);
    };

    return (
        <div style={{
            padding: '1rem',
            borderBottom: '1px solid var(--border-color)',
            background: symbol.enabled ? 'transparent' : 'rgba(0,0,0,0.2)'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <button onClick={onToggle} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                        {symbol.enabled ? (
                            <ToggleRight size={24} style={{ color: 'var(--success)' }} />
                        ) : (
                            <ToggleLeft size={24} style={{ color: 'var(--text-muted)' }} />
                        )}
                    </button>
                    <strong style={{ color: symbol.enabled ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                        {symbol.symbol}
                    </strong>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {editing ? (
                        <button className="btn btn-success" onClick={handleSave} style={{ padding: '0.25rem 0.5rem' }}>
                            <Save size={14} />
                        </button>
                    ) : (
                        <button className="btn btn-outline" onClick={() => setEditing(true)} style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}>
                            Edit
                        </button>
                    )}
                    <button className="btn btn-outline" onClick={onDelete} style={{ padding: '0.25rem 0.5rem', color: 'var(--danger)' }}>
                        <Trash2 size={14} />
                    </button>
                </div>
            </div>

            {editing ? (
                <div className="grid-2" style={{ gap: '0.5rem', marginTop: '0.5rem' }}>
                    <div>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Size (USDT)</label>
                        <input
                            type="number"
                            className="form-input"
                            value={values.position_size_usdt}
                            onChange={(e) => setValues({ ...values, position_size_usdt: parseFloat(e.target.value) })}
                            style={{ padding: '0.25rem 0.5rem' }}
                        />
                    </div>
                    <div>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Spread %</label>
                        <input
                            type="number"
                            className="form-input"
                            value={values.spread_threshold}
                            onChange={(e) => setValues({ ...values, spread_threshold: parseFloat(e.target.value) })}
                            step="0.1"
                            style={{ padding: '0.25rem 0.5rem' }}
                        />
                    </div>
                    <div>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Stop Loss %</label>
                        <input
                            type="number"
                            className="form-input"
                            value={values.stop_loss_percent}
                            onChange={(e) => setValues({ ...values, stop_loss_percent: parseFloat(e.target.value) })}
                            step="0.1"
                            style={{ padding: '0.25rem 0.5rem' }}
                        />
                    </div>
                    <div>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Take Profit %</label>
                        <input
                            type="number"
                            className="form-input"
                            value={values.take_profit_percent}
                            onChange={(e) => setValues({ ...values, take_profit_percent: parseFloat(e.target.value) })}
                            step="0.1"
                            style={{ padding: '0.25rem 0.5rem' }}
                        />
                    </div>
                </div>
            ) : (
                <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    <span>Size: ${symbol.position_size_usdt}</span>
                    <span>Spread: {symbol.spread_threshold}%</span>
                    <span>SL: {symbol.stop_loss_percent}%</span>
                    <span>TP: {symbol.take_profit_percent}%</span>
                </div>
            )}
        </div>
    );
}
