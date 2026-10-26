import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ShieldCheck,
  BarChart2,
  ExternalLink,
  ChevronLeft,
  Calendar,
  AlertTriangle,
  TrendingDown,
  Sparkles,
  Bookmark,
  Scale
} from 'lucide-react';
import { api } from '../api';
import { CATEGORY_SINGULAR } from '../types/api';
import { ScoreDial, ConfidenceBadge } from '../components/trust';
import { MatchBadge } from '../components/MatchBadge';
import { Loading, Notice } from '../components/states';
import { formatINR, formatDate } from '../lib/format';
import { usePageTitle } from '../lib/hooks';
import { STORAGE_KEYS, useStoredState } from '../lib/storage';

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: item, isLoading } = useQuery({
    queryKey: ['product', id],
    queryFn: () => (id ? api.getProduct(id) : null),
    enabled: Boolean(id)
  });

  usePageTitle(item ? `${item.product.name} — Review Master` : 'Product Detail');

  const [savedProducts, setSavedProducts] = useStoredState<string[]>(STORAGE_KEYS.savedProducts, []);
  const [compareList, setCompareList] = useStoredState<string[]>(STORAGE_KEYS.compareList, []);

  const isSaved = id ? savedProducts.includes(id) : false;
  const isComparing = id ? compareList.includes(id) : false;

  const toggleSave = () => {
    if (!id) return;
    setSavedProducts((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
  };

  const toggleCompare = () => {
    if (!id) return;
    setCompareList((prev) => {
      if (prev.includes(id)) return prev.filter((p) => p !== id);
      if (prev.length >= 4) return prev;
      return [...prev, id];
    });
  };

  if (isLoading) return <Loading />;
  if (!item) {
    return (
      <div className="stack stack--lg">
        <Link to="/catalog" className="btn btn-secondary btn-sm fit-content">
          <ChevronLeft size={16} />
          <span>Back to Catalogue</span>
        </Link>
        <Notice tone="error">Product not found. The requested ID could not be located in the catalog.</Notice>
      </div>
    );
  }

  const { product, variant, evaluation, community, evidence } = item;

  return (
    <div className="stack stack--lg">
      {/* Breadcrumb / Top Bar */}
      <div className="row row--between">
        <Link to="/catalog" className="breadcrumb-back">
          <ChevronLeft size={16} />
          <span>Catalogue / {CATEGORY_SINGULAR[product.category]}</span>
        </Link>
        <div className="row">
          <button
            type="button"
            className={`btn btn-sm ${isComparing ? 'btn-secondary' : 'btn-ghost'}`}
            onClick={toggleCompare}
          >
            <Scale size={16} />
            <span>{isComparing ? 'In Comparison' : 'Compare'}</span>
          </button>
          <button
            type="button"
            className={`btn btn-sm ${isSaved ? 'btn-secondary' : 'btn-ghost'}`}
            onClick={toggleSave}
          >
            <Bookmark size={16} />
            <span>{isSaved ? 'Saved' : 'Save for Price Alert'}</span>
          </button>
        </div>
      </div>

      {/* Hero Overview */}
      <div className="pdp-hero">
        <div className="pdp-header">
          <div className="row">
            <MatchBadge state={item.match_state} />
            <span className="badge badge-neutral">{CATEGORY_SINGULAR[product.category]}</span>
            {variant.asin && <span className="small muted">Amazon ASIN: {variant.asin}</span>}
          </div>
          <h1 className="pdp-title">{product.name}</h1>
          <div className="pdp-subtitle">
            {product.brand} · {variant.label}
          </div>
          <div className="pdp-price-wrap">
            <span className="pdp-price">{formatINR(item.price)}</span>
            <span className="pdp-timing-badge">
              {community.buy_timing_recommendation === 'buy_now'
                ? '🟢 Buy Now — Near 6-month low'
                : community.buy_timing_recommendation === 'wait_for_sale'
                ? '🟡 Wait for Sale — High price premium'
                : '🔵 Fair Price'}
            </span>
          </div>
        </div>

        {/* 3 Pillars Summary Dial Cluster */}
        <div className="pdp-dial-cluster">
          <div className="dial-card">
            <span className="dial-card__pillar">PILLAR 1: DETERMINISTIC SCORE</span>
            <ScoreDial score={evaluation.overall_score} size="lg" />
            <span className="small muted">Model {evaluation.model_version}</span>
          </div>

          <div className="dial-card">
            <span className="dial-card__pillar">PILLAR 2: CONFIDENCE</span>
            <div className="mt-2 mb-2">
              <ConfidenceBadge state={evaluation.confidence.state} score={evaluation.confidence.score} />
            </div>
            <span className="small muted">{evaluation.confidence.coverage_percent}% Evidence Coverage</span>
          </div>

          <div className="dial-card">
            <span className="dial-card__pillar">PILLAR 3: AUTHENTIC REVIEWS</span>
            <div className="score-dial score-dial--lg mt-1 mb-1">
              <span className="dial-number text-emerald">{community.authentic_percentage}%</span>
            </div>
            <span className="small muted">{community.total_reviews_analyzed.toLocaleString()} Audited Reviews</span>
          </div>
        </div>
      </div>

      {/* AI Grounded Summary */}
      <section className="panel grounded-summary-panel">
        <div className="row row--between mb-2">
          <div className="row">
            <Sparkles size={18} className="text-cyan" />
            <h3>AI Grounded Summary</h3>
          </div>
          <span className="badge badge-high">VERIFIED FROM LAB BENCHMARKS</span>
        </div>
        <p className="grounded-text">{evaluation.grounded_explanation}</p>
        <div className="small muted mt-2">
          * Note: AI strictly synthesizes verified laboratory benchmarks and validated specifications. It is
          architecturally prohibited from modifying or computing the mathematical score.
        </div>
      </section>

      {/* Pillar 1 Detail: Parameter Breakdown */}
      <section className="panel stack" aria-labelledby="param-heading">
        <div className="row row--between">
          <div>
            <h2 id="param-heading">Pillar 1: Deterministic Parameter Breakdown</h2>
            <p className="muted">
              Weights are locked by domain experts and published transparently. Every sub-score is
              calculated on verified lab values.
            </p>
          </div>
          <span className="badge badge-neutral">Model Version {evaluation.model_version}</span>
        </div>

        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Parameter</th>
                <th scope="col">Weight</th>
                <th scope="col">Lab / Measured Value</th>
                <th scope="col">Sub-Score</th>
                <th scope="col">Lab Evidence</th>
              </tr>
            </thead>
            <tbody>
              {evaluation.parameters.map((p) => (
                <tr key={p.key}>
                  <th scope="row">
                    <div>{p.name}</div>
                    <div className="small muted font-mono">{p.key}</div>
                  </th>
                  <td className="num">{(p.weight * 100).toFixed(0)}%</td>
                  <td>
                    {p.raw_value !== undefined ? (
                      <strong>
                        {p.raw_value} {p.unit || ''}
                      </strong>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td>
                    {p.score !== null ? (
                      <div className="row">
                        <span className="score-badge score-badge--inline">{p.score}/100</span>
                      </div>
                    ) : (
                      <span className="badge badge-insufficient">Not Scored</span>
                    )}
                  </td>
                  <td>
                    <span className="small muted">
                      {p.tier1_evidence_count > 0 ? (
                        <span className="text-emerald">✓ {p.tier1_evidence_count} Tier 1 citation(s)</span>
                      ) : (
                        'Standard spec'
                      )}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Pillar 2 Detail: Evidence Citations */}
      <section className="panel stack" aria-labelledby="evidence-heading">
        <div className="row row--between">
          <div>
            <h2 id="evidence-heading">Pillar 2: Verified Evidence Citations ({evidence.length})</h2>
            <p className="muted">
              Direct citations from accredited testing facilities, hardware benchmarks, and manufacturer
              whitepapers.
            </p>
          </div>
          <span className="badge badge-high">{evaluation.confidence.evidence_count} Citations Verified</span>
        </div>

        <div className="evidence-grid">
          {evidence.map((ev) => (
            <div key={ev.id} className="evidence-card">
              <div className="evidence-card__header">
                <span className={`badge ${ev.tier === 'tier1' ? 'badge-high' : 'badge-neutral'}`}>
                  {ev.tier.toUpperCase()} · {ev.reliability.replace('_', ' ').toUpperCase()}
                </span>
                <span className="small muted">
                  <Calendar size={12} className="inline-icon" /> {formatDate(ev.measured_at)}
                </span>
              </div>
              <h4 className="evidence-card__param">{ev.parameter}</h4>
              <div className="evidence-card__val">
                Measured: <strong>{ev.value} {ev.unit || ''}</strong>
              </div>
              <p className="evidence-card__citation">{ev.citation}</p>
              <div className="evidence-card__source">
                <span>Source: {ev.source_name}</span>
                {ev.source_url && (
                  <a href={ev.source_url} target="_blank" rel="noreferrer" className="row">
                    <ExternalLink size={12} />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Pillar 3 Detail: Community & Market Signals */}
      <section className="panel stack" aria-labelledby="community-heading">
        <h2 id="community-heading">Pillar 3: Community & Market Audit</h2>
        <p className="muted">
          Our review-audit pipeline analyzes linguistic markers, timing spikes, and verified purchases to detect
          sponsored and astroturfed customer feedback.
        </p>

        <div className="community-grid">
          <div className="community-stat-box">
            <span className="small muted">Authenticity Ratio</span>
            <div className="stat-number text-emerald">{community.authentic_percentage}%</div>
            <div className="small muted">
              {community.suspicious_percentage}% filtered as likely astroturfed
            </div>
            <div className="progress-bar mt-2">
              <div className="progress-fill progress-fill--high" style={{ width: `${community.authentic_percentage}%` }} />
            </div>
          </div>

          <div className="community-stat-box">
            <span className="small muted">Price Range (6 Months)</span>
            <div className="row row--between mt-1 mb-1">
              <div>
                <span className="small muted">Lowest</span>
                <div className="stat-sm">{formatINR(community.lowest_observed_price)}</div>
              </div>
              <TrendingDown size={20} className="text-cyan" />
              <div>
                <span className="small muted">Highest</span>
                <div className="stat-sm">{formatINR(community.highest_observed_price)}</div>
              </div>
            </div>
            <span className="small muted">Current: {formatINR(community.current_price)}</span>
          </div>

          <div className="community-themes-box">
            <span className="small muted font-bold">Top Verified Strengths</span>
            <ul className="themes-list">
              {community.top_positive_themes.map((theme, i) => (
                <li key={i} className="theme-item text-emerald">
                  ✓ {theme}
                </li>
              ))}
            </ul>
          </div>

          <div className="community-themes-box">
            <span className="small muted font-bold">Top Verified Criticisms</span>
            <ul className="themes-list">
              {community.top_criticisms.map((crit, i) => (
                <li key={i} className="theme-item text-rose">
                  <AlertTriangle size={14} className="inline-icon" /> {crit}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Price History Table */}
        <div className="mt-2">
          <h4>Price Observation History</h4>
          <div className="table-wrap mt-1">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Date Observed</th>
                  <th scope="col">Marketplace</th>
                  <th scope="col">Recorded Price</th>
                </tr>
              </thead>
              <tbody>
                {community.price_history.map((ph, idx) => (
                  <tr key={idx}>
                    <td>{formatDate(ph.date)}</td>
                    <td>{ph.marketplace}</td>
                    <td className="num">{formatINR(ph.price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
