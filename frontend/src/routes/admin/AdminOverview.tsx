import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { useStoredState, STORAGE_KEYS } from '../../lib/storage';
import { useAudit } from '../../lib/audit';
import { formatRelative } from '../../lib/format';
import { usePageTitle } from '../../lib/hooks';
import { Notice } from '../../components/states';
import {
  INTEGRATIONS,
  MAPPINGS_SEED,
  MODELS_SEED,
  MODERATION_SEED,
  type EvalModel,
  type MappingItem,
  type ModerationItem,
} from './adminData';

export default function AdminOverview() {
  usePageTitle('Admin overview');
  const { data } = useQuery({ queryKey: ['list', 'all'], queryFn: () => api.listProducts() });
  const [models] = useStoredState<EvalModel[]>(STORAGE_KEYS.adminModels, MODELS_SEED);
  const [mappings] = useStoredState<MappingItem[]>(STORAGE_KEYS.adminMappings, MAPPINGS_SEED);
  const [moderation] = useStoredState<ModerationItem[]>(STORAGE_KEYS.adminModeration, MODERATION_SEED);
  const { entries } = useAudit();

  const tiles: [string, string, string][] = [
    ['Products in the catalogue', String(data?.length ?? 0), '/admin/catalog'],
    ['Models published', `${models.filter((m) => m.status === 'published').length} of ${models.length}`, '/admin/models'],
    ['Matches waiting for review', String(mappings.filter((m) => m.status === 'pending').length), '/admin/catalog'],
    ['Reviews waiting for moderation', String(moderation.filter((m) => m.state === 'pending' || m.state === 'flagged').length), '/admin/moderation'],
  ];

  return (
    <div className="stack stack--lg">
      <h1>Overview</h1>
      <Notice tone="info">The numbers below come from sample data. They become live once the backend and database exist.</Notice>
      <ul className="tiles">
        {tiles.map(([label, value, to]) => (
          <li key={label}>
            <Link to={to}>
              <span className="tile__value num">{value}</span>
              <span className="muted">{label}</span>
            </Link>
          </li>
        ))}
      </ul>

      <section className="stack" aria-labelledby="int-h">
        <h2 id="int-h">System status</h2>
        <ul className="status-list">
          {INTEGRATIONS.map((i) => (
            <li key={i.name}>
              <span className={`dot dot-${i.status === 'healthy' ? 'high' : i.status === 'degraded' ? 'limited' : 'insufficient'}`} aria-hidden="true" />
              <div>
                <strong>{i.name}</strong>
                <div className="small muted">
                  {i.status === 'healthy' ? 'Working' : i.status === 'degraded' ? 'Degraded' : 'Not connected'}. {i.detail}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="stack" aria-labelledby="recent-h">
        <div className="row row--between">
          <h2 id="recent-h">Recent admin actions</h2>
          <Link to="/admin/audit" className="small">View all</Link>
        </div>
        {entries.length === 0 ? (
          <p className="muted">Nothing yet. Actions you take in the admin area appear here.</p>
        ) : (
          <ul className="status-list">
            {entries.slice(0, 5).map((e) => (
              <li key={e.id}>
                <div>
                  <strong>{e.action}</strong> <span className="muted">{e.object}</span>
                  <div className="small muted">{formatRelative(e.at)}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
