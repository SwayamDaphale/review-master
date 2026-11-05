import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { ApiError, CATEGORY_SINGULAR, type ComparisonResult } from '../../types/api';
import { usePageTitle } from '../../lib/hooks';
import { formatINR } from '../../lib/format';
import { productPath } from '../../lib/routes';
import { ConfidenceBadge, NotScored, ScoreInline } from '../../components/trust';
import { EmptyState, ErrorState, Loading, Notice } from '../../components/states';
import { useSiteSettings } from '../../state/siteSettings';

/** Marks the cells with the highest displayed value in a row. Never marks "not scored". */
function bestIndexes(values: (number | null)[]): Set<number> {
  const scored = values.filter((v): v is number => v !== null);
  if (scored.length < 2) return new Set();
  const max = Math.max(...scored);
  if (scored.every((v) => v === max)) return new Set();
  const out = new Set<number>();
  values.forEach((v, i) => {
    if (v === max) out.add(i);
  });
  return out;
}

function Matrix({ data }: { data: ComparisonResult }) {
  const first = data.items[0];
  const paramRows = first ? first.evaluation.parameters.map((p) => ({ key: p.key, name: p.name })) : [];
  const specKeys = useMemo(() => {
    const seen = new Map<string, string>();
    data.views.forEach((v) => v.specs.forEach((s) => (seen.has(s.key) ? null : seen.set(s.key, s.label))));
    return [...seen.entries()];
  }, [data.views]);
  const overall = bestIndexes(data.items.map((i) => i.evaluation.overall_score));

  return (
    <div className="table-wrap">
      <table className="table compare-table">
        <caption className="sr-only">Side-by-side comparison of {CATEGORY_SINGULAR[data.category]} products</caption>
        <thead>
          <tr>
            <th scope="col"><span className="sr-only">Measure</span></th>
            {data.items.map((i) => (
              <th scope="col" key={i.variant.id}>
                <Link to={productPath(i)}>{i.product.name}</Link>
                <div className="small muted">{i.variant.label}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Review Master score</th>
            {data.items.map((i, idx) => (
              <td key={i.variant.id} className={overall.has(idx) ? 'is-best' : undefined}>
                <ScoreInline score={i.evaluation.overall_score} />
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">Confidence</th>
            {data.items.map((i) => (
              <td key={i.variant.id}>
                <ConfidenceBadge state={i.evaluation.confidence.state} score={i.evaluation.confidence.score} />
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">Price</th>
            {data.items.map((i) => (
              <td key={i.variant.id} className="num">{formatINR(i.price)}</td>
            ))}
          </tr>
          <tr className="group-row">
            <th scope="colgroup" colSpan={data.items.length + 1}>Parameter scores</th>
          </tr>
          {paramRows.map((row) => {
            const scores = data.items.map((i) => i.evaluation.parameters.find((p) => p.key === row.key)?.score ?? null);
            const best = bestIndexes(scores);
            return (
              <tr key={row.key}>
                <th scope="row">{row.name}</th>
                {scores.map((s, idx) => (
                  <td key={data.items[idx]?.variant.id} className={best.has(idx) ? 'is-best' : undefined}>
                    <ScoreInline score={s} />
                  </td>
                ))}
              </tr>
            );
          })}
          <tr className="group-row">
            <th scope="colgroup" colSpan={data.items.length + 1}>Specifications</th>
          </tr>
          {specKeys.map(([key, label]) => (
            <tr key={key}>
              <th scope="row">{label}</th>
              {data.views.map((v) => {
                const s = v.specs.find((x) => x.key === key);
                return (
                  <td key={v.variant.id}>
                    {s?.value ? s.value : <span className="muted">Not captured</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ComparePage() {
  usePageTitle('Compare');
  const [settings] = useSiteSettings();
  const [params, setParams] = useSearchParams();
  const ids = (params.get('ids') ?? '').split(',').filter(Boolean).slice(0, 3);

  const listQ = useQuery({ queryKey: ['list', 'all'], queryFn: () => api.listProducts() });
  const cmpQ = useQuery({
    queryKey: ['compare', ids.join(',')],
    queryFn: () => api.compare(ids),
    enabled: ids.length >= 2,
    retry: false,
  });

  if (!settings.features.compare) {
    return <Notice tone="info">Comparison is switched off at the moment.</Notice>;
  }

  const setIds = (next: string[]) => setParams(next.length ? { ids: next.join(',') } : {}, { replace: true });
  const options = (listQ.data ?? []).filter((i) => !ids.includes(i.variant.id));
  const chosen = ids.map((id) => listQ.data?.find((i) => i.variant.id === id));

  return (
    <div className="page stack stack--lg">
      <div className="stack">
        <h1>Compare products</h1>
        <p className="lead">Choose two or three products from the same category. Scores are shown with their confidence, side by side.</p>
      </div>

      <div className="stack">
        <ul className="chips">
          {ids.map((id, idx) => {
            const item = chosen[idx];
            return (
              <li key={id} className="chip chip--removable">
                <span>{item ? `${item.product.name}, ${item.variant.label}` : id}</span>
                <button type="button" aria-label={`Remove ${item ? item.product.name : id}`} onClick={() => setIds(ids.filter((x) => x !== id))}>
                  ×
                </button>
              </li>
            );
          })}
        </ul>
        {ids.length < 3 ? (
          <div className="row">
            <label className="sr-only" htmlFor="add-product">Add a product to compare</label>
            <select
              id="add-product"
              className="select"
              value=""
              onChange={(e) => e.target.value && setIds([...ids, e.target.value])}
            >
              <option value="">Add a product…</option>
              {options.map((o) => (
                <option key={o.variant.id} value={o.variant.id}>
                  {o.product.name}, {o.variant.label}
                </option>
              ))}
            </select>
          </div>
        ) : null}
      </div>

      {ids.length < 2 ? (
        <EmptyState title="Pick at least two products" message="Add a second product to see the comparison." />
      ) : cmpQ.isLoading ? (
        <Loading label="Building the comparison" />
      ) : cmpQ.error ? (
        <ErrorState
          title="These cannot be compared"
          message={cmpQ.error instanceof ApiError ? cmpQ.error.message : 'The comparison could not be built.'}
          action={
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setIds(ids.slice(0, 1))}>
              Start again with the first product
            </button>
          }
        />
      ) : cmpQ.data ? (
        <>
          <Matrix data={cmpQ.data} />
          <p className="small muted">
            Shaded cells have the higher score in that row. Read each score together with its confidence: a higher score with limited
            confidence is less certain.
          </p>
          <p className="small muted"><NotScored /> means there was not enough evidence to score it.</p>
        </>
      ) : null}
    </div>
  );
}
