import React from 'react';
import { Play, Square, AlertTriangle } from 'lucide-react';

export default function ControlPanel({
    status,
    onStart,
    onStop,
    onPanic,
    loading = false,
    disabled = false
}) {
    const isRunning = status === 'running';

    return (
        <div className="card">
            <div className="card-header">
                <h3 className="card-title">Bot Control</h3>
                <div className="status-indicator">
                    <span className={`status-dot ${status || 'stopped'}`}></span>
                    <span style={{ textTransform: 'capitalize' }}>{status || 'Stopped'}</span>
                </div>
            </div>

            <div className="btn-group" style={{ marginTop: '1rem' }}>
                {!isRunning ? (
                    <button
                        className="btn btn-success"
                        onClick={onStart}
                        disabled={loading || disabled}
                    >
                        {loading ? (
                            <div className="spinner" style={{ width: 16, height: 16 }}></div>
                        ) : (
                            <Play size={16} />
                        )}
                        Start Bot
                    </button>
                ) : (
                    <button
                        className="btn btn-outline"
                        onClick={onStop}
                        disabled={loading || disabled}
                    >
                        {loading ? (
                            <div className="spinner" style={{ width: 16, height: 16 }}></div>
                        ) : (
                            <Square size={16} />
                        )}
                        Stop Bot
                    </button>
                )}

                <button
                    className="btn btn-panic"
                    onClick={onPanic}
                    disabled={loading || disabled}
                >
                    <AlertTriangle size={16} />
                    PANIC CLOSE
                </button>
            </div>

            {isRunning && (
                <p style={{
                    marginTop: '1rem',
                    fontSize: '0.75rem',
                    color: 'var(--text-muted)'
                }}>
                    Bot is actively monitoring markets...
                </p>
            )}
        </div>
    );
}
