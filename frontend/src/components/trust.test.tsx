import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AiSummary, ConfidenceBadge, EvidenceMeter, NotScored, ScoreRing } from './trust';
import type { ParameterResult } from '../types/api';

const param = (key: string, score: number | null, tier: 1 | 2 | 3 | null): ParameterResult => ({
  key,
  name: key,
  status: score === null ? 'not_scored' : 'scored',
  score,
  weight: 0.25,
  is_critical: false,
  evidence: tier
    ? [{ evidence_id: `e-${key}`, source_type: 'marketplace', trust_tier: tier, label: 'Listing', observed_at: new Date().toISOString(), verification_state: 'verified' }]
    : [],
});

describe('ScoreRing', () => {
  it('shows the score out of 10', () => {
    render(<ScoreRing score={86.3} />);
    expect(screen.getByRole('img', { name: 'Review Master score 8.6 out of 10' })).toBeInTheDocument();
  });

  it('shows "Not scored" and never a zero when the score is missing', () => {
    render(<ScoreRing score={null} />);
    expect(screen.getByRole('img', { name: /not scored/i })).toBeInTheDocument();
    expect(screen.getByText('Not scored')).toBeInTheDocument();
    expect(screen.queryByText(/^0(\.0)?$/)).not.toBeInTheDocument();
  });
});

describe('ConfidenceBadge', () => {
  it('names the level and shows the percentage', () => {
    render(<ConfidenceBadge state="limited" score={0.62} />);
    expect(screen.getByText('Limited confidence')).toBeInTheDocument();
    expect(screen.getByText('62%')).toBeInTheDocument();
  });

  it('uses plain words for insufficient evidence', () => {
    render(<ConfidenceBadge state="insufficient_evidence" score={0.31} />);
    expect(screen.getByText('Insufficient evidence')).toBeInTheDocument();
  });
});

describe('EvidenceMeter', () => {
  it('draws unscored parameters as hatched segments', () => {
    const { container } = render(<EvidenceMeter parameters={[param('a', 80, 1), param('b', null, null), param('c', 60, 3)]} />);
    expect(container.querySelectorAll('.seg-t1')).toHaveLength(1);
    expect(container.querySelectorAll('.seg-t3')).toHaveLength(1);
    expect(container.querySelectorAll('.seg-none')).toHaveLength(1);
  });
});

describe('AiSummary and NotScored', () => {
  it('labels AI text', () => {
    render(<AiSummary explanation={{ text: 'Hello', ai_generated: true, mode: 'ai', referenced_parameters: [] }} />);
    expect(screen.getByText('AI grounded summary')).toBeInTheDocument();
  });

  it('labels template text as not written by AI', () => {
    render(<AiSummary explanation={{ text: 'Hello', ai_generated: false, mode: 'template', referenced_parameters: [] }} />);
    expect(screen.getByText('Template summary')).toBeInTheDocument();
    expect(screen.getByText(/Not written by AI/)).toBeInTheDocument();
  });

  it('renders the not-scored marker', () => {
    render(<NotScored />);
    expect(screen.getByText('Not scored')).toBeInTheDocument();
  });
});
