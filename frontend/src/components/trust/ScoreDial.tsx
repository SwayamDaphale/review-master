import React from 'react';

interface ScoreDialProps {
  score: number | null;
  label?: string;
  size?: number | 'sm' | 'md' | 'lg';
}

export function ScoreDial({ score, label = 'Review Master Score', size = 'lg' }: ScoreDialProps) {
  const numericSize =
    typeof size === 'number'
      ? size
      : size === 'sm'
      ? 64
      : size === 'md'
      ? 96
      : 120;
  const strokeWidth = numericSize < 80 ? 6 : 8;
  const radius = (numericSize - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const normalizedScore = score !== null ? Math.max(0, Math.min(10, score)) : 0;
  const progress = score !== null ? (normalizedScore / 10) * circumference : 0;

  let strokeColor = '#00E5FF';
  if (score !== null) {
    if (score >= 8.0) strokeColor = '#10B981'; // emerald
    else if (score >= 6.0) strokeColor = '#00E5FF'; // cyan
    else strokeColor = '#F59E0B'; // amber
  } else {
    strokeColor = '#475569';
  }

  return (
    <div className="score-dial-wrap" style={{ width: numericSize, height: numericSize }}>
      <svg width={numericSize} height={numericSize} className="score-dial-svg">
        <circle
          cx={numericSize / 2}
          cy={numericSize / 2}
          r={radius}
          stroke="#1E293B"
          strokeWidth={strokeWidth}
          fill="transparent"
        />
        <circle
          cx={numericSize / 2}
          cy={numericSize / 2}
          r={radius}
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          transform={`rotate(-90 ${numericSize / 2} ${numericSize / 2})`}
          style={{ transition: 'stroke-dashoffset 1s ease-out' }}
        />
      </svg>
      <div className="score-dial-content">
        <span className="score-dial-number">{score !== null ? score.toFixed(1) : '—'}</span>
        <span className="score-dial-denom">/10</span>
      </div>
    </div>
  );
}
