import React from 'react';

interface ScoreInlineProps {
  score: number | null;
  size?: 'sm' | 'md' | 'lg';
}

export function ScoreInline({ score, size = 'md' }: ScoreInlineProps) {
  if (score === null || score === undefined) {
    return <span className={`score-inline score-inline--null score-inline--${size}`}>Not Scored</span>;
  }

  let colorClass = 'score-mid';
  if (score >= 8.0) colorClass = 'score-high';
  else if (score < 6.0) colorClass = 'score-low';

  return (
    <span className={`score-inline ${colorClass} score-inline--${size}`}>
      <span className="score-val">{score.toFixed(1)}</span>
      <span className="score-scale">/10</span>
    </span>
  );
}
