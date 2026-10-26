import React from 'react';
import type { MatchState } from '../types/api';

interface MatchBadgeProps {
  state: MatchState;
}

export function MatchBadge({ state }: MatchBadgeProps) {
  const map: Record<MatchState, { label: string; className: string }> = {
    confirmed: { label: 'Confirmed Match', className: 'badge-high' },
    probable: { label: 'Probable Match', className: 'badge-moderate' },
    ambiguous: { label: 'Ambiguous', className: 'badge-limited' },
    unconfirmed: { label: 'Unconfirmed', className: 'badge-insufficient' }
  };

  const item = map[state] || { label: state, className: 'badge-neutral' };

  return (
    <span className={`badge ${item.className}`}>
      <span className="badge-dot" />
      {item.label}
    </span>
  );
}
