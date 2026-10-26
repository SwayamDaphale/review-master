import { useEffect } from 'react';

export function usePageTitle(title: string): void {
  useEffect(() => {
    const prev = document.title;
    document.title = `${title} — Review Master`;
    return () => {
      document.title = prev;
    };
  }, [title]);
}
