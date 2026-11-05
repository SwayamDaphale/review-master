import { STORAGE_KEYS, useStoredState } from '../../lib/storage';
import { useAudit } from '../../lib/audit';
import { useAuth } from '../../state/auth';
import { usePageTitle } from '../../lib/hooks';
import { Notice } from '../../components/states';
import { ROLES, USERS_SEED, type AdminUser, type Role } from './adminData';

const ROLE_LABEL: Record<Role, string> = {
  consumer: 'Consumer',
  public_reviewer: 'Public reviewer',
  expert_reviewer: 'Expert reviewer',
  admin: 'Admin',
  api_consumer: 'API customer',
};

export default function AdminUsers() {
  usePageTitle('Users');
  const [users, setUsers] = useStoredState<AdminUser[]>(STORAGE_KEYS.adminUsers, USERS_SEED);
  const { session } = useAuth();
  const { log } = useAudit();

  const changeRole = (u: AdminUser, role: Role) => {
    setUsers((prev) => prev.map((x) => (x.id === u.id ? { ...x, role } : x)));
    log('Changed user role', u.email, `${ROLE_LABEL[u.role]} to ${ROLE_LABEL[role]}`);
  };

  return (
    <div className="stack stack--lg">
      <h1>Users and roles</h1>
      <Notice tone="info">
        Sample users. Real accounts will come from Google sign-in once the database exists. Role changes are recorded in the audit
        log, and nobody can change their own role.
      </Notice>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Email</th>
              <th scope="col">Role</th>
            </tr>
          </thead>
          <tbody>
            {session ? (
              <tr>
                <th scope="row">
                  {session.name} <span className="badge badge-accent">Signed in here</span>
                </th>
                <td>{session.email}</td>
                <td className="muted">Consumer (set by the backend later)</td>
              </tr>
            ) : null}
            {users.map((u) => {
              const self = u.id === 'u-4';
              return (
                <tr key={u.id}>
                  <th scope="row">{u.name}</th>
                  <td>{u.email}</td>
                  <td>
                    <label className="sr-only" htmlFor={`role-${u.id}`}>Role for {u.name}</label>
                    <select
                      id={`role-${u.id}`}
                      className="select"
                      value={u.role}
                      disabled={self}
                      onChange={(e) => changeRole(u, e.target.value as Role)}
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{ROLE_LABEL[r]}</option>
                      ))}
                    </select>
                    {self ? <span className="small muted"> You cannot change your own role.</span> : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
