import { Shield, Lock, Terminal, FileCode } from 'lucide-react';
import { Link } from 'react-router-dom';

export function Footer() {
  return (
    <footer className="footer">
      <div className="container stack stack--lg">
        <div className="footer-grid">
          <div className="stack stack--tight">
            <div className="row">
              <Shield className="brand-accent" size={20} />
              <strong className="footer-heading">REVIEW MASTER V1.0</strong>
            </div>
            <p className="small muted">
              Evidence-driven, deterministic product evaluation engine. Mathematical scoring from published category models,
              transparent lab benchmarks, and review fraud detection.
            </p>
            <div className="security-badges row">
              <span className="badge badge-high small">
                <Lock size={12} /> Trivy Verified
              </span>
              <span className="badge badge-high small">
                <Terminal size={12} /> Gitleaks Clean
              </span>
              <span className="badge badge-moderate small">
                <FileCode size={12} /> MV3 Permission Gate Passed
              </span>
            </div>
          </div>

          <div className="footer-col">
            <span className="footer-title">Platform</span>
            <ul className="footer-link-list">
              <li><Link to="/catalog">Browse Catalogue</Link></li>
              <li><Link to="/compare">Side-by-Side Compare</Link></li>
              <li><Link to="/saved">Price Drop Alerts</Link></li>
              <li><Link to="/admin">Governance & Models</Link></li>
            </ul>
          </div>

          <div className="footer-col">
            <span className="footer-title">Evaluation Models</span>
            <ul className="footer-link-list">
              <li><Link to="/catalog?category=smartphone">Smartphones (v1.0)</Link></li>
              <li><Link to="/catalog?category=laptop">Laptops (Draft)</Link></li>
              <li><Link to="/catalog?category=ssd">External SSDs (v1.0)</Link></li>
              <li><Link to="/admin/models">Model Parameter Registry</Link></li>
            </ul>
          </div>

          <div className="footer-col">
            <span className="footer-title">Integrity & Rules</span>
            <ul className="footer-link-list">
              <li><span className="small muted">Deterministic core; LLM never generates scores.</span></li>
              <li><span className="small muted">Confidence is first-class and separate from scores.</span></li>
              <li><span className="small muted">No private browsing history or cookie inspection.</span></li>
            </ul>
          </div>
        </div>

        <div className="footer-bottom row row--between">
          <span className="small muted">© 2026 Review Master Architecture. Released under single project repository.</span>
          <span className="small muted">Local Development Mode · API on localhost:8000</span>
        </div>
      </div>
    </footer>
  );
}
