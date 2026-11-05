import { useEffect, useRef } from 'react';
import { GOOGLE_CLIENT_ID, loadGoogleScript } from '../auth/google';
import { useTheme } from '../state/theme';

/** Renders the official Google button. Needs VITE_GOOGLE_CLIENT_ID; the page shows a demo option otherwise. */
export function GoogleSignInButton({
  mode,
  onCredential,
  onError,
}: {
  mode: 'signin' | 'signup';
  onCredential: (credential: string) => void;
  onError: (message: string) => void;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const { effective } = useTheme();
  const handlers = useRef({ onCredential, onError });
  handlers.current = { onCredential, onError };

  useEffect(() => {
    let cancelled = false;
    loadGoogleScript()
      .then(() => {
        const el = holder.current;
        if (cancelled || !el || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (r) => handlers.current.onCredential(r.credential),
          auto_select: false,
          cancel_on_tap_outside: true,
        });
        el.innerHTML = '';
        window.google.accounts.id.renderButton(el, {
          type: 'standard',
          theme: effective === 'dark' ? 'filled_black' : 'outline',
          size: 'large',
          text: mode === 'signup' ? 'signup_with' : 'signin_with',
          shape: 'rectangular',
          logo_alignment: 'left',
          width: 320,
        });
      })
      .catch(() => {
        if (!cancelled) {
          handlers.current.onError(
            'Google sign-in could not load. Check your connection or any content blocker, then reload the page.',
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [effective, mode]);

  return <div ref={holder} className="google-btn" aria-label="Sign in with Google" />;
}
