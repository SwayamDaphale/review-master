import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { usePageTitle } from '../../lib/hooks';
import { formatINR } from '../../lib/format';
import { ConfidenceBadge, ScoreInline } from '../../components/trust';
import { EmptyState, ErrorState, Loading } from '../../components/states';
import { httpClient } from '../../api/httpClient';
import type { ApiRecommendationResponse } from '../../types/api';

export default function RecommendationsPage() {
  usePageTitle('Recommendations');
  const [query, setQuery] = useState('');
  const [categoryKey, setCategoryKey] = useState('smartphone');

  const mutation = useMutation<ApiRecommendationResponse, Error, { query: string; category_key: string }>({
    mutationFn: (vars) =>
      httpClient.generateRecommendations({
        query: vars.query,
        category_key: vars.category_key,
        limit: 5,
      }),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    mutation.mutate({ query: query.trim(), category_key: categoryKey });
  };

  const data = mutation.data;

  return (
    <div className="page stack stack--lg">
      <div className="stack">
        <h1>Requirement-Based Recommendations</h1>
        <p className="lead">
          Describe what you need in plain language. The system applies strict deterministic hard constraints,
          verifies catalog specifications, and ranks eligible products using Review Master evaluation scores.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="stack" style={{ maxWidth: '720px' }}>
        <div className="row" style={{ gap: '1rem', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label htmlFor="req-query" className="label" style={{ fontWeight: 600, marginBottom: '0.25rem', display: 'block' }}>
              Your Requirements
            </label>
            <input
              id="req-query"
              className="input"
              type="text"
              placeholder="e.g. Smartphone under ₹25,000 with at least 8GB RAM and 128GB storage"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{ width: '100%', padding: '0.75rem' }}
            />
          </div>
          <div>
            <label htmlFor="req-cat" className="label" style={{ fontWeight: 600, marginBottom: '0.25rem', display: 'block' }}>
              Category
            </label>
            <select
              id="req-cat"
              className="select"
              value={categoryKey}
              onChange={(e) => setCategoryKey(e.target.value)}
              style={{ padding: '0.75rem' }}
            >
              <option value="smartphone">Smartphones</option>
              <option value="laptop">Laptops</option>
              <option value="external_ssd">External SSDs</option>
            </select>
          </div>
          <button type="submit" className="btn btn-primary" disabled={mutation.isPending || !query.trim()} style={{ height: '42px' }}>
            {mutation.isPending ? 'Finding...' : 'Find Products'}
          </button>
        </div>
      </form>

      {mutation.isPending && <Loading label="Extracting requirements and evaluating catalog products..." />}

      {mutation.isError && (
        <ErrorState
          title="Could not generate recommendations"
          message={mutation.error.message || 'An unexpected error occurred while processing requirements.'}
        />
      )}

      {data && (
        <div className="stack stack--lg">
          {/* Parsed Constraints Snapshot */}
          <div className="card" style={{ padding: '1.25rem', backgroundColor: 'var(--surface-subtle, #f8f9fa)', borderRadius: '8px' }}>
            <h3 style={{ marginTop: 0, marginBottom: '0.75rem' }}>Verified Requirements Snapshot</h3>
            <div className="row" style={{ gap: '1.5rem', flexWrap: 'wrap' }}>
              <div>
                <span className="muted small">Category:</span> <strong>{data.category_key}</strong>
              </div>
              {data.parsed_requirements.budget_max && (
                <div>
                  <span className="muted small">Maximum Budget:</span> <strong>{formatINR(data.parsed_requirements.budget_max)}</strong>
                </div>
              )}
              <div>
                <span className="muted small">Hard Constraints:</span>{' '}
                {data.parsed_requirements.hard_constraints.length > 0 ? (
                  data.parsed_requirements.hard_constraints.map((hc, idx) => (
                    <span key={idx} className="badge badge--neutral" style={{ marginRight: '0.5rem' }}>
                      {hc.attribute_key.toUpperCase()} {hc.operator} {String(hc.target_value)} {hc.unit || ''}
                    </span>
                  ))
                ) : (
                  <span className="muted">None specified</span>
                )}
              </div>
              {data.parsed_requirements.soft_preferences.length > 0 && (
                <div>
                  <span className="muted small">Preferences:</span>{' '}
                  {data.parsed_requirements.soft_preferences.map((sp, idx) => (
                    <span key={idx} className="badge badge--info" style={{ marginRight: '0.5rem' }}>
                      {sp.description || sp.preference_key}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Ranked Eligible Products */}
          <div className="stack">
            <h2>Eligible Recommendations ({data.eligible_count})</h2>
            {data.ranked_recommendations.length === 0 ? (
              <EmptyState
                title="No matching products found"
                message="None of the products in the catalog satisfied all your required hard constraints. Check excluded products below for details."
              />
            ) : (
              <div className="stack" style={{ gap: '1rem' }}>
                {data.ranked_recommendations.map((item) => (
                  <div
                    key={item.variant_id}
                    className="card"
                    style={{
                      padding: '1.5rem',
                      border: '1px solid var(--border-color, #e2e8f0)',
                      borderRadius: '8px',
                    }}
                  >
                    <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span
                            className="badge badge--primary"
                            style={{ fontSize: '1rem', padding: '0.2rem 0.6rem', fontWeight: 'bold' }}
                          >
                            #{item.rank}
                          </span>
                          <h3 style={{ margin: 0 }}>
                            <Link to={`/app/products/${item.product_id}`}>{item.product_name}</Link>
                          </h3>
                        </div>
                        <div className="muted small" style={{ marginTop: '0.25rem' }}>
                          {item.manufacturer} • {item.sku_label}
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>{formatINR(item.current_price)}</div>
                        <div style={{ marginTop: '0.25rem' }}>
                          <ScoreInline score={item.overall_score} />
                          <span style={{ marginLeft: '0.5rem' }}>
                            <ConfidenceBadge state={item.confidence_state as any} score={item.confidence_score ?? undefined} />
                          </span>
                        </div>
                      </div>
                    </div>

                    <div style={{ marginTop: '1rem', borderTop: '1px solid #edf2f7', paddingTop: '0.75rem' }}>
                      <p style={{ margin: 0, color: 'var(--text-color, #2d3748)', lineHeight: 1.5 }}>
                        <strong>Why recommended:</strong> {item.explanation}
                      </p>
                    </div>

                    {item.community_summary && (
                      <div className="muted small" style={{ marginTop: '0.5rem' }}>
                        <strong>Customer Sentiment:</strong> {item.community_summary}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Excluded Candidates Section */}
          {data.excluded_candidates.length > 0 && (
            <div className="stack" style={{ marginTop: '2rem' }}>
              <h3 className="muted">Excluded Products ({data.ineligible_count})</h3>
              <p className="muted small" style={{ marginTop: 0 }}>
                Products that failed a hard constraint or had unverified (UNKNOWN) specifications were strictly excluded from recommendations.
              </p>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Variant</th>
                      <th>Status</th>
                      <th>Reason for Exclusion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.excluded_candidates.map((exc) => (
                      <tr key={exc.variant_id}>
                        <td>{exc.product_name}</td>
                        <td className="muted">{exc.sku_label}</td>
                        <td>
                          {exc.failed_constraints.length > 0 ? (
                            <span className="badge badge--danger" style={{ color: '#e53e3e' }}>FAIL</span>
                          ) : (
                            <span className="badge badge--warning" style={{ color: '#d69e2e' }}>UNKNOWN</span>
                          )}
                        </td>
                        <td className="small">{exc.reasons.join('; ')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Audit & Fingerprint Information */}
          <div className="muted small" style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
            <span>Audit Fingerprint (Input): <code>{data.input_fingerprint.slice(0, 16)}...</code></span> •{' '}
            <span>Audit Fingerprint (Output): <code>{data.output_fingerprint.slice(0, 16)}...</code></span> •{' '}
            <span>Ranking Policy: <code>{data.ranking_policy_version}</code></span>
          </div>
        </div>
      )}
    </div>
  );
}
