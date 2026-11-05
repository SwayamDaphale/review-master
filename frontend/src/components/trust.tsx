import type { ConfidenceState, EvidenceRef, Explanation, ParameterResult, TrustTier } from '../types/api';
import { CONFIDENCE_LABEL, displayScore, formatPercent01 } from '../lib/format';

export const TIER_LABEL: Record<TrustTier, string> = {
  1: 'Independent or expert test',
  2: 'Manufacturer or marketplace claim',
  3: 'Community report',
};

export function bestTier(evidence: EvidenceRef[]): TrustTier | null {
  if (evidence.length === 0) return null;
  return evidence.reduce<TrustTier>((best, e) => (e.trust_tier < best ? e.trust_tier : best), 3);
}

export function NotScored({ label = 'Not scored' }: { label?: string }) {
  return (
    <span className="not-scored">
      <span className="hatch" aria-hidden="true" />
      {label}
    </span>
  );
}

export function SampleBadge() {
  return (
    <span className="badge badge-sample" title="This page shows demo data. Scores are placeholders until evaluation models are published.">
      Sample data
    </span>
  );
}

/** Draws a ring from the score the API returned. A null score is drawn as an empty, hatched ring. */
export function ScoreRing({ score, size = 132 }: { score: number | null; size?: number }) {
  const r = 44;
  const circumference = 2 * Math.PI * r;
  const text = displayScore(score);
  const filled = score === null ? 0 : Math.max(0, Math.min(100, score)) / 100;
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg
        viewBox="0 0 100 100"
        role="img"
        aria-label={text ? `Review Master score ${text} out of 10` : 'Review Master score: not scored'}
      >
        <circle className={score === null ? 'score-ring__track score-ring__track--none' : 'score-ring__track'} cx="50" cy="50" r={r} />
        {score !== null ? (
          <circle
            className="score-ring__value"
            cx="50"
            cy="50"
            r={r}
            strokeDasharray={`${circumference * filled} ${circumference}`}
            transform="rotate(-90 50 50)"
          />
        ) : null}
      </svg>
      <div className="score-ring__label" aria-hidden="true">
        {text ? (
          <>
            <span className="score-ring__num num">{text}</span>
            <span className="score-ring__max">out of 10</span>
          </>
        ) : (
          <span className="score-ring__none">Not scored</span>
        )}
      </div>
    </div>
  );
}

export function ScoreInline({ score }: { score: number | null }) {
  const text = displayScore(score);
  return text ? (
    <span className="score-inline num">
      {text}
      <span className="score-inline__max">/10</span>
    </span>
  ) : (
    <NotScored />
  );
}

export function ConfidenceBadge({
  state,
  score,
  showPercent = true,
}: {
  state: ConfidenceState;
  score?: number;
  showPercent?: boolean;
}) {
  const cls = state === 'insufficient_evidence' ? 'insufficient' : state;
  return (
    <span className={`badge badge-${cls}`}>
      <span className={`dot dot-${cls}`} aria-hidden="true" />
      {CONFIDENCE_LABEL[state]}
      {showPercent && score !== undefined ? <span className="num">{formatPercent01(score)}</span> : null}
    </span>
  );
}

export function TierBadge({ tier }: { tier: TrustTier }) {
  return (
    <span className={`tier tier-${tier}`} title={TIER_LABEL[tier]}>
      Tier {tier}
    </span>
  );
}

function segmentClass(p: ParameterResult): string {
  if (p.status === 'not_scored' || p.score === null) return 'seg-none';
  const t = bestTier(p.evidence);
  return t === 1 ? 'seg-t1' : t === 2 ? 'seg-t2' : 'seg-t3';
}

function segmentLabel(p: ParameterResult): string {
  if (p.score === null) return `${p.name}: not scored`;
  const t = bestTier(p.evidence);
  return `${p.name}: scored, best evidence ${t ? `tier ${t}` : 'not linked'}`;
}

/**
 * Shows how a score is built. Segment width follows each parameter's weight, colour follows the best
 * evidence tier behind it, and hatching marks parameters that are not scored (never drawn as zero).
 */
export function EvidenceMeter({
  parameters,
  activeKey,
  onActiveChange,
  compact = false,
}: {
  parameters: ParameterResult[];
  activeKey?: string | null;
  onActiveChange?: (key: string | null) => void;
  compact?: boolean;
}) {
  const interactive = onActiveChange !== undefined;
  return (
    <div className={compact ? 'meter meter--compact' : 'meter'} role="group" aria-label="How the score is built from evidence">
      {parameters.map((p) => {
        const cls = `meter__seg ${segmentClass(p)}${activeKey === p.key ? ' is-active' : ''}`;
        const style = { flexGrow: p.weight ?? 1 };
        return interactive ? (
          <button
            key={p.key}
            type="button"
            className={cls}
            style={style}
            aria-label={segmentLabel(p)}
            onMouseEnter={() => onActiveChange(p.key)}
            onFocus={() => onActiveChange(p.key)}
            onMouseLeave={() => onActiveChange(null)}
            onBlur={() => onActiveChange(null)}
          />
        ) : (
          <span key={p.key} className={cls} style={style} title={segmentLabel(p)} />
        );
      })}
    </div>
  );
}

export function MeterLegend() {
  return (
    <ul className="legend" aria-label="Evidence legend">
      <li>
        <span className="swatch seg-t1" aria-hidden="true" />
        Tier 1: independent or expert test
      </li>
      <li>
        <span className="swatch seg-t2" aria-hidden="true" />
        Tier 2: manufacturer or marketplace claim
      </li>
      <li>
        <span className="swatch seg-t3" aria-hidden="true" />
        Tier 3: community report
      </li>
      <li>
        <span className="swatch seg-none" aria-hidden="true" />
        Not scored
      </li>
    </ul>
  );
}

export function AiSummary({ explanation }: { explanation: Explanation }) {
  const isAi = explanation.mode === 'ai';
  return (
    <section className="ai-summary" aria-label={isAi ? 'AI grounded summary' : 'Template summary'}>
      <div className="ai-summary__head">
        <span className="badge badge-accent">{isAi ? 'AI grounded summary' : 'Template summary'}</span>
        <span className="small muted">
          {isAi
            ? 'Written only from the evidence on this page. It cannot add scores or specifications.'
            : 'Not written by AI. Built from the stored evaluation.'}
        </span>
      </div>
      <p>{explanation.text}</p>
    </section>
  );
}
