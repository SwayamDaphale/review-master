import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { ProductSummary } from '../types/api';
import { formatINR } from '../lib/format';
import { productPath } from '../lib/routes';
import { ConfidenceBadge, EvidenceMeter, ScoreInline } from './trust';

export function ProductRow({ item, actions }: { item: ProductSummary; actions?: ReactNode }) {
  const { evaluation: ev } = item;
  return (
    <li className="prow">
      <div className="prow__main">
        <Link to={productPath(item)} className="prow__title">
          {item.product.name}
        </Link>
        <span className="small muted">{item.variant.label}</span>
      </div>
      <div className="prow__meter">
        <EvidenceMeter parameters={ev.parameters} compact />
      </div>
      <div className="prow__score">
        <ScoreInline score={ev.overall_score} />
        <ConfidenceBadge state={ev.confidence.state} score={ev.confidence.score} />
      </div>
      <div className="prow__price num">{formatINR(item.price)}</div>
      {actions ? <div className="prow__actions">{actions}</div> : null}
    </li>
  );
}
