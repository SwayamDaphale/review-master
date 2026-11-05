import type { PriceHistory } from '../types/api';
import { formatDate, formatINR } from '../lib/format';

/** Draws the points the API returned. Min, median and max come from the API windows, not from here. */
export function PriceChart({ history, days }: { history: PriceHistory; days: 30 | 90 }) {
  const points = history.points.slice(-days);
  const windowStats = history.windows[String(days) as '30' | '90'];
  if (points.length < 2) {
    return <p className="muted">Not enough price history yet to draw a chart.</p>;
  }
  const W = 600;
  const H = 160;
  const pad = 8;
  const prices = points.map((p) => p.price);
  const lo = Math.min(...prices);
  const hi = Math.max(...prices);
  const span = hi - lo || 1;
  const x = (i: number) => pad + (i * (W - pad * 2)) / (points.length - 1);
  const y = (v: number) => H - pad - ((v - lo) * (H - pad * 2)) / span;
  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(p.price).toFixed(1)}`).join(' ');
  const area = `${line} L${x(points.length - 1).toFixed(1)} ${H - pad} L${x(0).toFixed(1)} ${H - pad} Z`;
  const first = points[0];
  const last = points[points.length - 1];
  return (
    <figure className="price-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Price over the last ${points.length} days, from ${formatINR(first?.price)} to ${formatINR(last?.price)}`} preserveAspectRatio="none">
        <path d={area} className="price-chart__area" />
        <path d={line} className="price-chart__line" />
      </svg>
      <figcaption className="small muted price-chart__axis">
        <span>{first ? formatDate(first.observed_at) : ''}</span>
        <span>{last ? formatDate(last.observed_at) : ''}</span>
      </figcaption>
      {windowStats ? (
        <dl className="stat-row">
          <div>
            <dt>Lowest</dt>
            <dd className="num">{formatINR(windowStats.min)}</dd>
          </div>
          <div>
            <dt>Typical</dt>
            <dd className="num">{formatINR(windowStats.median)}</dd>
          </div>
          <div>
            <dt>Highest</dt>
            <dd className="num">{formatINR(windowStats.max)}</dd>
          </div>
        </dl>
      ) : null}
    </figure>
  );
}
