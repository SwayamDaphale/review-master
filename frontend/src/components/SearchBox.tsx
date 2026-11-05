import { useId, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import { parseIdentifier } from '../lib/identifiers';
import { useDebounced } from '../lib/hooks';
import { productPath } from '../lib/routes';

export function SearchBox({
  size = 'md',
  initial = '',
  autoFocus = false,
}: {
  size?: 'sm' | 'md' | 'lg';
  initial?: string;
  autoFocus?: boolean;
}) {
  const id = useId();
  const [value, setValue] = useState(initial);
  const [open, setOpen] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  const navigate = useNavigate();
  const debounced = useDebounced(value.trim(), 200);
  const plainText = parseIdentifier(debounced).kind === 'text';

  const { data } = useQuery({
    queryKey: ['suggest', debounced],
    queryFn: () => api.searchProducts(debounced),
    enabled: open && debounced.length >= 2 && plainText,
  });
  const suggestions = (data ?? []).slice(0, 5);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    setOpen(false);
    navigate(`/app/search?q=${encodeURIComponent(q)}`);
  };

  return (
    <form
      ref={formRef}
      role="search"
      className={`searchbox searchbox--${size}`}
      onSubmit={submit}
      onBlur={(e) => {
        if (!formRef.current?.contains(e.relatedTarget as Node | null)) setOpen(false);
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') setOpen(false);
      }}
    >
      <label className="sr-only" htmlFor={id}>
        Search products
      </label>
      <input
        id={id}
        className="input"
        type="search"
        placeholder="Search a phone, laptop or SSD, or paste an Amazon India link"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        autoComplete="off"
        autoFocus={autoFocus}
      />
      <button type="submit" className="btn btn-primary">
        Search
      </button>
      {open && suggestions.length > 0 ? (
        <ul className="suggest" aria-label="Suggestions">
          {suggestions.map((s) => (
            <li key={s.variant.id}>
              <Link to={productPath(s)} onClick={() => setOpen(false)}>
                <span>{s.product.name}</span>
                <span className="small muted">{s.variant.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </form>
  );
}
