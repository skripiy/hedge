import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

export default function EquityChart({ data = [], loading = false }) {
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);

    useEffect(() => {
        if (!chartContainerRef.current || loading) return;

        // Create chart
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: 'solid', color: '#0d1117' },
                textColor: '#94a3b8',
            },
            grid: {
                vertLines: { color: '#1e293b' },
                horzLines: { color: '#1e293b' },
            },
            width: chartContainerRef.current.clientWidth,
            height: 300,
            rightPriceScale: {
                borderColor: '#1e293b',
            },
            timeScale: {
                borderColor: '#1e293b',
                timeVisible: true,
                secondsVisible: false,
            },
            crosshair: {
                mode: 1,
                vertLine: {
                    color: '#3b82f6',
                    width: 1,
                    style: 2,
                },
                horzLine: {
                    color: '#3b82f6',
                    width: 1,
                    style: 2,
                },
            },
        });

        // Add area series
        const areaSeries = chart.addAreaSeries({
            topColor: 'rgba(59, 130, 246, 0.4)',
            bottomColor: 'rgba(59, 130, 246, 0.0)',
            lineColor: '#3b82f6',
            lineWidth: 2,
        });

        // Transform data for chart
        if (data.length > 0) {
            const chartData = data.map((item) => ({
                time: Math.floor(new Date(item.timestamp).getTime() / 1000),
                value: item.balance,
            }));

            // Sort by time
            chartData.sort((a, b) => a.time - b.time);

            areaSeries.setData(chartData);
            chart.timeScale().fitContent();
        }

        chartRef.current = chart;

        // Handle resize
        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, [data, loading]);

    if (loading) {
        return (
            <div className="chart-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <div className="spinner"></div>
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="chart-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <p style={{ color: 'var(--text-muted)' }}>No trading data available</p>
            </div>
        );
    }

    return <div ref={chartContainerRef} className="chart-container" />;
}
