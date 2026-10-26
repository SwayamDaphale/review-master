import { STORAGE_KEYS, useStoredState } from '../../lib/storage';
import { useAudit } from '../../lib/audit';
import { usePageTitle } from '../../lib/hooks';
import { MODERATION_SEED, type ModerationItem } from './adminData';

const BADGE: Record<ModerationItem['state'], string> = {
  pending: 'badge-neutral',
  approved: 'badge-high',
  rejected: 'badge-insufficient',
  flagged: 'badge-limited',
};

export default function AdminModeration() {
  usePageTitle('Moderation');
  const [items, setItems] = useStoredState<ModerationItem[]>(STORAGE_KEYS.adminModeration, MODERATION_SEED);
  const { log } = useAudit();

  const decide = (item: ModerationItem, state: ModerationItem['state']) => {
    setItems((prev) => prev.map((x) => (x.id === item.id ? { ...x, state } : x)));
    log(`Moderation: ${state}`, item.target, `${item.author}`);
  };

  return (
    <div className="stack stack--lg">
      <h1>Moderation</h1>
      <p className="muted">
        Community reviews wait here before they are shown. Rejected reviews are kept for the record, not deleted. Pattern flags are
        hints for a person to check, not verdicts.
      </p>
      <ul className="queue">
        {items.map((m) => (
          <li key={m.id}>
            <div className="stack stack--tight">
              <div className="row">
                <span className={`badge ${BADGE[m.state]}`}>{m.state}</span>
                <span className="small muted">{m.target}, by {m.author}</span>
              </div>
              <p>{m.text}</p>
              {m.flags.map((f) => (
                <p key={f} className="small flag">Pattern flag: {f}</p>
              ))}
            </div>
            <div className="row">
              <button type="button" className="btn btn-primary btn-sm" onClick={() => decide(m, 'approved')} disabled={m.state === 'approved'}>
                Approve
              </button>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => decide(m, 'flagged')} disabled={m.state === 'flagged'}>
                Flag
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => decide(m, 'rejected')} disabled={m.state === 'rejected'}>
                Reject
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
