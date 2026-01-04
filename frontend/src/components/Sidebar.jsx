import React from 'react';
import { NavLink } from 'react-router-dom';
import {
    LayoutDashboard,
    Settings,
    BarChart3,
    ScrollText,
    Activity
} from 'lucide-react';

export default function Sidebar() {
    const navItems = [
        { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
        { to: '/positions', icon: Activity, label: 'Positions' },
        { to: '/analytics', icon: BarChart3, label: 'Analytics' },
        { to: '/logs', icon: ScrollText, label: 'Logs' },
        { to: '/settings', icon: Settings, label: 'Settings' },
    ];

    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <Activity size={28} />
                <h1>HedgeBot</h1>
            </div>

            <nav className="sidebar-nav">
                {navItems.map(({ to, icon: Icon, label }) => (
                    <NavLink
                        key={to}
                        to={to}
                        className={({ isActive }) =>
                            `nav-item ${isActive ? 'active' : ''}`
                        }
                    >
                        <Icon size={20} />
                        <span>{label}</span>
                    </NavLink>
                ))}
            </nav>

            <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    HedgeBot v1.0.0
                </div>
            </div>
        </aside>
    );
}
