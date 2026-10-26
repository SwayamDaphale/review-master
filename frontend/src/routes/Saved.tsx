import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Bookmark, Bell, Trash2, ArrowRight } from 'lucide-react';
import { api } from '../api';
import type { ProductItem } from '../types/api';
import { CATEGORY_SINGULAR } from '../types/api';
import { ScoreInline, ConfidenceBadge } from '../components/trust';
import { MatchBadge } from '../components/MatchBadge';
import { Loading } from '../components/states';
import { formatINR } from '../lib/format';
import { usePageTitle } from '../lib/hooks';
import { STORAGE_KEYS, useStoredState } from '../lib/storage';

export default function Saved() {
  usePageTitle('Saved Products & Price Alerts');
  const [savedProducts, setSavedProducts] = useStoredState<string[]>(STORAGE_KEYS.savedProducts, [
    's25-ultra-512',
    'nothing-phone-4a-256'
  ]);

  const [alerts, setAlerts] = useStoredState<Record<string, number>>(STORAGE_KEYS.priceAlerts, {
    's25-ultra-512': 125000,
    'nothing-phone-4a-256': 29999
  });

  const [editingAlertId, setEditingAlertId] = useState<string | null>(null);
  const [alertValue, setAlertValue] = useState<string>('');

  const { data: allProducts, isLoading } = useQuery({
    queryKey: ['list', 'all'],
    queryFn: () => api.listProducts()
  });

  const savedItems: ProductItem[] = (allProducts || []).filter((p) =>
    savedProducts.includes(p.product.id) || savedProducts.includes(p.variant.id)
  );

  const removeSaved = (id: string) => {
    setSavedProducts((prev) => prev.filter((p) => p !== id));
  };

  const startEditAlert = (id: string, currentTarget?: number) => {
    setEditingAlertId(id);
    setAlertValue(currentTarget ? String(currentTarget) : '');
  };

  const saveAlert = (id: string) => {
    const val = Number(alertValue);
    if (!Number.isNaN(val) && val > 0) {
      setAlerts((prev) => ({ ...prev, [id]: val }));
    } else {
      setAlerts((prev) => {
        const copy = { ...prev };
        delete copy[id];
        return copy;
      });
    }
    setEditingAlertId(null);
  };

  return (
    <div className="stack stack--lg">
      <div className="row row--between">
        <div>
          <h1>Saved Products & Price Alerts</h1>
          <p className="muted">
            Track devices you are considering. Review Master monitors marketplace fluctuations and alerts you
            when verified pricing reaches your target threshold.
          </p>
        </div>
      </div>

      {isLoading ? (
        <Loading />
      ) : savedItems.length === 0 ? (
        <div className="empty-state">
          <Bookmark size={48} className="muted" />
          <h3>No saved devices yet</h3>
          <p className="muted">
            Click the star icon on any product in our catalogue to save it here and set price drop alerts.
          </p>
          <Link to="/catalog" className="btn btn-primary mt-2">
            <span>Browse Catalogue</span>
            <ArrowRight size={16} />
          </Link>
        </div>
      ) : (
        <div className="saved-grid">
          {savedItems.map((item) => {
            const targetAlert = alerts[item.product.id] || alerts[item.variant.id];
            const isTargetMet = targetAlert ? item.price <= targetAlert : false;

            return (
              <div key={item.variant.id} className="saved-card">
                <div className="saved-card__header">
                  <div className="row">
                    <MatchBadge state={item.match_state} />
                    <span className="badge badge-neutral">
                      {CATEGORY_SINGULAR[item.product.category]}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn-icon"
                    onClick={() => removeSaved(item.product.id)}
                    title="Remove from saved"
                    aria-label="Remove saved product"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>

                <div className="saved-card__body">
                  <h3 className="saved-card__title">
                    <Link to={`/product/${item.product.id}`}>{item.product.name}</Link>
                  </h3>
                  <div className="small muted mb-2">
                    {item.product.brand} · {item.variant.label}
                  </div>

                  <div className="row row--between mb-2">
                    <div className="row">
                      <span className="small muted">Score:</span>
                      <ScoreInline score={item.evaluation.overall_score} />
                    </div>
                    <ConfidenceBadge
                      state={item.evaluation.confidence.state}
                      score={item.evaluation.confidence.score}
                    />
                  </div>

                  <div className="saved-card__price-box">
                    <div>
                      <span className="small muted">Current Price</span>
                      <div className="saved-card__price">{formatINR(item.price)}</div>
                    </div>

                    <div className="saved-card__alert-box">
                      {editingAlertId === item.product.id ? (
                        <div className="row">
                          <input
                            type="number"
                            className="input input--num input--sm"
                            placeholder="Target INR"
                            value={alertValue}
                            onChange={(e) => setAlertValue(e.target.value)}
                          />
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => saveAlert(item.product.id)}
                          >
                            Save
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className={`btn btn-sm ${isTargetMet ? 'btn-primary' : 'btn-ghost'}`}
                          onClick={() => startEditAlert(item.product.id, targetAlert)}
                        >
                          <Bell size={14} />
                          <span>
                            {targetAlert
                              ? isTargetMet
                                ? `Alert Met: ≤ ${formatINR(targetAlert)}`
                                : `Alert: ≤ ${formatINR(targetAlert)}`
                              : 'Set Price Alert'}
                          </span>
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="small muted mt-2">
                    Signal:{' '}
                    {item.community.buy_timing_recommendation === 'buy_now'
                      ? '🔥 Good time to buy (low price)'
                      : item.community.buy_timing_recommendation === 'wait_for_sale'
                      ? '⏳ Consider waiting for promotion'
                      : '⚖️ Fair market rate'}
                  </div>
                </div>

                <div className="saved-card__footer">
                  <Link to={`/product/${item.product.id}`} className="btn btn-primary btn-sm w-full">
                    Inspect Evidence & Citations
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
