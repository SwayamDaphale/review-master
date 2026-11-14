import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../state/auth';
import { useAdmin } from '../lib/adminAuth';
import { Loading } from '../components/states';

/** Pages that need a signed-in user (saved products, alerts, account). */
export function RequireAuth() {
  const { session, isInitializing } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return <Loading label="Verifying session..." />;
  }

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  return <Outlet />;
}

export function RequireAdmin() {
  const { isAdmin } = useAdmin();
  const location = useLocation();
  if (!isAdmin) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
