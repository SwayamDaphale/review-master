import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { usePageTitle } from '../../lib/hooks';
import { CATEGORY_LABEL, type Category } from '../../types/api';
import { SearchBox } from '../../components/SearchBox';
import { Tabs } from '../../components/Tabs';
import { ProductRow } from '../../components/ProductRow';
import { MeterLegend } from '../../components/trust';
import { EmptyState, ErrorState, Loading } from '../../components/states';

type Filter = 'all' | Category;

export default function Explore() {
  usePageTitle('Explore');
  const [filter, setFilter] = useState<Filter>('all');
  const { data, isLoading, error } = useQuery({
    queryKey: ['list', filter],
    queryFn: () => api.listProducts(filter === 'all' ? undefined : filter),
  });
  const tabs = [{ id: 'all' as Filter, label: 'All' }, ...(Object.keys(CATEGORY_LABEL) as Category[]).map((c) => ({ id: c as Filter, label: CATEGORY_LABEL[c] }))];

  return (
    <div className="page">
      <section className="explore-hero">
        <h1>What are you thinking of buying?</h1>
        <p className="lead">Search by name, or paste an Amazon India link or product ID to see what we know about it.</p>
        <SearchBox size="lg" autoFocus />
        <p className="small muted">
          Have data from the browser extension? <Link to="/app/import">Import it</Link> to see how it matches.
        </p>
      </section>

      <section className="stack">
        <div className="row row--between">
          <h2>Evaluated products</h2>
          <Tabs label="Category filter" tabs={tabs} value={filter} onChange={setFilter} />
        </div>
        <div role="tabpanel" id={`panel-${filter}`} aria-labelledby={`tab-${filter}`}>
          {isLoading ? (
            <Loading />
          ) : error ? (
            <ErrorState message="The product list could not be loaded. Try again in a moment." />
          ) : !data || data.length === 0 ? (
            <EmptyState title="Nothing here yet" message="No products have been evaluated in this category." />
          ) : (
            <ul className="prow-list">
              {data.map((item) => (
                <ProductRow key={item.variant.id} item={item} />
              ))}
            </ul>
          )}
        </div>
        <MeterLegend />
      </section>
    </div>
  );
}
