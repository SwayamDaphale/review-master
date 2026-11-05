import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { usePageTitle } from '../../lib/hooks';
import { formatDate, formatINR } from '../../lib/format';
import { productPath } from '../../lib/routes';
import { ProductRow } from '../../components/ProductRow';
import { EmptyState, Loading, Notice } from '../../components/states';
import { useLibrary } from '../../state/library';

export default function SavedPage() {
  usePageTitle('Saved and alerts');
  const { saved, alerts, toggleSaved, removeAlert } = useLibrary();
  const ids = Array.from(new Set([...saved, ...alerts.map((a) => a.variantId)]));
  const { data, isLoading } = useQuery({
    queryKey: ['summaries', ids.join(',')],
    queryFn: () => api.getSummaries(ids),
    enabled: ids.length > 0,
  });
  const byId = new Map((data ?? []).map((s) => [s.variant.id, s]));
  const savedItems = saved.map((id) => byId.get(id)).filter((s): s is NonNullable<typeof s> => s !== undefined);

  return (
    <div className="page stack stack--lg">
      <h1>Saved and alerts</h1>
      <Notice tone="info">
        Your list is stored in this browser only. Price alerts are saved, but nothing checks prices yet because the price service is
        not built.
      </Notice>

      {isLoading ? <Loading /> : null}

      <section className="stack" aria-labelledby="saved-h">
        <h2 id="saved-h">Saved products</h2>
        {saved.length === 0 ? (
          <EmptyState
            title="Nothing saved yet"
            message="Save a product from its page to keep an eye on it."
            action={<Link to="/app" className="btn btn-secondary btn-sm">Explore products</Link>}
          />
        ) : (
          <ul className="prow-list">
            {savedItems.map((item) => (
              <ProductRow
                key={item.variant.id}
                item={item}
                actions={
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => toggleSaved(item.variant.id)}>
                    Remove
                  </button>
                }
              />
            ))}
          </ul>
        )}
      </section>

      <section className="stack" aria-labelledby="alerts-h">
        <h2 id="alerts-h">Price alerts</h2>
        {alerts.length === 0 ? (
          <p className="muted">No alerts yet. Set one from a product page.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Product</th>
                  <th scope="col">Alert below</th>
                  <th scope="col">Current price</th>
                  <th scope="col">Created</th>
                  <th scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => {
                  const s = byId.get(a.variantId);
                  return (
                    <tr key={a.id}>
                      <td>{s ? <Link to={productPath(s)}>{s.product.name}, {s.variant.label}</Link> : a.variantId}</td>
                      <td className="num">{formatINR(a.target)}</td>
                      <td className="num">{formatINR(s?.price ?? null)}</td>
                      <td className="small muted">{formatDate(a.createdAt)}</td>
                      <td>
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => removeAlert(a.id)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
