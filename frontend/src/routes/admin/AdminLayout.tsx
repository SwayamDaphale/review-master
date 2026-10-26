import { NavLink, Outlet } from 'react-router-dom';

export default function AdminLayout() {
  const tabs = [
    { label: 'Overview', to: '/admin', end: true },
    { label: 'Catalogue', to: '/admin/catalog' },
    { label: 'Evaluation Models', to: '/admin/models' },
    { label: 'Moderation', to: '/admin/moderation' },
    { label: 'Audit Log', to: '/admin/audit' }
  ];

  return (
    <div className="admin-shell">
      <div className="admin-banner">
        <div className="container row row--between">
          <div className="row">
            <span className="admin-pill">ADMIN CONSOLE</span>
            <span className="small muted">Deterministic evaluation, catalog match review & model governance</span>
          </div>
          <span className="small muted">v1.0-mvp</span>
        </div>
      </div>
      <nav className="admin-subnav" aria-label="Admin Navigation">
        <div className="container">
          <ul className="admin-tab-list">
            {tabs.map((tab) => (
              <li key={tab.to}>
                <NavLink
                  to={tab.to}
                  end={tab.end}
                  className={({ isActive }) => `admin-tab-link ${isActive ? 'is-active' : ''}`}
                >
                  {tab.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      </nav>
      <main className="container admin-content">
        <Outlet />
      </main>
    </div>
  );
}
