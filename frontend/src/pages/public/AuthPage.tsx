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
  const { session, signInWithGoogle, signInDemo } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const from = (location.state as LocationState | null)?.from ?? '/app';
  const configured = isGoogleConfigured();

  if (session) return <Navigate to={from} replace />;

  const onCredential = (credential: string) => {
    const result = signInWithGoogle(credential);
    if (result.ok) navigate(from, { replace: true });
    else setError(result.error);
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
          One Google sign-in does both. If this is your first time, your Review Master account is created for you.
        </p>

        {error ? <Notice tone="danger">{error}</Notice> : null}

        {configured ? (
          <GoogleSignInButton mode={mode} onCredential={onCredential} onError={setError} />
        ) : (
          <>
            <Notice tone="warn">
              Google sign-in is not set up yet. Add <code>VITE_GOOGLE_CLIENT_ID</code> to <code>frontend/.env.local</code> and
              restart the dev server. Until then you can continue with a demo account.
            </Notice>
            <button
              type="button"
              className="btn btn-primary btn-lg btn-block"
              onClick={() => {
                signInDemo();
                navigate(from, { replace: true });
              }}
            >
              Continue with a demo account
            </button>
          </>
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
