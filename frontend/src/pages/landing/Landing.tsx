import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import { usePageTitle } from '../../lib/hooks';
import { CATEGORY_LABEL, type Category } from '../../types/api';
import { displayScore } from '../../lib/format';
import { Tabs } from '../../components/Tabs';
import { ProductRow } from '../../components/ProductRow';
import { Loading } from '../../components/states';
import {
  ConfidenceBadge,
  EvidenceMeter,
  MeterLegend,
  NotScored,
  SampleBadge,
  ScoreRing,
  TierBadge,
  bestTier,
} from '../../components/trust';

function HeroScorecard() {
  const [active, setActive] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ['hero-view'],
    queryFn: () => api.getVariantView('v-s25u-12-256'),
  });
  if (isLoading || !data) return <div className="scorecard"><Loading label="Loading example" /></div>;
  const ev = data.evaluation;
  const activeParam = ev.parameters.find((p) => p.key === active) ?? null;
  const activeTier = activeParam ? bestTier(activeParam.evidence) : null;
  return (
    <div className="scorecard" aria-label="Example scorecard">
      <div className="scorecard__top">
        <div>
          <div className="scorecard__name">{data.product.name}</div>
          <div className="small muted">{data.variant.label}</div>
        </div>
        <SampleBadge />
      </div>
      <div className="scorecard__main">
        <ScoreRing score={ev.overall_score} size={116} />
        <div className="stack stack--tight">
          <ConfidenceBadge state={ev.confidence.state} score={ev.confidence.score} />
          <p className="small muted">{ev.confidence.reasons[0]}</p>
        </div>
      </div>
      <div>
        <div className="small muted scorecard__label">How the score is built</div>
        <EvidenceMeter parameters={ev.parameters} activeKey={active} onActiveChange={setActive} />
      </div>
      <ul className="scorecard__params">
        {ev.parameters.map((p) => (
          <li key={p.key}>
            <button
              type="button"
              className={active === p.key ? 'is-active' : undefined}
              onMouseEnter={() => setActive(p.key)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(p.key)}
              onBlur={() => setActive(null)}
            >
              <span>{p.name}</span>
              <span className="num">{displayScore(p.score) ?? <NotScored />}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="scorecard__detail small" aria-live="polite">
        {activeParam ? (
          <>
            <strong>{activeParam.name}:</strong>{' '}
            {activeTier ? (
              <>
                <TierBadge tier={activeTier} /> {activeParam.evidence[0]?.label}
              </>
            ) : (
              'No evidence yet, so this is not scored.'
            )}
          </>
        ) : (
          <span className="muted">Point at a parameter to see the evidence behind it.</span>
        )}
      </p>
    </div>
  );
}

function Hero() {
  return (
    <section className="hero">
      <div className="container hero__grid">
        <div className="hero__copy">
          <h1 className="display">Stop trusting fake 5-star reviews. Start trusting verified evidence.</h1>
          <p className="lead">
            Review Master replaces star averages with a transparent score, traceable evidence and a clear statement of how
            sure it is. It also checks review patterns for anything unusual.
          </p>
          <div className="row">
            <Link to="/app" className="btn btn-primary btn-lg">
              Open the app
            </Link>
            <Link to="/extension" className="btn btn-secondary btn-lg">
              Get the browser extension
            </Link>
          </div>
          <p className="small muted">The extension is in developer preview. The scores shown today are sample data.</p>
        </div>
        <HeroScorecard />
      </div>
    </section>
  );
}

const ROWS: [string, string, string][] = [
  ['What you see', 'One average from thousands of reviews', 'A score, how sure we are, and the evidence behind it'],
  ['Specifications', 'Written by the seller, in whatever units they choose', 'Converted to the same units, with the source shown'],
  ['Missing information', 'Often hidden or ignored', 'Shown as "Not scored", never counted as a zero'],
  ['Reviews', 'Counted as they come', 'Checked for unusual patterns such as bursts and repeated wording'],
  ['AI', 'Can invent details that sound right', 'Writes summaries only from stored evidence, and labels them'],
  ['Money', 'Sponsored placement can shape what you see', 'No brand, seller or customer can change a score'],
];

function Compare() {
  return (
    <section className="section" id="how">
      <div className="container">
        <h2>Why star ratings fall short</h2>
        <p className="lead narrow">
          Review Master does not average opinions. It scores products from evidence, then shows you how much that evidence can be
          trusted.
        </p>
        <div className="table-wrap">
          <table className="table compare-plain">
            <caption className="sr-only">Star ratings compared with Review Master</caption>
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">Topic</span></th>
                <th scope="col">Star ratings</th>
                <th scope="col">Review Master</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map(([topic, a, b]) => (
                <tr key={topic}>
                  <th scope="row">{topic}</th>
                  <td className="muted">{a}</td>
                  <td>{b}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function Pillars() {
  const { data } = useQuery({ queryKey: ['hero-view'], queryFn: () => api.getVariantView('v-s25u-12-256') });
  const { data: hist } = useQuery({ queryKey: ['hero-history'], queryFn: () => api.getPriceHistory('v-s25u-12-256') });
  const pts = hist?.points.slice(-30) ?? [];
  const lo = pts.length ? Math.min(...pts.map((p) => p.price)) : 0;
  const hi = pts.length ? Math.max(...pts.map((p) => p.price)) : 1;
  const path = pts
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${(i * 120) / Math.max(pts.length - 1, 1)} ${36 - ((p.price - lo) * 32) / (hi - lo || 1)}`)
    .join(' ');
  return (
    <section className="section section--tint">
      <div className="container">
        <h2>Three answers, kept apart</h2>
        <p className="lead narrow">A single number hides too much. Review Master shows these separately and never blends them.</p>
        <div className="pillars">
          <article>
            <div className="pillar__visual">
              <ScoreRing score={data?.evaluation.overall_score ?? null} size={84} />
            </div>
            <h3>The score</h3>
            <p>
              A published, versioned model turns specifications and test results into one score. The same inputs always give the
              same score, and AI never sets or changes it.
            </p>
          </article>
          <article>
            <div className="pillar__visual">
              {data ? <EvidenceMeter parameters={data.evaluation.parameters} /> : null}
            </div>
            <h3>The confidence</h3>
            <p>
              How much of the score rests on real evidence, and how good that evidence is. Missing data is shown as not scored,
              never as zero.
            </p>
          </article>
          <article>
            <div className="pillar__visual">
              <svg viewBox="0 0 120 40" className="spark" role="img" aria-label="Price over 30 days">
                <path d={path || 'M0 20 L120 20'} />
              </svg>
            </div>
            <h3>People and the market</h3>
            <p>
              Community feedback, review-pattern checks, expert notes and price history sit beside the score, not inside it.
            </p>
          </article>
        </div>
        <MeterLegend />
      </div>
    </section>
  );
}

function Categories() {
  const [cat, setCat] = useState<Category>('smartphone');
  const { data, isLoading } = useQuery({ queryKey: ['landing-list', cat], queryFn: () => api.listProducts(cat) });
  return (
    <section className="section" id="categories">
      <div className="container">
        <h2>Start with phones, laptops and SSDs</h2>
        <p className="lead narrow">These three categories come first. Open any product to see its score, evidence and price history.</p>
        <Tabs
          label="Category"
          value={cat}
          onChange={setCat}
          tabs={(Object.keys(CATEGORY_LABEL) as Category[]).map((c) => ({ id: c, label: CATEGORY_LABEL[c] }))}
        />
        <div role="tabpanel" id={`panel-${cat}`} aria-labelledby={`tab-${cat}`}>
          {isLoading || !data ? (
            <Loading />
          ) : (
            <ul className="prow-list">
              {data.map((item) => (
                <ProductRow key={item.variant.id} item={item} />
              ))}
            </ul>
          )}
        </div>
        <p className="small muted">Sample data. Only the Galaxy S25 Ultra and iPhone 17 Pro Max details come from real Amazon India captures.</p>
      </div>
    </section>
  );
}

function ExtensionPreview() {
  const [done, setDone] = useState(false);
  const fields: [string, string][] = [
    ['Brand', 'Samsung'],
    ['Model', 'Galaxy S25 Ultra'],
    ['Config', '12 GB RAM / 256 GB'],
    ['Price', '₹94,999'],
    ['Battery', '5000 mAh'],
    ['Display', '6.9 in'],
    ['5G', 'Yes'],
    ['Processor', 'Snapdragon 8 Elite'],
  ];
  return (
    <section className="section section--tint" id="extension">
      <div className="container split">
        <div className="stack">
          <h2>Read a listing without leaving the page</h2>
          <p className="lead">
            Open a smartphone on Amazon India and press Extract. The extension reads the specifications already on the page and
            turns them into one clean record you can check, download and bring into the app.
          </p>
          <ul className="ticks">
            <li>It only runs when you press the button.</li>
            <li>It flags anything it could not read, instead of guessing.</li>
            <li>It does not read cookies, your browsing history or your account.</li>
          </ul>
          <div>
            <Link to="/extension" className="btn btn-secondary">
              How to install it
            </Link>
          </div>
        </div>
        <div className="browser" aria-label="Browser extension preview">
          <div className="browser__bar">
            <span className="dots" aria-hidden="true"><i /><i /><i /></span>
            <span className="browser__url">amazon.in/Samsung-Galaxy-S25-Ultra/dp/B0DSKMV3ZC</span>
          </div>
          <div className="browser__body">
            <div className="browser__page" aria-hidden="true">
              <div className="ph ph--img" />
              <div className="ph ph--line" />
              <div className="ph ph--line short" />
              <div className="ph ph--price">₹94,999</div>
            </div>
            <div className="browser__panel">
              <div className="panel__head">
                <strong>Smartphone Extractor</strong>
                {done ? <span className="badge badge-high">Valid</span> : <span className="badge badge-neutral">Ready</span>}
              </div>
              <button type="button" className="btn btn-primary btn-sm" onClick={() => setDone((d) => !d)}>
                {done ? 'Clear' : 'Extract smartphone data'}
              </button>
              <dl className="panel__grid" aria-live="polite">
                {fields.map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{done ? v : <span className="muted">Waiting</span>}</dd>
                  </div>
                ))}
                <div>
                  <dt>Identity</dt>
                  <dd>{done ? <span className="badge badge-high">Identified</span> : <span className="muted">Waiting</span>}</dd>
                </div>
              </dl>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Privacy() {
  const items: [string, string][] = [
    ['It reads only when you ask', 'The extension reads the specifications on the page you are viewing when you press Extract. It does not crawl in the background.'],
    ['No cookies, history or accounts', 'It does not read cookies, your browsing history or your marketplace account. A check in our build fails if its permissions grow.'],
    ['Scores cannot be bought', 'No brand, seller or customer can change a score. Models are versioned, and every change is recorded.'],
    ['AI is labelled and limited', 'AI summaries carry a label and can only restate stored evidence. They cannot add scores or specifications.'],
  ];
  return (
    <section className="section" id="privacy">
      <div className="container">
        <h2>What we promise, and how it is enforced</h2>
        <dl className="promises">
          {items.map(([t, d]) => (
            <div key={t}>
              <dt>{t}</dt>
              <dd className="muted">{d}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

function UnderTheHood() {
  const steps: [string, string][] = [
    ['Identify', 'Find the exact product and variant, such as 12 GB RAM and 256 GB, not just the model name.'],
    ['Normalise', 'Convert specifications to common units and keep the source of every value.'],
    ['Score', 'Apply a published, versioned model to the evidence. The result is reproducible and auditable.'],
    ['Explain', 'Write a short summary from the stored result. AI can explain the score but never set it.'],
  ];
  return (
    <section className="section section--tint">
      <div className="container">
        <h2>How a score is made</h2>
        <ol className="steps">
          {steps.map(([t, d]) => (
            <li key={t}>
              <strong>{t}</strong>
              <span className="muted">{d}</span>
            </li>
          ))}
        </ol>
        <p className="small muted">
          Every change to the code runs automated checks for leaked secrets, vulnerable dependencies and extension permissions.
        </p>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="section cta">
      <div className="container cta__inner">
        <h2>Check a phone you are thinking of buying</h2>
        <div className="row">
          <Link to="/app" className="btn btn-primary btn-lg">
            Open the app
          </Link>
          <Link to="/signup" className="btn btn-secondary btn-lg">
            Create an account
          </Link>
        </div>
      </div>
    </section>
  );
}

export default function Landing() {
  usePageTitle('');
  return (
    <>
      <Hero />
      <Compare />
      <Pillars />
      <Categories />
      <ExtensionPreview />
      <Privacy />
      <UnderTheHood />
      <FinalCta />
    </>
  );
}
