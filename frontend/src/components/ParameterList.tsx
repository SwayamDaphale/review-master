import type { ParameterResult } from '../types/api';
import { displayScore, formatDate } from '../lib/format';
import { NotScored, TierBadge, bestTier } from './trust';

const VERIFICATION_LABEL: Record<string, string> = {
  verified: 'Verified',
  unverified: 'Not independently verified',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
};

export function ParameterList({
  parameters,
  highlightKey,
}: {
  parameters: ParameterResult[];
  highlightKey?: string | null;
}) {
  return (
    <div className="params">
      {parameters.map((p) => {
        const tier = bestTier(p.evidence);
        const text = displayScore(p.score);
        return (
          <details key={p.key} className={highlightKey === p.key ? 'param is-active' : 'param'}>
            <summary>
              <span className="param__name">
                {p.name}
                {p.is_critical ? <span className="badge badge-neutral">Critical</span> : null}
              </span>
              <span className="param__score">
                {text && p.score !== null ? (
                  <>
                    <span className="bar" aria-hidden="true">
                      <span className="bar__fill" style={{ width: `${p.score}%` }} />
                    </span>
                    <span className="num param__num">{text}</span>
                  </>
                ) : (
                  <NotScored />
                )}
              </span>
              <span className="param__tier">{tier ? <TierBadge tier={tier} /> : <span className="small muted">No evidence</span>}</span>
            </summary>
            <div className="param__body">
              {p.evidence.length === 0 ? (
                <p className="small muted">{p.note ?? 'No evidence is linked to this parameter yet.'}</p>
              ) : (
                <ul className="evidence-list">
                  {p.evidence.map((e) => (
                    <li key={e.evidence_id}>
                      <span>{e.label}</span>
                      <TierBadge tier={e.trust_tier} />
                      <span className="small muted">
                        {VERIFICATION_LABEL[e.verification_state] ?? e.verification_state}, observed {formatDate(e.observed_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {p.note && p.evidence.length > 0 ? <p className="small muted">{p.note}</p> : null}
            </div>
          </details>
        );
      })}
    </div>
  );
}
