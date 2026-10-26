import { useState, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, Filter, ArrowUpDown, ChevronRight, Check } from 'lucide-react';
import { api } from '../api';
import type { Category, ProductItem } from '../types/api';
import { CATEGORY_SINGULAR } from '../types/api';
import { ScoreInline, ConfidenceBadge } from '../components/trust';
import { MatchBadge } from '../components/MatchBadge';
import { Loading } from '../components/states';
import { formatINR } from '../lib/format';
import { usePageTitle } from '../lib/hooks';
import { STORAGE_KEYS, useStoredState } from '../lib/storage';

export default function Catalog() {
  usePageTitle('Catalogue — Verified Evidence');
  const [searchParams, setSearchParams] = useSearchParams();
  const categoryParam = searchParams.get('category') as Category | null;

  const [activeCategory, setActiveCategory] = useState<string>(categoryParam || 'all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'score' | 'price-asc' | 'price-desc' | 'confidence'>('score');

  const [savedProducts, setSavedProducts] = useStoredState<string[]>(STORAGE_KEYS.savedProducts, []);
  const [compareList, setCompareList] = useStoredState<string[]>(STORAGE_KEYS.compareList, []);

  const { data: products, isLoading } = useQuery({
    queryKey: ['products', activeCategory],
    queryFn: () => (activeCategory === 'all' ? api.listProducts() : api.listProducts(activeCategory as Category))
  });

  const toggleSave = (id: string) => {
    setSavedProducts((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));
  };

  const toggleCompare = (id: string) => {
    setCompareList((prev) => {
      if (prev.includes(id)) return prev.filter((p) => p !== id);
      if (prev.length >= 4) return prev; // max 4
      return [...prev, id];
    });
  };

  const filtered = useMemo(() => {
    if (!products) return [];
    let list = [...products];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (p) =>
          p.product.name.toLowerCase().includes(q) ||
          p.product.brand.toLowerCase().includes(q) ||
          p.variant.label.toLowerCase().includes(q) ||
          p.variant.asin?.toLowerCase().includes(q)
      );
    }

    list.sort((a, b) => {
      if (sortBy === 'score') {
        return (b.evaluation.overall_score ?? -1) - (a.evaluation.overall_score ?? -1);
      }
      if (sortBy === 'price-asc') {
        return a.price - b.price;
      }
      if (sortBy === 'price-desc') {
        return b.price - a.price;
      }
      if (sortBy === 'confidence') {
        return b.evaluation.confidence.score - a.evaluation.confidence.score;
      }
      return 0;
    });

    return list;
  }, [products, searchQuery, sortBy]);

  const setCategoryFilter = (cat: string) => {
    setActiveCategory(cat);
    if (cat === 'all') {
      searchParams.delete('category');
    } else {
      searchParams.set('category', cat);
    }
    setSearchParams(searchParams);
  };

  return (
    <div className="stack stack--lg">
      <div className="catalog-header">
        <div>
          <h1>Verified Product Catalogue</h1>
          <p className="muted">
            All devices below have been processed through deterministic lab-score models with verified evidence citations.
          </p>
        </div>

        {compareList.length > 0 && (
          <Link to="/compare" className="btn btn-secondary btn-sm">
            <span>Compare Selected ({compareList.length})</span>
            <ChevronRight size={16} />
          </Link>
        )}
      </div>

      {/* Filter and Search Bar */}
      <div className="catalog-toolbar">
        <div className="search-bar">
          <Search size={18} className="search-icon" />
          <input
            type="search"
            className="input search-input"
            placeholder="Search by product name, brand, or ASIN..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="filter-controls">
          <div className="category-tabs" role="tablist" aria-label="Product categories">
            {['all', 'smartphone', 'laptop', 'ssd'].map((cat) => (
              <button
                key={cat}
                type="button"
                role="tab"
                aria-selected={activeCategory === cat}
                className={`tab-btn ${activeCategory === cat ? 'is-active' : ''}`}
                onClick={() => setCategoryFilter(cat)}
              >
                {cat === 'all' ? 'All Devices' : CATEGORY_SINGULAR[cat as Category]}
              </button>
            ))}
          </div>

          <div className="sort-dropdown">
            <ArrowUpDown size={16} className="muted" />
            <select
              aria-label="Sort products by"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="select-sort"
            >
              <option value="score">Sort: Highest Score</option>
              <option value="confidence">Sort: Highest Confidence</option>
              <option value="price-asc">Sort: Price Low to High</option>
              <option value="price-desc">Sort: Price High to Low</option>
            </select>
          </div>
        </div>
      </div>

      {/* Product List */}
      {isLoading ? (
        <Loading />
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <Filter size={40} className="muted" />
          <h3>No matching devices found</h3>
          <p className="muted">Try adjusting your category filter or search keywords.</p>
        </div>
      ) : (
        <div className="catalog-grid">
          {filtered.map((item: ProductItem) => {
            const isSaved = savedProducts.includes(item.product.id);
            const isComparing = compareList.includes(item.product.id);

            return (
              <article key={item.variant.id} className="catalog-card">
                <div className="catalog-card__header">
                  <div className="row">
                    <MatchBadge state={item.match_state} />
                    <span className="badge badge-neutral">
                      {CATEGORY_SINGULAR[item.product.category]}
                    </span>
                  </div>
                  <div className="row">
                    <button
                      type="button"
                      className={`btn-icon ${isSaved ? 'is-active' : ''}`}
                      onClick={() => toggleSave(item.product.id)}
                      title={isSaved ? 'Remove from saved' : 'Save for alerts'}
                      aria-label="Save product"
                    >
                      {isSaved ? '★' : '☆'}
                    </button>
                  </div>
                </div>

                <div className="catalog-card__body">
                  <h3 className="catalog-card__title">
                    <Link to={`/product/${item.product.id}`}>{item.product.name}</Link>
                  </h3>
                  <div className="small muted mb-2">
                    {item.product.brand} · {item.variant.label}
                    {item.variant.asin && ` · ASIN: ${item.variant.asin}`}
                  </div>

                  <div className="catalog-card__metrics">
                    <div className="metric-box">
                      <span className="metric-label">Review Master</span>
                      <ScoreInline score={item.evaluation.overall_score} />
                    </div>
                    <div className="metric-box">
                      <span className="metric-label">Confidence</span>
                      <ConfidenceBadge
                        state={item.evaluation.confidence.state}
                        score={item.evaluation.confidence.score}
                      />
                    </div>
                  </div>

                  <div className="catalog-card__price-row">
                    <div>
                      <div className="catalog-card__price">{formatINR(item.price)}</div>
                      <div className="small muted">
                        {item.community.buy_timing_recommendation === 'buy_now'
                          ? '🔥 Good time to buy'
                          : item.community.buy_timing_recommendation === 'wait_for_sale'
                          ? '⏳ Price drop expected'
                          : '⚖️ Fair market price'}
                      </div>
                    </div>
                    <div className="small muted">
                      {item.community.authentic_percentage}% verified reviews
                    </div>
                  </div>
                </div>

                <div className="catalog-card__footer">
                  <button
                    type="button"
                    className={`btn btn-sm ${isComparing ? 'btn-secondary' : 'btn-ghost'}`}
                    onClick={() => toggleCompare(item.product.id)}
                  >
                    {isComparing ? (
                      <>
                        <Check size={14} />
                        <span>In Compare</span>
                      </>
                    ) : (
                      '+ Compare'
                    )}
                  </button>
                  <Link to={`/product/${item.product.id}`} className="btn btn-primary btn-sm">
                    Inspect Evidence
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
