import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { CATEGORY_SINGULAR } from '../../types/api';
import { formatINR } from '../../lib/format';
import { STORAGE_KEYS, useStoredState } from '../../lib/storage';
import { useAudit } from '../../lib/audit';
import { usePageTitle } from '../../lib/hooks';
import { ConfidenceBadge, ScoreInline } from '../../components/trust';
import { MatchBadge } from '../../components/MatchBadge';
import { Loading } from '../../components/states';
import { MAPPINGS_SEED, type MappingItem } from './adminData';

export default function AdminCatalog() {
  usePageTitle('Catalogue');
  const { data, isLoading } = useQuery({ queryKey: ['list', 'all'], queryFn: () => api.listProducts() });
  const [mappings, setMappings] = useStoredState<MappingItem[]>(STORAGE_KEYS.adminMappings, MAPPINGS_SEED);
  const { log } = useAudit();

  const decide = (item: MappingItem, status: 'confirmed' | 'rejected') => {
    setMappings((prev) => prev.map((m) => (m.id === item.id ? { ...m, status } : m)));
    log(status === 'confirmed' ? 'Confirmed product match' : 'Rejected product match', item.listing, item.suggestion);
  };

  return (
    <div className="stack stack--lg">
      <h1>Catalogue</h1>

      <section className="stack" aria-labelledby="q-h">
        <h2 id="q-h">Matches waiting for review</h2>
        <p className="muted">
          The extension and the matcher mark some listings as probable or ambiguous. A person confirms them here. A language model
          can suggest, but it can never confirm a match.
        </p>
        <ul className="queue">
          {mappings.map((m) => (
            <li key={m.id}>
              <div className="stack stack--tight">
                <div className="row">
                  <MatchBadge state={m.state} />
                  <span className="small muted">{m.listing}</span>
                </div>
                <div>{m.title}</div>
                <div className="small muted">Suggested: {m.suggestion}. {m.reason}</div>
              </div>
              <div className="row">
                {m.status === 'pending' ? (
                  <>
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => decide(m, 'confirmed')}>
                      Confirm match
                    </button>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => decide(m, 'rejected')}>
                      Reject
                    </button>
                  </>
                ) : (
                  <span className={`badge ${m.status === 'confirmed' ? 'badge-high' : 'badge-insufficient'}`}>
                    {m.status === 'confirmed' ? 'Confirmed' : 'Rejected'}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="stack" aria-labelledby="all-h">
        <h2 id="all-h">All variants</h2>
        {isLoading || !data ? (
          <Loading />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Product</th>
                  <th scope="col">Category</th>
                  <th scope="col">Identity</th>
                  <th scope="col">Score</th>
                  <th scope="col">Confidence</th>
                  <th scope="col">Price</th>
                </tr>
              </thead>
              <tbody>
                {data.map((i) => (
                  <tr key={i.variant.id}>
                    <th scope="row">
                      {i.product.name}
                      <div className="small muted">{i.variant.label}</div>
                    </th>
                    <td>{CATEGORY_SINGULAR[i.product.category]}</td>
                    <td><MatchBadge state={i.match_state} /></td>
                    <td><ScoreInline score={i.evaluation.overall_score} /></td>
                    <td><ConfidenceBadge state={i.evaluation.confidence.state} score={i.evaluation.confidence.score} /></td>
                    <td className="num">{formatINR(i.price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
