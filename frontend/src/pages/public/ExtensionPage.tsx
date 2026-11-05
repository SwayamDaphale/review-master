import { Link } from 'react-router-dom';
import { usePageTitle } from '../../lib/hooks';
import { Notice } from '../../components/states';

export default function ExtensionPage() {
  usePageTitle('Browser extension');
  return (
    <div className="container container--narrow page">
      <h1>Browser extension</h1>
      <p className="lead">
        The Review Master extension reads the specifications on an Amazon India smartphone page when you ask it to, and produces a
        clean record you can check and bring into the app.
      </p>
      <Notice tone="info">
        It is in developer preview and is not on the Chrome Web Store yet. It works in Chrome, Brave and other Chromium browsers.
      </Notice>

      <h2>Install it</h2>
      <ol className="steps steps--plain">
        <li>
          <strong>Open the extensions page.</strong>
          <span className="muted">Go to <code>chrome://extensions</code> in Chrome or <code>brave://extensions</code> in Brave.</span>
        </li>
        <li>
          <strong>Turn on Developer mode.</strong>
          <span className="muted">The switch is at the top right of the page.</span>
        </li>
        <li>
          <strong>Load the extension.</strong>
          <span className="muted">Choose Load unpacked, then select the <code>extension</code> folder of the project.</span>
        </li>
        <li>
          <strong>Use it on a product page.</strong>
          <span className="muted">Open a smartphone on amazon.in, click the Review Master icon and press Extract smartphone data.</span>
        </li>
        <li>
          <strong>Bring the result here.</strong>
          <span className="muted">
            Press Download validated JSON, then open <Link to="/app/import">Import</Link> and paste or upload the file.
          </span>
        </li>
      </ol>

      <h2>What it reads, and what it does not</h2>
      <div className="two-col">
        <div>
          <h3>Reads</h3>
          <ul className="ticks">
            <li>The specifications, price and rating visible on the product page</li>
            <li>Only when you press Extract</li>
            <li>Only on amazon.in smartphone pages</li>
          </ul>
        </div>
        <div>
          <h3>Never reads</h3>
          <ul className="crosses">
            <li>Cookies or login details</li>
            <li>Your browsing history</li>
            <li>Your marketplace account or orders</li>
          </ul>
        </div>
      </div>

      <h2>When it is not sure</h2>
      <p>
        If it cannot read a value, it leaves it empty and lists a warning. If the model name is unclear, it marks the match as
        probable instead of guessing. The app shows these gaps as <em>Not captured</em> or <em>Not scored</em>, never as zero.
      </p>
      <p>
        <Link to="/app/import" className="btn btn-primary">
          Import extension data
        </Link>
      </p>
    </div>
  );
}
