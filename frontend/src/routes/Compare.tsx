import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Scale, Trash2, Plus, Check, ArrowRight } from 'lucide-react';
import { api } from '../api';
import type { ProductItem } from '../types/api';
import { CATEGORY_SINGULAR } from '../types/api';
import { ScoreDial, ConfidenceBadge } from '../components/trust';
import { MatchBadge } from '../components/MatchBadge';
import { Loading } from '../components/states';
import { formatINR } from '../lib/format';
import { usePageTitle } from '../lib/hooks';
import { STORAGE_KEYS, useStoredState } from '../lib/storage';

export default function Compare() {
  usePageTitle('Compare Devices — Side by Side Evidence');
  const [compareList, setCompareList] = useStoredState<string[]>(STORAGE_KEYS.compareList, [
    's25-ultra-512',
    'nothing-phone-4a-256'
  ]);

  const { data: allProducts, isLoading } = useQuery({
    queryKey: ['list', 'all'],
    queryFn: () => api.listProducts()
  });

  const [selectedToAdd, setSelectedToAdd] = useState('');

  const comparedItems: ProductItem[] = (allProducts || []).filter((p) =>
    compareList.includes(p.product.id) || compareList.includes(p.variant.id)
  );

  const availableToAdd = (allProducts || []).filter(
    (p) => !compareList.includes(p.product.id) && !compareList.includes(p.variant.id)
  );

  const removeDevice = (id: string) => {
    setCompareList((prev) => prev.filter((p) => p !== id));
  };

  const addDevice = () => {
    if (!selectedToAdd || compareList.length >= 4) return;
    setCompareList((prev) => [...prev, selectedToAdd]);
    setSelectedToAdd('');
  };

  const clearAll = () => {
    setCompareList([]);
  };

  // Collect distinct parameters across compared items
  const allParamKeys = Array.from(
    new Set(
      comparedItems.flatMap((item) => item.evaluation.parameters.map((p) => p.key))
    )
  );

  return (
    <div className="stack stack--lg">
      <div className="row row--between">
        <div>
          <h1>Side-by-Side Comparison</h1>
          <p className="muted">
            Directly compare deterministic scores, benchmark measurements, and evidence coverage across devices.
          </p>
        </div>

        <div className="row">
          {comparedItems.length > 0 && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={clearAll}>
              <Trash2 size={14} />
              <span>Clear All</span>
            </button>
          )}
        </div>
      </div>

      {/* Add Device Bar */}
      {compareList.length < 4 && availableToAdd.length > 0 && (
        <div className="panel row row--between">
          <div className="row">
            <Plus size={16} className="text-cyan" />
            <span className="small muted">Add another device to comparison (up to 4):</span>
            <select
              aria-label="Select device to add"
              className="select-sort"
              value={selectedToAdd}
              onChange={(e) => setSelectedToAdd(e.target.value)}
            >
              <option value="">Choose a product...</option>
              {availableToAdd.map((p) => (
                <option key={p.product.id} value={p.product.id}>
                  {p.product.name} ({p.variant.label}) — {formatINR(p.price)}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={!selectedToAdd}
            onClick={addDevice}
          >
            Add to Compare
          </button>
        </div>
      )}

      {isLoading ? (
        <Loading />
      ) : comparedItems.length === 0 ? (
        <div className="empty-state">
          <Scale size={48} className="muted" />
          <h3>No devices in comparison</h3>
          <p className="muted">Select up to 4 devices from our catalogue to compare their evidence.</p>
          <Link to="/catalog" className="btn btn-primary mt-2">
            <span>Browse Catalogue</span>
            <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        <div className="compare-table-wrap">
          <table className="compare-table">
            <thead>
              <tr>
                <th className="compare-header-cell">Attribute</th>
                {comparedItems.map((item) => (
                  <th key={item.variant.id} className="compare-product-col">
                    <div className="compare-header-card">
                      <div className="row row--between">
                        <MatchBadge state={item.match_state} />
                        <button
                          type="button"
                          className="btn-icon"
                          onClick={() => removeDevice(item.product.id)}
                          title="Remove from comparison"
                          aria-label="Remove device"
                        >
                          ✕
                        </button>
                      </div>

                      <h3 className="compare-title">
                        <Link to={`/product/${item.product.id}`}>{item.product.name}</Link>
                      </h3>
                      <div className="small muted mb-2">
                        {CATEGORY_SINGULAR[item.product.category]} · {item.variant.label}
                      </div>

                      <div className="compare-score-box">
                        <ScoreDial score={item.evaluation.overall_score} size="md" />
                        <div className="mt-1">
                          <ConfidenceBadge
                            state={item.evaluation.confidence.state}
                            score={item.evaluation.confidence.score}
                          />
                        </div>
                      </div>

                      <div className="compare-price mt-2">{formatINR(item.price)}</div>

                      <Link to={`/product/${item.product.id}`} className="btn btn-secondary btn-sm mt-2 w-full">
                        Inspect Evidence
                      </Link>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Category & Status */}
              <tr className="compare-section-header">
                <td colSpan={comparedItems.length + 1}>Overview & Signals</td>
              </tr>
              <tr>
                <th scope="row">Brand & Category</th>
                {comparedItems.map((item) => (
                  <td key={item.variant.id}>
                    {item.product.brand} ({CATEGORY_SINGULAR[item.product.category]})
                  </td>
                ))}
              </tr>
              <tr>
                <th scope="row">Authentic Reviews</th>
                {comparedItems.map((item) => (
                  <td key={item.variant.id}>
                    <strong className="text-emerald">{item.community.authentic_percentage}%</strong>
                    <span className="small muted"> ({item.community.total_reviews_analyzed.toLocaleString()} reviews)</span>
                  </td>
                ))}
              </tr>
              <tr>
                <th scope="row">Buy Timing</th>
                {comparedItems.map((item) => (
                  <td key={item.variant.id}>
                    {item.community.buy_timing_recommendation === 'buy_now'
                      ? '🟢 Buy Now'
                      : item.community.buy_timing_recommendation === 'wait_for_sale'
                      ? '🟡 Wait for Sale'
                      : '🔵 Fair Price'}
                  </td>
                ))}
              </tr>

              {/* Parameter Rows */}
              <tr className="compare-section-header">
                <td colSpan={comparedItems.length + 1}>Deterministic Lab Parameters</td>
              </tr>

              {allParamKeys.map((paramKey) => {
                const paramLabel =
                  comparedItems.find((it) => it.evaluation.parameters.some((p) => p.key === paramKey))
                    ?.evaluation.parameters.find((p) => p.key === paramKey)?.name || paramKey;

                return (
                  <tr key={paramKey}>
                    <th scope="row">{paramLabel}</th>
                    {comparedItems.map((item) => {
                      const param = item.evaluation.parameters.find((p) => p.key === paramKey);
                      if (!param) return <td key={item.variant.id} className="muted">—</td>;

                      return (
                        <td key={item.variant.id}>
                          {param.score !== null ? (
                            <div>
                              <strong className="font-mono">{param.score}/100</strong>
                              {param.raw_value ? (
                                <div className="small muted">
                                  {param.raw_value} {param.unit || ''}
                                </div>
                              ) : null}
                            </div>
                          ) : (
                            <span className="badge badge-insufficient">Not Scored</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}

              {/* Evidence count */}
              <tr className="compare-section-header">
                <td colSpan={comparedItems.length + 1}>Verification & Citations</td>
              </tr>
              <tr>
                <th scope="row">Lab Citations Count</th>
                {comparedItems.map((item) => (
                  <td key={item.variant.id}>
                    <span className="text-cyan font-bold">{item.evidence.length} citations</span>
                    <div className="small muted">
                      {item.evidence.filter((e) => e.tier === 'tier1').length} Tier-1 Labs
                    </div>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
