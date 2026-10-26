import { useAudit } from '../../lib/audit';
import { formatDate } from '../../lib/format';
import { usePageTitle } from '../../lib/hooks';

export default function AdminAudit() {
  usePageTitle('Audit log');
  const { entries } = useAudit();

  const download = () => {
    const blob = new Blob([JSON.stringify(entries, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'review-master-audit-log.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="stack stack--lg">
      <div className="row row--between">
        <h1>Audit log</h1>
        <button type="button" className="btn btn-secondary btn-sm" onClick={download} disabled={entries.length === 0}>
          Download as JSON
        </button>
      </div>
      <p className="muted">
        Every admin action is recorded here and cannot be edited or deleted from this screen. For now the log lives in this browser;
        the real one will be append-only in the database.
      </p>
      {entries.length === 0 ? (
        <p className="muted">No actions yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Who</th>
                <th scope="col">Action</th>
                <th scope="col">Object</th>
                <th scope="col">Detail</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="small muted nowrap">
                    {formatDate(e.at)}, {new Date(e.at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="small">{e.actor}</td>
                  <td>{e.action}</td>
                  <td>{e.object}</td>
                  <td className="small muted">{e.detail ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
