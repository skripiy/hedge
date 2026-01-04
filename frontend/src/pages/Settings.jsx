import React, { useState, useEffect } from 'react';
import { Save, RefreshCw, Eye, EyeOff } from 'lucide-react';
import * as api from '../api';

export default function Settings() {
    const [config, setConfig] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [showSecrets, setShowSecrets] = useState(false);
    const [message, setMessage] = useState(null);

    // Form state
    const [formData, setFormData] = useState({
        name: '',
        mode: 'simulation',
        virtual_balance: 10000,
        exchange_a: 'binance',
        exchange_b: 'bybit',
        symbol: 'BTC/USDT',
        leverage: 1,
        position_size_usdt: 100,
        stop_loss_percent: 2,
        take_profit_percent: 5,
        spread_threshold: 0.5,
        max_daily_loss: 500,
        taker_fee: 0.1,
        maker_fee: 0.05,
        slippage: 0.05,
        api_key_a: '',
        api_secret_a: '',
        api_key_b: '',
        api_secret_b: '',
    });

    useEffect(() => {
        loadConfig();
    }, []);

    const loadConfig = async () => {
        setLoading(true);
        try {
            const data = await api.getConfig(1);
            setConfig(data);
            setFormData({
                name: data.name || '',
                mode: data.mode || 'simulation',
                virtual_balance: data.virtual_balance || 10000,
                exchange_a: data.exchange_a || 'binance',
                exchange_b: data.exchange_b || 'bybit',
                symbol: data.symbol || 'BTC/USDT',
                leverage: data.leverage || 1,
                position_size_usdt: data.position_size_usdt || 100,
                stop_loss_percent: data.stop_loss_percent || 2,
                take_profit_percent: data.take_profit_percent || 5,
                spread_threshold: data.spread_threshold || 0.5,
                max_daily_loss: data.max_daily_loss || 500,
                taker_fee: data.taker_fee || 0.1,
                maker_fee: data.maker_fee || 0.05,
                slippage: data.slippage || 0.05,
                api_key_a: '',
                api_secret_a: '',
                api_key_b: '',
                api_secret_b: '',
            });
        } catch (error) {
            setMessage({ type: 'error', text: `Failed to load config: ${error.message}` });
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (e) => {
        const { name, value, type } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'number' ? parseFloat(value) || 0 : value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setMessage(null);

        try {
            // Only send non-empty API keys
            const dataToSend = { ...formData };
            if (!dataToSend.api_key_a) delete dataToSend.api_key_a;
            if (!dataToSend.api_secret_a) delete dataToSend.api_secret_a;
            if (!dataToSend.api_key_b) delete dataToSend.api_key_b;
            if (!dataToSend.api_secret_b) delete dataToSend.api_secret_b;

            await api.updateConfig(1, dataToSend);
            setMessage({ type: 'success', text: 'Configuration saved successfully!' });
            loadConfig();
        } catch (error) {
            setMessage({ type: 'error', text: `Failed to save: ${error.message}` });
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="animate-in">
                <div className="page-header">
                    <h1 className="page-title">Settings</h1>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
                    <div className="spinner"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="animate-in">
            <div className="page-header">
                <h1 className="page-title">Settings</h1>
                <button className="btn btn-outline" onClick={loadConfig}>
                    <RefreshCw size={16} />
                    Refresh
                </button>
            </div>

            {message && (
                <div className={`card ${message.type === 'error' ? 'danger' : 'success'}`}
                    style={{ marginBottom: '1.5rem', padding: '1rem' }}>
                    {message.text}
                </div>
            )}

            {config?.status === 'running' && (
                <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem', borderColor: 'var(--warning)' }}>
                    ⚠️ Bot is running. Stop the bot to modify settings.
                </div>
            )}

            <form onSubmit={handleSubmit}>
                <div className="grid-2">
                    {/* General Settings */}
                    <div className="card">
                        <h3 style={{ marginBottom: '1.5rem' }}>General</h3>

                        <div className="form-group">
                            <label className="form-label">Strategy Name</label>
                            <input
                                type="text"
                                name="name"
                                className="form-input"
                                value={formData.name}
                                onChange={handleChange}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Trading Mode</label>
                            <select
                                name="mode"
                                className="form-input form-select"
                                value={formData.mode}
                                onChange={handleChange}
                            >
                                <option value="simulation">Simulation (Paper Trading)</option>
                                <option value="live">Live Trading</option>
                            </select>
                        </div>

                        <div className="form-group">
                            <label className="form-label">Virtual Balance (USDT)</label>
                            <input
                                type="number"
                                name="virtual_balance"
                                className="form-input"
                                value={formData.virtual_balance}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    {/* Trading Parameters */}
                    <div className="card">
                        <h3 style={{ marginBottom: '1.5rem' }}>Trading Parameters</h3>

                        <div className="form-group">
                            <label className="form-label">Symbol</label>
                            <input
                                type="text"
                                name="symbol"
                                className="form-input"
                                value={formData.symbol}
                                onChange={handleChange}
                            />
                        </div>

                        <div className="grid-2">
                            <div className="form-group">
                                <label className="form-label">Exchange A (Long)</label>
                                <select
                                    name="exchange_a"
                                    className="form-input form-select"
                                    value={formData.exchange_a}
                                    onChange={handleChange}
                                >
                                    <option value="binance">Binance</option>
                                    <option value="bybit">Bybit</option>
                                    <option value="okx">OKX</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label className="form-label">Exchange B (Short)</label>
                                <select
                                    name="exchange_b"
                                    className="form-input form-select"
                                    value={formData.exchange_b}
                                    onChange={handleChange}
                                >
                                    <option value="bybit">Bybit</option>
                                    <option value="binance">Binance</option>
                                    <option value="okx">OKX</option>
                                </select>
                            </div>
                        </div>

                        <div className="grid-2">
                            <div className="form-group">
                                <label className="form-label">Position Size (USDT)</label>
                                <input
                                    type="number"
                                    name="position_size_usdt"
                                    className="form-input"
                                    value={formData.position_size_usdt}
                                    onChange={handleChange}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Leverage</label>
                                <input
                                    type="number"
                                    name="leverage"
                                    className="form-input"
                                    min="1"
                                    max="100"
                                    value={formData.leverage}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="form-label">Spread Threshold (%)</label>
                            <input
                                type="number"
                                name="spread_threshold"
                                className="form-input"
                                step="0.1"
                                value={formData.spread_threshold}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    {/* Risk Management */}
                    <div className="card">
                        <h3 style={{ marginBottom: '1.5rem' }}>Risk Management</h3>

                        <div className="grid-2">
                            <div className="form-group">
                                <label className="form-label">Stop Loss (%)</label>
                                <input
                                    type="number"
                                    name="stop_loss_percent"
                                    className="form-input"
                                    step="0.1"
                                    value={formData.stop_loss_percent}
                                    onChange={handleChange}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Take Profit (%)</label>
                                <input
                                    type="number"
                                    name="take_profit_percent"
                                    className="form-input"
                                    step="0.1"
                                    value={formData.take_profit_percent}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>

                        <div className="form-group">
                            <label className="form-label">Max Daily Loss (USDT)</label>
                            <input
                                type="number"
                                name="max_daily_loss"
                                className="form-input"
                                value={formData.max_daily_loss}
                                onChange={handleChange}
                            />
                        </div>

                        <div className="grid-3">
                            <div className="form-group">
                                <label className="form-label">Taker Fee (%)</label>
                                <input
                                    type="number"
                                    name="taker_fee"
                                    className="form-input"
                                    step="0.01"
                                    value={formData.taker_fee}
                                    onChange={handleChange}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Maker Fee (%)</label>
                                <input
                                    type="number"
                                    name="maker_fee"
                                    className="form-input"
                                    step="0.01"
                                    value={formData.maker_fee}
                                    onChange={handleChange}
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Slippage (%)</label>
                                <input
                                    type="number"
                                    name="slippage"
                                    className="form-input"
                                    step="0.01"
                                    value={formData.slippage}
                                    onChange={handleChange}
                                />
                            </div>
                        </div>
                    </div>

                    {/* API Keys */}
                    <div className="card">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <h3>API Keys</h3>
                            <button
                                type="button"
                                className="btn btn-outline"
                                onClick={() => setShowSecrets(!showSecrets)}
                            >
                                {showSecrets ? <EyeOff size={16} /> : <Eye size={16} />}
                                {showSecrets ? 'Hide' : 'Show'}
                            </button>
                        </div>

                        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                            API keys are required for live trading. Leave empty to keep existing keys.
                            {config?.has_api_keys_a && <span className="badge badge-success" style={{ marginLeft: '0.5rem' }}>A: Set</span>}
                            {config?.has_api_keys_b && <span className="badge badge-success" style={{ marginLeft: '0.5rem' }}>B: Set</span>}
                        </p>

                        <div className="form-group">
                            <label className="form-label">Exchange A - API Key</label>
                            <input
                                type={showSecrets ? 'text' : 'password'}
                                name="api_key_a"
                                className="form-input"
                                placeholder="••••••••••••••••"
                                value={formData.api_key_a}
                                onChange={handleChange}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Exchange A - Secret</label>
                            <input
                                type={showSecrets ? 'text' : 'password'}
                                name="api_secret_a"
                                className="form-input"
                                placeholder="••••••••••••••••"
                                value={formData.api_secret_a}
                                onChange={handleChange}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Exchange B - API Key</label>
                            <input
                                type={showSecrets ? 'text' : 'password'}
                                name="api_key_b"
                                className="form-input"
                                placeholder="••••••••••••••••"
                                value={formData.api_key_b}
                                onChange={handleChange}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Exchange B - Secret</label>
                            <input
                                type={showSecrets ? 'text' : 'password'}
                                name="api_secret_b"
                                className="form-input"
                                placeholder="••••••••••••••••"
                                value={formData.api_secret_b}
                                onChange={handleChange}
                            />
                        </div>
                    </div>
                </div>

                <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={saving || config?.status === 'running'}
                    >
                        {saving ? (
                            <div className="spinner" style={{ width: 16, height: 16 }}></div>
                        ) : (
                            <Save size={16} />
                        )}
                        Save Settings
                    </button>
                </div>
            </form>
        </div>
    );
}
