import { useMemo } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { parseIdentifier } from '../../lib/identifiers';
import { usePageTitle } from '../../lib/hooks';
import { productPath } from '../../lib/routes';
import { ProductRow } from '../../components/ProductRow';
import { MatchBadge } from '../../components/MatchBadge';
import { EmptyState, ErrorState, Loading, Notice } from '../../components/states';

export default function SearchPage() {
  const [params] = useSearchParams();
  const q = (params.get('q') ?? '').trim();
  usePageTitle(q ? `Search: ${q}` : 'Search');
  const parsed = useMemo(() => parseIdentifier(q), [q]);
  const isIdentifier = parsed.kind !== 'text';

  const lookup = useQuery({
    queryKey: ['lookup', q],
    queryFn: () => api.lookupIdentifier(parsed),
    enabled: isIdentifier,
  });
  const search = useQuery({
    queryKey: ['search', q],
    queryFn: () => api.searchProducts(q),
    enabled: !isIdentifier && q.length > 0,
  });

  if (!q) {
    return <EmptyState title="Type something to search" message="Search by product name, or paste an Amazon India link or product ID." />;
  }

  if (isIdentifier) {
    if (lookup.isLoading) return <Loading label="Identifying this product" />;
    if (lookup.error || !lookup.data) return <ErrorState message="This link could not be checked. Try again in a moment." />;
    const r = lookup.data;
    const only = r.candidates.length === 1 ? r.candidates[0] : undefined;
    if (only) return <Navigate to={productPath(only)} replace />;
    return (
      <div className="page stack">
        <h1>Product lookup</h1>
        <p className="muted break">{q}</p>
        <p>
          <MatchBadge state={r.match_state} />
        </p>
        <Notice tone={r.candidates.length ? 'info' : 'warn'}>{r.reason}</Notice>
        {r.candidates.length > 0 ? (
          <ul className="prow-list">
            {r.candidates.map((c) => (
              <ProductRow key={c.variant.id} item={c} />
            ))}
          </ul>
        ) : (
          <div className="stack">
            <p>
              There is no evaluation for this product yet, so no score is shown. A missing evaluation is not a low score.
            </p>
            <p>
              If you have the browser extension, capture the page and <Link to="/app/import">import the data</Link> to see how it
              is read.
            </p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="page stack">
      <h1>Results for “{q}”</h1>
      {search.isLoading ? (
        <Loading />
      ) : search.error ? (
        <ErrorState message="Search failed. Try again in a moment." />
      ) : !search.data || search.data.length === 0 ? (
        <EmptyState
          title="No products found"
          message="Try the model name only, for example “Galaxy S25 Ultra”, or paste an Amazon India link."
        />
      ) : (
        <ul className="prow-list">
          {search.data.map((item) => (
            <ProductRow key={item.variant.id} item={item} />
          ))}
        </ul>
      )}
    </div>
  );
}
