import { STORAGE_KEYS, useStoredState } from '../../lib/storage';
import { useAudit } from '../../lib/audit';
import { usePageTitle } from '../../lib/hooks';
import { Notice } from '../../components/states';
import { MODELS_SEED, modelBlockers, type EvalModel } from './adminData';

export default function AdminModels() {
  usePageTitle('Evaluation models');
  const [models, setModels] = useStoredState<EvalModel[]>(STORAGE_KEYS.adminModels, MODELS_SEED);
  const { log } = useAudit();

  const patch = (id: string, fn: (m: EvalModel) => EvalModel) =>
    setModels((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));

  const setWeight = (id: string, key: string, raw: string) =>
    patch(id, (m) => ({
      ...m,
      params: m.params.map((p) => {
        if (p.key !== key) return p;
        if (raw.trim() === '') return { ...p, weight: null };
        const n = Number(raw);
        return { ...p, weight: Number.isFinite(n) ? Math.max(0, Math.min(1, n)) : p.weight };
      }),
    }));

  return (
    <div className="stack stack--lg">
      <h1>Evaluation models</h1>
      <Notice tone="info">
        Each category has a draft model. A model can only be published when every weight is set, the weights add up to 1.00 and both
        approvals are recorded. Published versions cannot be edited. Weights and thresholds come from domain experts, not from
        this screen.
      </Notice>

      {models.map((m) => {
        const blockers = modelBlockers(m);
        const published = m.status === 'published';
        const sum = m.params.reduce((a, p) => a + (p.weight ?? 0), 0);
        return (
          <section key={m.id} className="panel stack" aria-labelledby={`${m.id}-h`}>
            <div className="row row--between">
              <h2 id={`${m.id}-h`}>{m.category}</h2>
              <span className={`badge ${published ? 'badge-high' : 'badge-limited'}`}>
                {published ? 'Published' : 'Draft'} {m.version}
              </span>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Parameter</th>
                    <th scope="col">Weight (0 to 1)</th>
                  </tr>
                </thead>
                <tbody>
                  {m.params.map((p) => (
                    <tr key={p.key}>
                      <th scope="row">{p.name}</th>
                      <td>
                        <label className="sr-only" htmlFor={`${m.id}-${p.key}`}>Weight for {p.name}</label>
                        <input
                          id={`${m.id}-${p.key}`}
                          className="input input--num"
                          type="number"
                          min={0}
                          max={1}
                          step={0.01}
                          disabled={published}
                          value={p.weight === null ? '' : p.weight}
                          placeholder="Not set"
                          onChange={(e) => setWeight(m.id, p.key, e.target.value)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row">Total</th>
                    <td className="num">{sum.toFixed(2)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <div className="row">
              <label className="check">
                <input
                  type="checkbox"
                  checked={m.domainApproved}
                  disabled={published}
                  onChange={(e) => patch(m.id, (x) => ({ ...x, domainApproved: e.target.checked }))}
                />
                Domain expert approved
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={m.engineeringApproved}
                  disabled={published}
                  onChange={(e) => patch(m.id, (x) => ({ ...x, engineeringApproved: e.target.checked }))}
                />
                Engineering approved
              </label>
            </div>
            {published ? (
              <p className="small muted">Published and locked. A change needs a new version.</p>
            ) : (
              <>
                {blockers.length > 0 ? (
                  <ul className="blockers">
                    {blockers.map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                ) : null}
                <div>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={blockers.length > 0}
                    onClick={() => {
                      patch(m.id, (x) => ({ ...x, status: 'published' }));
                      log('Published evaluation model', m.category, `version ${m.version} (local preview)`);
                    }}
                  >
                    Publish this version
                  </button>
                </div>
              </>
            )}
          </section>
        );
      })}
    </div>
  );
}
