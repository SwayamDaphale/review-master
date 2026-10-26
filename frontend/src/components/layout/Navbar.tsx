import { Link, NavLink } from 'react-router-dom';
import { ShieldCheck, Search, Scale, Bookmark, SlidersHorizontal } from 'lucide-react';

export function Navbar() {
  return (
    <header className="navbar">
      <div className="container row row--between">
        <Link to="/" className="brand-logo" aria-label="Review Master Home">
          <div className="logo-icon-wrap">
            <ShieldCheck className="logo-icon" size={24} />
          </div>
          <div className="brand-text">
            <span className="brand-title">REVIEW MASTER</span>
            <span className="brand-tag">DETERMINISTIC EVALUATION</span>
          </div>
        </Link>

        <nav className="nav-links" aria-label="Main Navigation">
          <NavLink to="/catalog" className={({ isActive }) => `nav-link ${isActive ? 'is-active' : ''}`}>
            <Search size={16} />
            <span>Catalogue</span>
          </NavLink>
          <NavLink to="/compare" className={({ isActive }) => `nav-link ${isActive ? 'is-active' : ''}`}>
            <Scale size={16} />
            <span>Compare</span>
          </NavLink>
          <NavLink to="/saved" className={({ isActive }) => `nav-link ${isActive ? 'is-active' : ''}`}>
            <Bookmark size={16} />
            <span>Saved & Alerts</span>
          </NavLink>
          <NavLink to="/admin" className={({ isActive }) => `nav-link nav-link--admin ${isActive ? 'is-active' : ''}`}>
            <SlidersHorizontal size={16} />
            <span>Admin</span>
          </NavLink>
        </nav>

        <div className="nav-actions">
          <a
            href="https://github.com/SwayamDaphale/review-master"
            target="_blank"
            rel="noreferrer"
            className="btn btn-ghost btn-sm"
          >
            GitHub
          </a>
          <Link to="/catalog" className="btn btn-primary btn-sm">
            Launch App
          </Link>
        </div>
      </div>
    </header>
  );
}
