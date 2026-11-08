import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { GoogleSignInButton } from '../../components/GoogleSignInButton';
import { Logo, ThemeToggle } from '../../components/misc';
import { Notice } from '../../components/states';
import { isGoogleConfigured } from '../../auth/google';
import { useAuth } from '../../state/auth';
import { usePageTitle } from '../../lib/hooks';

interface LocationState {
  from?: string;
}

export default function AuthPage({ mode }: { mode: 'signin' | 'signup' }) {
  usePageTitle(mode === 'signup' ? 'Create account' : 'Sign in');
  const { session, signInWithGoogle, signInWithEmail, registerWithEmail, signInDemo } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as LocationState | null)?.from ?? '/app';
  const configured = isGoogleConfigured();

  if (session) return <Navigate to={from} replace />;

  const onCredential = (credential: string) => {
    const result = signInWithGoogle(credential);
    if (result.ok) navigate(from, { replace: true });
    else setError(result.error);
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email || !password) {
      setError('Please provide both email and password.');
      return;
    }
    setSubmitting(true);
    try {
      const res =
        mode === 'signup'
          ? await registerWithEmail(email, password, displayName || undefined)
          : await signInWithEmail(email, password);

      if (res.ok) {
        navigate(from, { replace: true });
      } else {
        setError(res.error);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth">
      <header className="auth__top">
        <Logo />
        <ThemeToggle />
      </header>
      <main id="main" className="auth__card">
        <h1>{mode === 'signup' ? 'Create your account' : 'Sign in'}</h1>
        <p className="muted">
          Access verified evaluations, save products, and create multi-variant comparisons.
        </p>

        {error ? <Notice tone="danger">{error}</Notice> : null}

        <form onSubmit={handleEmailSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.25rem' }}>
          {mode === 'signup' && (
            <div>
              <label htmlFor="display_name" className="small muted" style={{ display: 'block', marginBottom: '0.25rem' }}>
                Display Name (Optional)
              </label>
              <input
                id="display_name"
                type="text"
                className="input"
                style={{ width: '100%' }}
                placeholder="Your Name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={submitting}
              />
            </div>
          )}
          <div>
            <label htmlFor="auth_email" className="small muted" style={{ display: 'block', marginBottom: '0.25rem' }}>
              Email Address
            </label>
            <input
              id="auth_email"
              type="email"
              className="input"
              style={{ width: '100%' }}
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={submitting}
            />
          </div>
          <div>
            <label htmlFor="auth_password" className="small muted" style={{ display: 'block', marginBottom: '0.25rem' }}>
              Password
            </label>
            <input
              id="auth_password"
              type="password"
              className="input"
              style={{ width: '100%' }}
              placeholder={mode === 'signup' ? 'Minimum 8 characters' : 'Enter password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={submitting}
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary btn-lg btn-block"
            disabled={submitting}
            style={{ marginTop: '0.5rem' }}
          >
            {submitting ? 'Please wait...' : mode === 'signup' ? 'Create account' : 'Sign in'}
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', margin: '1rem 0', color: 'var(--color-muted)' }}>
          <div style={{ flex: 1, height: '1px', background: 'var(--color-border)' }} />
          <span style={{ padding: '0 0.75rem', fontSize: '0.85rem' }}>or</span>
          <div style={{ flex: 1, height: '1px', background: 'var(--color-border)' }} />
        </div>

        {configured ? (
          <GoogleSignInButton mode={mode} onCredential={onCredential} onError={setError} />
        ) : (
          <button
            type="button"
            className="btn btn-secondary btn-block"
            onClick={() => {
              signInDemo();
              navigate(from, { replace: true });
            }}
          >
            Continue with a demo account
          </button>
        )}

        <p className="small muted">
          Saved products and price alerts stay in this browser for now. We do not have a database yet, so signing in on another
          device starts empty.
        </p>
        <p className="small">
          {mode === 'signup' ? (
            <>
              Already have an account? <Link to="/login">Sign in</Link>
            </>
          ) : (
            <>
              New to Review Master? <Link to="/signup">Create an account</Link>
            </>
          )}
        </p>
      </main>
    </div>
  );
}
