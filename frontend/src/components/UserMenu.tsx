import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../state/auth';
import { initials } from '../lib/format';

export function UserMenu() {
  const { session, signOut } = useAuth();
  const navigate = useNavigate();
  if (!session) {
    return (
      <Link to="/login" className="btn btn-secondary btn-sm">
        Sign in
      </Link>
    );
  }
  return (
    <details className="menu">
      <summary aria-label={`Account menu for ${session.name}`}>
        {session.picture ? (
          <img src={session.picture} alt="" className="avatar" referrerPolicy="no-referrer" />
        ) : (
          <span className="avatar avatar--initials">{initials(session.name)}</span>
        )}
      </summary>
      <div className="menu__panel">
        <div className="menu__who">
          <strong>{session.name}</strong>
          <span className="small muted">{session.email}</span>
          {session.provider === 'demo' ? <span className="badge badge-neutral">Demo account</span> : null}
        </div>
        <Link to="/app/saved">Saved and alerts</Link>
        <Link to="/app/account">Account</Link>
        <button
          type="button"
          onClick={() => {
            signOut();
            navigate('/');
          }}
        >
          Sign out
        </button>
      </div>
    </details>
  );
}
