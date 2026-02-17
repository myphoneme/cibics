import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import { ThemeToggle } from './ThemeToggle';

const SIDEBAR_KEY = 'cibics_sidebar_collapsed';

export function ShellLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    const saved = localStorage.getItem(SIDEBAR_KEY);
    if (saved !== null) {
      return saved === '1';
    }
    return window.innerWidth < 980;
  });

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0');
  }, [collapsed]);

  function signOut() {
    logout();
    navigate('/login');
  }

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="sidebar-head">
          <button
            type="button"
            className="icon-btn"
            onClick={() => setCollapsed((prev) => !prev)}
            title={collapsed ? 'Expand menu' : 'Collapse menu'}
          >
            <IconMenu />
          </button>
          <div className="brand-wrap">
            <div className="brand">CIBICS</div>
            <div className="brand-sub">Tracking</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <NavItem to="/dashboard" label="Dashboard" icon={<IconDashboard />} collapsed={collapsed} end />
          <NavItem to="/records" label="Records" icon={<IconRecords />} collapsed={collapsed} end />
          {user?.role === 'SUPER_ADMIN' ? (
            <NavItem to="/records/excel-upload" label="Excel Upload" icon={<IconUpload />} collapsed={collapsed} end />
          ) : null}
          <NavItem to="/users" label={user?.role === 'SUPER_ADMIN' ? 'Users' : 'Profile'} icon={<IconUsers />} collapsed={collapsed} end />
        </nav>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <button
            type="button"
            className="icon-btn mobile-only"
            onClick={() => setCollapsed((prev) => !prev)}
            title={collapsed ? 'Open menu' : 'Close menu'}
          >
            <IconMenu />
          </button>
          <div className="user-tag">{user?.full_name} ({user?.role})</div>
          <div className="topbar-right">
            <ThemeToggle />
            <button type="button" className="btn btn-outline" onClick={signOut}>
              Logout
            </button>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}

function NavItem({
  to,
  label,
  icon,
  collapsed,
  end = false,
}: {
  to: string;
  label: string;
  icon: React.ReactNode;
  collapsed: boolean;
  end?: boolean;
}) {
  return (
    <NavLink to={to} className="sidebar-link" title={label} end={end}>
      <span className="nav-icon">{icon}</span>
      <span className={`nav-label ${collapsed ? 'is-hidden' : ''}`}>{label}</span>
    </NavLink>
  );
}

function IconMenu() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="svg-icon">
      <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function IconDashboard() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="svg-icon">
      <rect x="3" y="3" width="8" height="8" rx="2" stroke="currentColor" fill="none" strokeWidth="2" />
      <rect x="13" y="3" width="8" height="5" rx="2" stroke="currentColor" fill="none" strokeWidth="2" />
      <rect x="13" y="10" width="8" height="11" rx="2" stroke="currentColor" fill="none" strokeWidth="2" />
      <rect x="3" y="13" width="8" height="8" rx="2" stroke="currentColor" fill="none" strokeWidth="2" />
    </svg>
  );
}

function IconRecords() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="svg-icon">
      <rect x="4" y="4" width="16" height="16" rx="2" stroke="currentColor" fill="none" strokeWidth="2" />
      <path d="M8 9h8M8 13h8M8 17h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function IconUsers() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="svg-icon">
      <circle cx="9" cy="9" r="3" stroke="currentColor" fill="none" strokeWidth="2" />
      <path d="M3.5 18a5.5 5.5 0 0 1 11 0" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" />
      <circle cx="17" cy="9" r="2" stroke="currentColor" fill="none" strokeWidth="2" />
      <path d="M14.5 17.5a4 4 0 0 1 6 0" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function IconUpload() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="svg-icon">
      <path d="M12 4v10M8 8l4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" stroke="currentColor" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
