import React from 'react';
import type { ConfidenceState } from '../../types/api';

interface ConfidenceBadgeProps {
  state: ConfidenceState;
  score?: number;
  showPercent?: boolean;
}

export function ConfidenceBadge({ state, score, showPercent = true }: ConfidenceBadgeProps) {
  const percent = score !== undefined ? Math.round(score * 100) : null;

  const labelMap: Record<ConfidenceState, string> = {
    high: 'High Confidence',
    moderate: 'Moderate Confidence',
    limited: 'Limited Confidence',
    insufficient: 'Insufficient Evidence'
  };

  const badgeClassMap: Record<ConfidenceState, string> = {
    high: 'badge-high',
    moderate: 'badge-moderate',
    limited: 'badge-limited',
    insufficient: 'badge-insufficient'
  };

  return (
    <span className={`badge ${badgeClassMap[state]}`}>
      <span className="badge-dot" />
      {labelMap[state]}
      {showPercent && percent !== null ? ` · ${percent}%` : ''}
    </span>
  );
}
