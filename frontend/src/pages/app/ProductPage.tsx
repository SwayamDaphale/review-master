import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { usePageTitle } from '../../lib/hooks';
import { CATEGORY_LABEL, type CommunityInsights, type ExpertAssessmentSummary, type PriceHistory, type VariantView } from '../../types/api';
import { formatDate, formatINR, formatRelative } from '../../lib/format';
import { AiSummary, ConfidenceBadge, EvidenceMeter, MeterLegend, SampleBadge, ScoreRing } from '../../components/trust';
import { ParameterList } from '../../components/ParameterList';
import { PriceChart } from '../../components/PriceChart';
import { SpecTable, VariantPicker } from '../../components/misc';
import { Tabs } from '../../components/Tabs';
import { MatchBadge } from '../../components/MatchBadge';
import { ErrorState, Loading, Notice } from '../../components/states';
import { useLibrary } from '../../state/library';
import { useSiteSettings } from '../../state/siteSettings';

function ScoreSection({ view }: { view: VariantView }) {
  const ev = view.evaluation;
  return (
    <section className="panel" aria-labelledby="score-h">
      <h2 id="score-h">Review Master score and confidence</h2>
      <div className="score-block">
        <ScoreRing score={ev.overall_score} size={148} />
        <div className="stack">
          <ConfidenceBadge state={ev.confidence.state} score={ev.confidence.score} />
          <ul className="reasons">
            {ev.confidence.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="small muted">
            Model: {ev.model.name}, version {ev.model.version}. Evaluated {formatDate(ev.created_at)}.
          </p>
        </div>
      </div>
      {ev.overall_score === null ? (
        <Notice tone="warn">
          The overall score is withheld because there is not enough evidence. Parameters that do have evidence are shown below.
        </Notice>
      ) : null}
      {ev.limitations.length > 0 ? (
        <ul className="limits">
          {ev.limitations.map((l) => (
            <li key={l} className="small muted">{l}</li>
          ))}
        </ul>
      ) : null}
      <AiSummary explanation={view.explanation} />
      <div className="stack">
        <h3>How the score is built</h3>
        <EvidenceMeter parameters={ev.parameters} />
        <MeterLegend />
      </div>
      <div className="stack">
        <h3>Parameters and their evidence</h3>
        <ParameterList parameters={ev.parameters} />
      </div>
    </section>
  );
}

function CommunitySection({ community, rating }: { community: CommunityInsights; rating: VariantView['marketplace_rating'] }) {
  return (
    <section className="panel" aria-labelledby="community-h">
      <h2 id="community-h">Community feedback</h2>
      <p className="small muted">Kept separate from the score. Community feedback never changes it.</p>
      {community.status === 'available' ? (
        <>
          <p>
            From {community.sample_size} Review Master reviews{community.ai_generated ? ', summarised by AI' : ''}.
          </p>
          <ul className="themes">
            {community.themes.map((t) => (
              <li key={t.label}>
                <span>{t.label}</span>
                <span className={`badge badge-${t.polarity === 'positive' ? 'high' : t.polarity === 'negative' ? 'insufficient' : 'limited'}`}>
                  {t.polarity}, {t.count}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="muted">
          Not enough feedback yet{community.sample_size > 0 ? ` (${community.sample_size} so far)` : ''}. A summary appears once there
          are enough reviews to be meaningful.
        </p>
      )}
      <h3>Review-pattern signals</h3>
      {community.review_quality_signals.length === 0 ? (
        <p className="small muted">No unusual review patterns detected in the reviews analysed.</p>
      ) : (
        <ul className="signals">
          {community.review_quality_signals.map((s) => (
            <li key={s.signal_type}>
              <span className="badge badge-limited">{s.strength} signal</span>
              <span>{s.description}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="small muted">Signals point to patterns worth a closer look. They are not proof that a review is untrue.</p>
      {rating ? (
        <p className="small muted">
          External rating (not part of the score): {rating.rating.toFixed(1)} from {rating.count.toLocaleString('en-IN')} ratings on {rating.source}.
        </p>
      ) : null}
    </section>
  );
}

function ExpertSection({ expert }: { expert: ExpertAssessmentSummary }) {
  return (
    <section className="panel" aria-labelledby="expert-h">
      <h2 id="expert-h">Expert assessment</h2>
      {expert.status === 'published' ? (
        <>
          <p className="small muted">
            {expert.expert_label}
            {expert.published_at ? `, published ${formatDate(expert.published_at)}` : ''}
          </p>
          <ul className="findings">
            {expert.findings.map((f) => (
              <li key={f.parameter}>
                <strong>{f.parameter}</strong>
                <span>{f.finding}</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="muted">No expert assessment has been published for this product yet.</p>
      )}
    </section>
  );
}

function PriceSection({ view, history }: { view: VariantView; history: PriceHistory | undefined }) {
  const [days, setDays] = useState<'30' | '90'>('30');
  const [target, setTarget] = useState('');
  const [saved, setSaved] = useState(false);
  const { addAlert, signedIn } = useLibrary();
  const [settings] = useSiteSettings();
  const navigate = useNavigate();
  const targetNum = Number(target);
  const valid = Number.isFinite(targetNum) && targetNum > 0;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!signedIn) {
      navigate('/login', { state: { from: window.location.pathname + window.location.search } });
      return;
    }
    if (!valid) return;
    addAlert(view.variant.id, targetNum);
    setSaved(true);
  };

  return (
    <section className="panel" aria-labelledby="price-h">
      <h2 id="price-h">Price</h2>
      {view.offers.length === 0 ? (
        <p className="muted">No current offers are available for this variant.</p>
      ) : (
        <ul className="offers">
          {view.offers.map((o) => (
            <li key={o.offer_id}>
              <div>
                <strong className="num">{formatINR(o.price)}</strong>
                <span className="small muted">{o.seller}</span>
              </div>
              <div className="small muted">
                {o.availability === 'in_stock' ? 'In stock' : o.availability === 'out_of_stock' ? 'Out of stock' : 'Availability unknown'}, {o.source}, checked {formatRelative(o.observed_at)}
                {o.stale ? <span className="badge badge-limited">Old price</span> : null}
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="stack">
        <div className="row row--between">
          <h3>Price history</h3>
          <Tabs
            label="History length"
            tabs={[{ id: '30', label: '30 days' }, { id: '90', label: '90 days' }]}
            value={days}
            onChange={setDays}
          />
        </div>
        {history ? (
          <>
            <PriceChart history={history} days={days === '30' ? 30 : 90} />
            {history.coverage_days < Number(days) ? (
              <p className="small muted">Only {history.coverage_days} days of history are available, so the range may not be typical.</p>
            ) : null}
          </>
        ) : (
          <Loading />
        )}
      </div>
      {settings.features.priceAlerts ? (
        <form className="alert-form" onSubmit={submit}>
          <label htmlFor="alert-target">Notify me when the price drops below</label>
          <div className="row">
            <span className="input-prefix">
              <span aria-hidden="true">₹</span>
              <input
                id="alert-target"
                className="input"
                inputMode="numeric"
                value={target}
                onChange={(e) => {
                  setTarget(e.target.value.replace(/[^\d]/g, ''));
                  setSaved(false);
                }}
                placeholder="e.g. 89999"
              />
            </span>
            <button type="submit" className="btn btn-secondary" disabled={signedIn && !valid}>
              {signedIn ? 'Create alert' : 'Sign in to set an alert'}
            </button>
          </div>
          {saved ? (
            <p className="small" role="status">
              Alert saved in this browser. Alerts are not checked yet because the price service is not built.
            </p>
          ) : null}
        </form>
      ) : null}
    </section>
  );
}

export default function ProductPage() {
  const { productId } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { isSaved, toggleSaved, signedIn } = useLibrary();

  const productQ = useQuery({
    queryKey: ['product', productId],
    queryFn: () => api.getProduct(productId ?? ''),
    enabled: Boolean(productId),
  });
  const wanted = params.get('v');
  const variants = productQ.data?.variants ?? [];
  const variantId = variants.find((v) => v.id === wanted)?.id ?? variants[0]?.id;

  const viewQ = useQuery({
    queryKey: ['variant-view', variantId],
    queryFn: () => api.getVariantView(variantId ?? ''),
    enabled: Boolean(variantId),
  });
  const histQ = useQuery({
    queryKey: ['history', variantId],
    queryFn: () => api.getPriceHistory(variantId ?? ''),
    enabled: Boolean(variantId),
  });

  const view = viewQ.data;
  usePageTitle(view ? view.product.name : 'Product');

  if (productQ.isLoading || (variantId && viewQ.isLoading)) return <Loading label="Loading product" />;
  if (productQ.error || viewQ.error || !productQ.data || !view || !variantId) {
    return (
      <ErrorState
        title="Product not found"
        message="We could not find this product. It may have been removed, or the link may be wrong."
        action={<Link to="/app" className="btn btn-secondary btn-sm">Back to Explore</Link>}
      />
    );
  }

  const topOffer = view.offers[0];
  const saved = isSaved(variantId);

  return (
    <div className="page stack stack--lg">
      <nav aria-label="Breadcrumb" className="crumbs small">
        <Link to="/app">Explore</Link>
        <span aria-hidden="true">/</span>
        <span>{CATEGORY_LABEL[view.product.category]}</span>
      </nav>

      <header className="product-head">
        <div className="stack">
          <div className="row">
            <h1>{view.product.name}</h1>
            {view.sample ? <SampleBadge /> : null}
          </div>
          <VariantPicker
            variants={productQ.data.variants}
            value={variantId}
            onChange={(id) => setParams({ v: id }, { replace: true })}
          />
          {productQ.data.variants.length < 2 ? <p className="muted">{view.variant.label}</p> : null}
        </div>
        <div className="product-head__side">
          <div className="price-now num">{formatINR(topOffer?.price ?? null)}</div>
          <div className="small muted">
            {topOffer ? (topOffer.availability === 'in_stock' ? 'In stock' : 'Check availability') : 'No current offer'}
          </div>
          <div className="row">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              aria-pressed={saved}
              onClick={() =>
                signedIn
                  ? toggleSaved(variantId)
                  : navigate('/login', { state: { from: window.location.pathname + window.location.search } })
              }
            >
              {saved ? 'Saved' : signedIn ? 'Save' : 'Sign in to save'}
            </button>
            <Link to={`/app/compare?ids=${variantId}`} className="btn btn-secondary btn-sm">
              Compare
            </Link>
          </div>
        </div>
      </header>

      {view.match_state !== 'confirmed' ? (
        <Notice tone="warn">
          <MatchBadge state={view.match_state} /> This listing was matched to the catalogue but not confirmed. Check that the variant
          is the one you are looking at before relying on the score.
        </Notice>
      ) : null}

      <div className="product-grid">
        <div className="stack stack--lg">
          <ScoreSection view={view} />
          <section className="panel" aria-labelledby="specs-h">
            <h2 id="specs-h">Specifications</h2>
            <SpecTable specs={view.specs} />
          </section>
        </div>
        <div className="stack stack--lg">
          <CommunitySection community={view.community} rating={view.marketplace_rating} />
          <ExpertSection expert={view.expert} />
          <PriceSection view={view} history={histQ.data} />
        </div>
      </div>
    </div>
  );
}
