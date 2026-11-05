import { useState } from 'react';
import { useAuth } from '../../state/auth';
import { useTheme, type ThemePreference } from '../../state/theme';
import { clearAllAppStorage } from '../../lib/storage';
import { usePageTitle } from '../../lib/hooks';
import { initials } from '../../lib/format';
import { Notice } from '../../components/states';

const THEMES: [ThemePreference, string][] = [
  ['light', 'Light'],
  ['dark', 'Dark'],
  ['system', 'Match my device'],
];

export default function AccountPage() {
  usePageTitle('Account');
  const { session, signOut } = useAuth();
  const { preference, setPreference } = useTheme();
  const [confirm, setConfirm] = useState(false);
  if (!session) return null;

  return (
    <div className="page container--narrow stack stack--lg">
      <h1>Account</h1>
      <section className="stack" aria-labelledby="profile-h">
        <h2 id="profile-h">Profile</h2>
        <div className="row">
          {session.picture ? (
            <img src={session.picture} alt="" className="avatar avatar--lg" referrerPolicy="no-referrer" />
          ) : (
            <span className="avatar avatar--lg avatar--initials">{initials(session.name)}</span>
          )}
          <div>
            <strong>{session.name}</strong>
            <div className="muted">{session.email}</div>
            <div className="small muted">
              Signed in with {session.provider === 'google' ? 'Google' : 'a demo account'}
            </div>
          </div>
        </div>
      </section>

      <section className="stack" aria-labelledby="theme-h">
        <h2 id="theme-h">Appearance</h2>
        <div role="radiogroup" aria-label="Theme" className="variant-picker">
          {THEMES.map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={preference === id}
              className={preference === id ? 'chip is-active' : 'chip'}
              onClick={() => setPreference(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      <section className="stack" aria-labelledby="data-h">
        <h2 id="data-h">Your data</h2>
        <Notice tone="info">
          There is no database yet. Your saved products, alerts and settings live in this browser only. Clearing them cannot be
          undone.
        </Notice>
        {confirm ? (
          <div className="row">
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => {
                clearAllAppStorage();
                setConfirm(false);
              }}
            >
              Yes, clear everything stored here
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setConfirm(false)}>
              Cancel
            </button>
          </div>
        ) : (
          <div>
            <button type="button" className="btn btn-secondary" onClick={() => setConfirm(true)}>
              Clear data stored in this browser
            </button>
          </div>
        )}
      </section>

      <div>
        <button type="button" className="btn btn-secondary" onClick={signOut}>
          Sign out
        </button>
      </div>
    </div>
  );
}
