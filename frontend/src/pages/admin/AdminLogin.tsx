import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Logo, ThemeToggle } from '../../components/misc';
import { Notice } from '../../components/states';
import { useAdmin, ADMIN_PASSWORD } from '../../lib/adminAuth';
import { usePageTitle } from '../../lib/hooks';

export default function AdminLogin() {
  usePageTitle('Admin sign in');
  const { isAdmin, login } = useAdmin();
  const navigate = useNavigate();
  const location = useLocation();
  const [password, setPassword] = useState('');
  const [failed, setFailed] = useState(false);
  const from = (location.state as { from?: string } | null)?.from ?? '/admin';

  if (isAdmin) return <Navigate to={from} replace />;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (login(password)) navigate(from, { replace: true });
    else {
      setFailed(true);
      setPassword('');
    }
  };

  return (
    <div className="auth">
      <header className="auth__top">
        <Logo />
        <ThemeToggle />
      </header>
      <main id="main" className="auth__card">
        <h1>Admin sign in</h1>
        <Notice tone="warn">
          Temporary gate for development. The password is checked in the browser, so it does not protect anything real. Real admin
          sign-in arrives with the backend.
        </Notice>
        <form className="stack" onSubmit={submit}>
          <div className="field">
            <label htmlFor="admin-pw">Password</label>
            <input
              id="admin-pw"
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setFailed(false);
              }}
              aria-invalid={failed}
              aria-describedby={failed ? 'admin-pw-error' : undefined}
            />
          </div>
          {failed ? (
            <p id="admin-pw-error" role="alert" className="error-text">
              That password is not correct.
            </p>
          ) : null}
          <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={!password}>
            Sign in
          </button>
        </form>
        {import.meta.env.DEV ? (
          <p className="small muted">
            Development hint: the password is <code>{ADMIN_PASSWORD}</code>. Change it with <code>VITE_ADMIN_PASSWORD</code>.
          </p>
        ) : null}
        <p className="small">
          <Link to="/">Back to the site</Link>
        </p>
      </main>
    </div>
  );
}
