import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ShieldCheck,
  CheckCircle2,
  Sparkles,
  Search,
  ExternalLink,
  Laptop,
  Smartphone,
  HardDrive,
  BarChart3,
  Scale
} from 'lucide-react';
import { api } from '../api';
import { ScoreDial, ConfidenceBadge } from '../components/trust';
import { MatchBadge } from '../components/MatchBadge';
import { formatINR } from '../lib/format';
import { usePageTitle } from '../lib/hooks';

export default function Home() {
  usePageTitle('Home — Verified Evidence & Product Evaluation');
  const { data: products } = useQuery({
    queryKey: ['list', 'featured'],
    queryFn: () => api.listProducts()
  });

  const [selectedDemoIndex, setSelectedDemoIndex] = useState(0);

  const demoItems = products?.slice(0, 3) || [];
  const currentDemo = demoItems[selectedDemoIndex] || demoItems[0];

  return (
    <div className="stack stack--lg">
      {/* Hero Section */}
      <section className="hero-banner">
        <div className="hero-badge">
          <Sparkles size={14} className="accent-icon" />
          <span>Deterministic E-Commerce Trust Architecture</span>
        </div>
        <h1 className="hero-title">
          Stop trusting fake 5-star reviews.<br />
          <span className="text-gradient">Start trusting verified evidence.</span>
        </h1>
        <p className="hero-subtitle">
          Review Master extracts raw marketplace specs, links them to independent lab benchmarks
          (Geekbench, GSMArena, DisplayMate), strips out astroturfed reviews, and delivers
          a mathematically reproducible evaluation.
        </p>

        <div className="hero-actions">
          <Link to="/catalog" className="btn btn-primary btn-lg">
            <Search size={18} />
            <span>Explore Verified Catalogue</span>
          </Link>
          <Link to="/compare" className="btn btn-secondary btn-lg">
            <Scale size={18} />
            <span>Compare Devices</span>
          </Link>
        </div>

        {/* Category Pills */}
        <div className="hero-categories">
          <span className="small muted">Categories Evaluated:</span>
          <Link to="/catalog?category=smartphone" className="category-pill">
            <Smartphone size={16} />
            <span>Smartphones</span>
          </Link>
          <Link to="/catalog?category=laptop" className="category-pill">
            <Laptop size={16} />
            <span>Laptops</span>
          </Link>
          <Link to="/catalog?category=ssd" className="category-pill">
            <HardDrive size={16} />
            <span>External SSDs</span>
          </Link>
        </div>
      </section>

      {/* The 3 Independent Trust Pillars */}
      <section className="stack">
        <div className="section-header">
          <h2>Three Independent Trust Pillars</h2>
          <p className="muted">
            Most platforms blend reviews into a single misleading star rating. Review Master keeps
            independent signals cleanly separated so you can make an informed decision.
          </p>
        </div>

        <div className="pillars-grid">
          <div className="pillar-card">
            <div className="pillar-header">
              <div className="pillar-icon pillar-icon--cyan">
                <BarChart3 size={24} />
              </div>
              <span className="pillar-num">Pillar 01</span>
            </div>
            <h3>Deterministic Lab Score</h3>
            <p className="muted">
              Calculated using domain-expert validated weights. Pure math on lab-tested specifications,
              benchmarks, and component measurements. Zero influence from sponsored ads or influencer opinions.
            </p>
            <ul className="pillar-features">
              <li><CheckCircle2 size={16} /> Geekbench & AnTuTu verified compute</li>
              <li><CheckCircle2 size={16} /> DisplayMate & DxOMark sensor labs</li>
              <li><CheckCircle2 size={16} /> Transparent mathematical weights</li>
            </ul>
          </div>

          <div className="pillar-card">
            <div className="pillar-header">
              <div className="pillar-icon pillar-icon--emerald">
                <ShieldCheck size={24} />
              </div>
              <span className="pillar-num">Pillar 02</span>
            </div>
            <h3>Evidence & Confidence Tier</h3>
            <p className="muted">
              We never fabricate scores. If test data is missing, we flag it as
              &quot;Insufficient Evidence&quot;. Every parameter cites its exact Tier 1–4 source and verification method.
            </p>
            <ul className="pillar-features">
              <li><CheckCircle2 size={16} /> Tier 1: Independent lab instruments</li>
              <li><CheckCircle2 size={16} /> Tier 2: Official manufacturer whitepapers</li>
              <li><CheckCircle2 size={16} /> Strict confidence coverage grading</li>
            </ul>
          </div>

          <div className="pillar-card">
            <div className="pillar-header">
              <div className="pillar-icon pillar-icon--violet">
                <Sparkles size={24} />
              </div>
              <span className="pillar-num">Pillar 03</span>
            </div>
            <h3>Authentic Community Signals</h3>
            <p className="muted">
              Algorithms audit thousands of marketplace customer reviews, identify incentivized
              patterns, and distill genuine owner feedback and long-term durability warnings.
            </p>
            <ul className="pillar-features">
              <li><CheckCircle2 size={16} /> Astroturf & review bot detection</li>
              <li><CheckCircle2 size={16} /> Multi-month price volatility history</li>
              <li><CheckCircle2 size={16} /> Buy now vs wait timing advice</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Interactive Live Scorecard Demo */}
      {currentDemo ? (
        <section className="stack">
          <div className="row row--between">
            <div>
              <h2>Interactive Evidence Scorecard</h2>
              <p className="muted">Select a device below to inspect its verified evaluation.</p>
            </div>
            <div className="segmented-control" role="tablist" aria-label="Demo products">
              {demoItems.map((item, idx) => (
                <button
                  key={item.product.id}
                  type="button"
                  role="tab"
                  aria-selected={idx === selectedDemoIndex}
                  className={`btn btn-sm ${idx === selectedDemoIndex ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSelectedDemoIndex(idx)}
                >
                  {item.product.name}
                </button>
              ))}
            </div>
          </div>

          <div className="scorecard-demo">
            <div className="scorecard-main">
              <div className="scorecard-hero">
                <div className="scorecard-id">
                  <div className="row">
                    <MatchBadge state={currentDemo.match_state} />
                    <span className="badge badge-neutral">{currentDemo.product.category.toUpperCase()}</span>
                    {currentDemo.variant.asin && (
                      <span className="small muted">ASIN: {currentDemo.variant.asin}</span>
                    )}
                  </div>
                  <h3>{currentDemo.product.name}</h3>
                  <div className="small muted">{currentDemo.variant.label}</div>
                  <div className="scorecard-price">{formatINR(currentDemo.price)}</div>
                </div>

                <div className="scorecard-dials">
                  <div className="dial-box">
                    <ScoreDial score={currentDemo.evaluation.overall_score} label="Score" size="lg" />
                    <span className="small muted mt-1">Review Master</span>
                  </div>
                  <div className="dial-box">
                    <ConfidenceBadge
                      state={currentDemo.evaluation.confidence.state}
                      score={currentDemo.evaluation.confidence.score}
                    />
                    <span className="small muted mt-1">
                      {currentDemo.evaluation.confidence.coverage_percent}% Coverage
                    </span>
                  </div>
                </div>
              </div>

              {/* Parameter Bar Breakdown */}
              <div className="scorecard-params">
                <h4>Deterministic Parameters ({currentDemo.evaluation.model_version})</h4>
                <div className="params-list">
                  {currentDemo.evaluation.parameters.map((p) => {
                    const pct = p.score !== null ? p.score : 0;
                    return (
                      <div key={p.key} className="param-row">
                        <div className="param-meta">
                          <span className="param-name">{p.name}</span>
                          <span className="param-val">
                            {p.score !== null ? `${p.score}/100` : <span className="muted">Not Scored</span>}
                            {p.raw_value ? ` (${p.raw_value} ${p.unit || ''})` : ''}
                          </span>
                        </div>
                        <div className="progress-bar">
                          <div
                            className={`progress-fill ${
                              p.score === null
                                ? 'progress-fill--none'
                                : p.score >= 85
                                ? 'progress-fill--high'
                                : p.score >= 70
                                ? 'progress-fill--med'
                                : 'progress-fill--low'
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="scorecard-footer">
                <Link to={`/product/${currentDemo.product.id}`} className="btn btn-primary btn-sm">
                  <span>Inspect All {currentDemo.evidence.length} Lab Citations</span>
                  <ExternalLink size={14} />
                </Link>
                <div className="small muted">
                  Authentic review score: {currentDemo.community.authentic_percentage}% verified
                </div>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {/* Browser Extension Feature Callout */}
      <section className="extension-banner">
        <div className="extension-content">
          <span className="badge badge-high">CHROME & FIREFOX EXTENSION</span>
          <h2>Audit Amazon India Listings Live In Your Browser</h2>
          <p className="muted">
            The Review Master extension runs completely client-side. When you view any product on Amazon India,
            it extracts technical specifications, runs schema validation, and queries our verified lab database
            without sending your browsing history anywhere.
          </p>
          <div className="row">
            <Link to="/catalog" className="btn btn-primary">
              View Supported Products
            </Link>
            <a
              href="https://github.com/SwayamDaphale/review-master/tree/main/extension"
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary"
            >
              Extension Source Code
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}
