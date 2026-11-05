import { useState, useEffect, useCallback, type ChangeEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { api } from '../../api';
import { usePageTitle } from '../../lib/hooks';
import {
  FIELD_LABEL,
  SAMPLE_EXTRACTION,
  SAMPLE_EXTRACTION_PARTIAL,
  parseExtractedJson,
  type ImportResult,
} from '../../lib/extensionImport';
import { formatINR } from '../../lib/format';
import { MatchBadge } from '../../components/MatchBadge';
import { ProductRow } from '../../components/ProductRow';
import { Notice } from '../../components/states';
import { useSiteSettings } from '../../state/siteSettings';

const FIELD_ORDER = [
  'brand',
  'model_name',
  'model_number',
  'ram_gb',
  'storage_gb',
  'display_size_inches',
  'battery_capacity_mah',
  'processor',
  'operating_system',
  'supports_5g',
  'price_amount',
  'availability',
  'rating',
  'review_count',
] as const;

function show(key: string, v: unknown): string | null {
  if (v === null || v === undefined) return null;
  if (key === 'price_amount' && typeof v === 'number') return formatINR(v);
  if (key === 'ram_gb' || key === 'storage_gb') return `${String(v)} GB`;
  if (key === 'display_size_inches') return `${String(v)} in`;
  if (key === 'battery_capacity_mah') return `${Number(v).toLocaleString('en-IN')} mAh`;
  if (key === 'supports_5g') return v ? 'Yes' : 'No';
  return String(v);
}

export default function ImportPage() {
  usePageTitle('Import extension data');
  const [settings] = useSiteSettings();
  const [text, setText] = useState('');
  const [parsed, setParsed] = useState<ImportResult | null>(null);
  const match = useMutation({ mutationFn: api.matchExtracted });

  const run = useCallback((source: string) => {
    const result = parseExtractedJson(source);
    setParsed(result);
    match.reset();
    if (result.ok) match.mutate(result.value);
  }, [match]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = window.location.hash;
    if (hash && hash.startsWith('#data=')) {
      try {
        const rawJson = decodeURIComponent(hash.slice(6));
        setText(rawJson);
        run(rawJson);
        window.history.replaceState(null, '', window.location.pathname + window.location.search);
      } catch (err) {
        console.error('Failed to parse extension payload from hash', err);
      }
    }
  }, [run]);

  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const content = await file.text();
    setText(content);
    run(content);
    e.target.value = '';
  };

  if (!settings.features.importTool) {
    return <Notice tone="info">Import is switched off at the moment.</Notice>;
  }

  return (
    <div className="page stack stack--lg">
      <div className="stack">
        <h1>Import extension data</h1>
        <p className="lead">
          Paste the JSON the browser extension downloaded. We check it, show what was and was not captured, and look for a matching
          product. Need the extension? <Link to="/extension">See how to install it</Link>.
        </p>
      </div>

      <div className="stack">
        <label htmlFor="json-input" className="label">Extension JSON</label>
        <textarea
          id="json-input"
          className="textarea"
          rows={10}
          spellCheck={false}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='{ "brand": "Samsung", "category": "smartphone", ... }'
        />
        <div className="row">
          <button type="button" className="btn btn-primary" disabled={!text.trim()} onClick={() => run(text)}>
            Check this data
          </button>
          <label className="btn btn-secondary">
            Upload a file
            <input type="file" accept="application/json,.json" className="sr-only" onChange={onFile} />
          </label>
          <button type="button" className="btn btn-ghost" onClick={() => { setText(SAMPLE_EXTRACTION); run(SAMPLE_EXTRACTION); }}>
            Try the S25 Ultra sample
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => { setText(SAMPLE_EXTRACTION_PARTIAL); run(SAMPLE_EXTRACTION_PARTIAL); }}>
            Try the iPhone sample (partial)
          </button>
        </div>
      </div>

      {parsed && !parsed.ok ? <Notice tone="danger">{parsed.error}</Notice> : null}

      {parsed && parsed.ok ? (
        <section className="stack" aria-labelledby="result-h">
          <h2 id="result-h">What the extension captured</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Value</th>
                </tr>
              </thead>
              <tbody>
                {FIELD_ORDER.map((key) => {
                  const v = show(key, parsed.value[key as keyof typeof parsed.value]);
                  return (
                    <tr key={key}>
                      <th scope="row">{FIELD_LABEL[key] ?? key}</th>
                      <td>{v ?? <span className="muted">Not captured</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {parsed.missing.length > 0 ? (
            <p className="small muted">
              Not captured: {parsed.missing.map((k) => FIELD_LABEL[k] ?? k).join(', ')}. These stay empty and are never treated as zero.
            </p>
          ) : null}

          <h2>Matching product</h2>
          {match.isPending ? <p role="status" className="muted">Looking for a match</p> : null}
          {match.error ? <Notice tone="danger">The match could not be checked. Try again.</Notice> : null}
          {match.data ? (
            <div className="stack">
              <p>
                <MatchBadge state={match.data.match_state} />
              </p>
              <Notice tone={match.data.match_state === 'confirmed' ? 'ok' : match.data.match_state === 'unmatched' ? 'warn' : 'info'}>
                {match.data.reason}
              </Notice>
              {match.data.candidates.length > 0 ? (
                <ul className="prow-list">
                  {match.data.candidates.map((c) => (
                    <ProductRow key={c.variant.id} item={c} />
                  ))}
                </ul>
              ) : (
                <p className="muted">There is no evaluation for this product yet, so no score is shown.</p>
              )}
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
