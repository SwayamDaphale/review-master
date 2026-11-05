import { useEffect, useState } from 'react';

export function useDebounced<T>(value: T, delayMs = 200): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = title ? `${title} | Review Master` : 'Review Master: product scores you can check';
  }, [title]);
}
