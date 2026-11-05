import { Link } from 'react-router-dom';
import { usePageTitle } from '../../lib/hooks';

export default function NotFound() {
  usePageTitle('Page not found');
  return (
    <div className="container container--narrow page stack">
      <h1>We could not find that page</h1>
      <p className="muted">The link may be old or mistyped.</p>
      <div className="row">
        <Link to="/" className="btn btn-secondary">Go to the home page</Link>
        <Link to="/app" className="btn btn-primary">Open the app</Link>
      </div>
    </div>
  );
}
