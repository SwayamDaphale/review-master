import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { Logo, ThemeToggle } from '../components/misc';
import { UserMenu } from '../components/UserMenu';
import { SearchBox } from '../components/SearchBox';
import { SampleBadge } from '../components/trust';
import { Notice } from '../components/states';
import { useSiteSettings } from '../state/siteSettings';
import { useAdmin } from '../lib/adminAuth';

function SiteBanner() {
  const [settings] = useSiteSettings();
  if (!settings.bannerEnabled || !settings.bannerText.trim()) return null;
  return (
    <div className="banner" role="status">
      {settings.bannerText}
    </div>
  );
}

function ScrollManager() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (hash) {
      document.getElementById(hash.slice(1))?.scrollIntoView();
    } else {
      window.scrollTo(0, 0);
    }
  }, [pathname, hash]);
  return null;
}

function SkipLink() {
  return (
    <a className="skip-link" href="#main">
      Skip to content
    </a>
  );
}

export function PublicLayout() {
  const [menu, setMenu] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setMenu(false), [pathname]);
  const links = (
    <>
      <Link to="/#how">How it works</Link>
      <Link to="/#categories">Categories</Link>
      <NavLink to="/extension">Extension</NavLink>
      <Link to="/#privacy">Privacy</Link>
    </>
  );
  return (
    <>
      <SkipLink />
      <ScrollManager />
      <SiteBanner />
      <header className="site-header">
        <div className="container site-header__inner">
          <Logo />
          <nav className="nav nav--desktop" aria-label="Main">
            {links}
          </nav>
          <div className="header-actions">
            <ThemeToggle />
            <UserMenu />
            <Link to="/app" className="btn btn-primary btn-sm">
              Open the app
            </Link>
            <button
              type="button"
              className="icon-btn nav-toggle"
              aria-expanded={menu}
              aria-controls="mobile-nav"
              aria-label="Menu"
              onClick={() => setMenu((m) => !m)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
          </div>
        </div>
        {menu ? (
          <nav id="mobile-nav" className="nav nav--mobile container" aria-label="Main">
            {links}
          </nav>
        ) : null}
      </header>
      <main id="main">
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="container site-footer__inner">
          <div>
            <Logo />
            <p className="small muted footer-note">
              Review Master is in development. Every score you can open today is sample data and is labelled that way.
            </p>
          </div>
          <nav className="footer-links" aria-label="Footer">
            <Link to="/app">Open the app</Link>
            <Link to="/extension">Browser extension</Link>
            <Link to="/login">Sign in</Link>
            <Link to="/admin/login">Admin</Link>
          </nav>
        </div>
      </footer>
    </>
  );
}

export function AppLayout() {
  const [settings] = useSiteSettings();
  const { isAdmin } = useAdmin();
  const { pathname } = useLocation();
  const [menu, setMenu] = useState(false);
  useEffect(() => setMenu(false), [pathname]);
  const onExplore = pathname === '/app' || pathname === '/app/';
  const nav = (
    <>
      <NavLink to="/app" end>
        Explore
      </NavLink>
      {settings.features.compare ? <NavLink to="/app/compare">Compare</NavLink> : null}
      <NavLink to="/app/recommendations">Recommendations</NavLink>
      <NavLink to="/app/saved">Saved</NavLink>
      {settings.features.importTool ? <NavLink to="/app/import">Import</NavLink> : null}
    </>
  );
  return (
    <>
      <SkipLink />
      <ScrollManager />
      <SiteBanner />
      <header className="site-header">
        <div className="container site-header__inner">
          <Logo to="/app" />
          <nav className="nav nav--desktop" aria-label="App">
            {nav}
          </nav>
          {!onExplore ? (
            <div className="header-search">
              <SearchBox size="sm" />
            </div>
          ) : null}
          <div className="header-actions">
            <ThemeToggle />
            <UserMenu />
            <button
              type="button"
              className="icon-btn nav-toggle"
              aria-expanded={menu}
              aria-controls="app-mobile-nav"
              aria-label="Menu"
              onClick={() => setMenu((m) => !m)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
          </div>
        </div>
        {menu ? (
          <nav id="app-mobile-nav" className="nav nav--mobile container" aria-label="App">
            {nav}
          </nav>
        ) : null}
      </header>
      <main id="main" className="container app-main">
        {settings.showSampleNotice ? (
          <div className="sample-strip">
            <SampleBadge />
            <span className="small muted">
              The scores here are placeholders for demonstration. They are not real evaluations.
            </span>
          </div>
        ) : null}
        {settings.maintenance ? (
          isAdmin ? (
            <>
              <Notice tone="warn">Maintenance mode is on. Visitors see the maintenance page; you can see the app because you are signed in as admin.</Notice>
              <Outlet />
            </>
          ) : (
            <div className="state">
              <strong>Review Master is down for maintenance</strong>
              <span className="muted">We are updating the app. Please check back soon.</span>
            </div>
          )
        ) : (
          <Outlet />
        )}
      </main>
    </>
  );
}

export function AdminLayout() {
  const { logout } = useAdmin();
  const items: [string, string][] = [
    ['/admin', 'Overview'],
    ['/admin/catalog', 'Catalogue'],
    ['/admin/models', 'Evaluation models'],
    ['/admin/moderation', 'Moderation'],
    ['/admin/users', 'Users'],
    ['/admin/settings', 'Site settings'],
    ['/admin/audit', 'Audit log'],
  ];
  return (
    <div className="admin-shell">
      <SkipLink />
      <aside className="admin-side">
        <Logo to="/admin" />
        <span className="badge badge-neutral">Admin</span>
        <nav aria-label="Admin">
          {items.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/admin'}>
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="admin-main">
        <header className="admin-top">
          <Notice tone="warn">
            Development gate: the admin password is checked in the browser, and changes are stored in this browser only.
          </Notice>
          <div className="header-actions">
            <ThemeToggle />
            <Link to="/" className="btn btn-secondary btn-sm">
              View site
            </Link>
            <button type="button" className="btn btn-ghost btn-sm" onClick={logout}>
              Sign out
            </button>
          </div>
        </header>
        <main id="main" className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
