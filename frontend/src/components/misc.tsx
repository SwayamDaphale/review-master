import { Link } from 'react-router-dom';
import type { SpecItem, Variant } from '../types/api';
import { useTheme } from '../state/theme';

export function Logo({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} className="brand" aria-label="Review Master home">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill="var(--accent)" />
        <path d="M8 17.5l5 5L24 10" fill="none" stroke="var(--accent-ink)" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span>Review Master</span>
    </Link>
  );
}

export function ThemeToggle() {
  const { effective, toggle } = useTheme();
  const dark = effective === 'dark';
  return (
    <button
      type="button"
      className="icon-btn"
      onClick={toggle}
      aria-pressed={dark}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {dark ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
        </svg>
      )}
    </button>
  );
}

export function SpecTable({ specs }: { specs: SpecItem[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <caption className="sr-only">Normalised specifications</caption>
        <thead>
          <tr>
            <th scope="col">Specification</th>
            <th scope="col">Value</th>
            <th scope="col">Source</th>
          </tr>
        </thead>
        <tbody>
          {specs.map((s) => (
            <tr key={s.key}>
              <th scope="row">{s.label}</th>
              <td>{s.value ?? <span className="muted">Not captured</span>}</td>
              <td className="small muted">{s.source}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function VariantPicker({
  variants,
  value,
  onChange,
}: {
  variants: Variant[];
  value: string;
  onChange: (id: string) => void;
}) {
  if (variants.length < 2) return null;
  return (
    <div className="variant-picker" role="radiogroup" aria-label="Choose a variant">
      {variants.map((v) => (
        <button
          key={v.id}
          type="button"
          role="radio"
          aria-checked={v.id === value}
          className={v.id === value ? 'chip is-active' : 'chip'}
          onClick={() => onChange(v.id)}
        >
          {v.label}
        </button>
      ))}
    </div>
  );
}
