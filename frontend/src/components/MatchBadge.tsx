import type { MatchState } from '../types/api';

const LABEL: Record<MatchState, string> = {
  confirmed: 'Identified',
  probable: 'Probable match',
  ambiguous: 'Needs your choice',
  unmatched: 'Not in catalogue',
};

export function MatchBadge({ state }: { state: MatchState }) {
  const cls = state === 'confirmed' ? 'badge-high' : state === 'unmatched' ? 'badge-insufficient' : 'badge-limited';
  return <span className={`badge ${cls}`}>{LABEL[state]}</span>;
}
