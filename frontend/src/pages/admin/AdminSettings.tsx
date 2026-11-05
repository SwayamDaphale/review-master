import { useAudit } from '../../lib/audit';
import { usePageTitle } from '../../lib/hooks';
import { useSiteSettings, type SiteSettings } from '../../state/siteSettings';
import { Notice } from '../../components/states';

function Switch({
  id,
  label,
  hint,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <div className="setting">
      <div>
        <label htmlFor={id}>{label}</label>
        {hint ? <div className="small muted">{hint}</div> : null}
      </div>
      <input id={id} type="checkbox" role="switch" className="switch" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </div>
  );
}

export default function AdminSettings() {
  usePageTitle('Site settings');
  const [settings, update, reset] = useSiteSettings();
  const { log } = useAudit();

  const set = <K extends keyof SiteSettings>(key: K, value: SiteSettings[K], what: string) => {
    update({ [key]: value } as Partial<SiteSettings>);
    log('Changed site setting', what, String(typeof value === 'object' ? JSON.stringify(value) : value));
  };
  const setFeature = (key: keyof SiteSettings['features'], value: boolean) =>
    set('features', { ...settings.features, [key]: value }, `feature: ${key}`);

  return (
    <div className="stack stack--lg container--narrow-left">
      <h1>Site settings</h1>
      <Notice tone="info">Changes apply immediately, in this browser. They will be saved on the server once the backend exists.</Notice>

      <section className="stack" aria-labelledby="ann-h">
        <h2 id="ann-h">Announcement banner</h2>
        <Switch
          id="banner-on"
          label="Show a banner at the top of every page"
          checked={settings.bannerEnabled}
          onChange={(v) => set('bannerEnabled', v, 'announcement banner')}
        />
        <div className="field">
          <label htmlFor="banner-text">Banner text</label>
          <input
            id="banner-text"
            className="input"
            value={settings.bannerText}
            maxLength={160}
            onChange={(e) => update({ bannerText: e.target.value })}
            onBlur={() => log('Changed site setting', 'banner text', settings.bannerText)}
            placeholder="For example: Prices on Amazon India were last checked this morning."
          />
        </div>
      </section>

      <section className="stack" aria-labelledby="site-h">
        <h2 id="site-h">Site</h2>
        <Switch
          id="maintenance"
          label="Maintenance mode"
          hint="Visitors see a maintenance message instead of the app. The home page and admin stay available."
          checked={settings.maintenance}
          onChange={(v) => set('maintenance', v, 'maintenance mode')}
        />
        <Switch
          id="sample-notice"
          label="Show the sample-data notice in the app"
          hint="Keep this on until real evaluations replace the demo data."
          checked={settings.showSampleNotice}
          onChange={(v) => set('showSampleNotice', v, 'sample-data notice')}
        />
      </section>

      <section className="stack" aria-labelledby="feat-h">
        <h2 id="feat-h">Features</h2>
        <Switch id="f-compare" label="Product comparison" checked={settings.features.compare} onChange={(v) => setFeature('compare', v)} />
        <Switch id="f-alerts" label="Price alerts" checked={settings.features.priceAlerts} onChange={(v) => setFeature('priceAlerts', v)} />
        <Switch id="f-import" label="Import from the browser extension" checked={settings.features.importTool} onChange={(v) => setFeature('importTool', v)} />
      </section>

      <div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => {
            reset();
            log('Reset site settings', 'all settings');
          }}
        >
          Reset to defaults
        </button>
      </div>
    </div>
  );
}
