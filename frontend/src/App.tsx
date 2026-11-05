import { Navigate, Route, Routes } from 'react-router-dom';
import { AdminLayout, AppLayout, PublicLayout } from './layouts/Layouts';
import { RequireAdmin, RequireAuth } from './auth/guards';
import Landing from './pages/landing/Landing';
import AuthPage from './pages/public/AuthPage';
import ExtensionPage from './pages/public/ExtensionPage';
import NotFound from './pages/public/NotFound';
import Explore from './pages/app/Explore';
import SearchPage from './pages/app/SearchPage';
import ProductPage from './pages/app/ProductPage';
import ComparePage from './pages/app/ComparePage';
import SavedPage from './pages/app/SavedPage';
import ImportPage from './pages/app/ImportPage';
import AccountPage from './pages/app/AccountPage';
import AdminLogin from './pages/admin/AdminLogin';
import AdminOverview from './pages/admin/AdminOverview';
import AdminCatalog from './pages/admin/AdminCatalog';
import AdminModels from './pages/admin/AdminModels';
import AdminModeration from './pages/admin/AdminModeration';
import AdminUsers from './pages/admin/AdminUsers';
import AdminSettings from './pages/admin/AdminSettings';
import AdminAudit from './pages/admin/AdminAudit';

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="extension" element={<ExtensionPage />} />
      </Route>

      <Route path="login" element={<AuthPage mode="signin" />} />
      <Route path="signup" element={<AuthPage mode="signup" />} />

      <Route path="app" element={<AppLayout />}>
        <Route index element={<Explore />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="products/:productId" element={<ProductPage />} />
        <Route path="compare" element={<ComparePage />} />
        <Route path="import" element={<ImportPage />} />
        <Route element={<RequireAuth />}>
          <Route path="saved" element={<SavedPage />} />
          <Route path="account" element={<AccountPage />} />
        </Route>
      </Route>

      <Route path="admin/login" element={<AdminLogin />} />
      <Route path="admin" element={<RequireAdmin />}>
        <Route element={<AdminLayout />}>
          <Route index element={<AdminOverview />} />
          <Route path="catalog" element={<AdminCatalog />} />
          <Route path="models" element={<AdminModels />} />
          <Route path="moderation" element={<AdminModeration />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="settings" element={<AdminSettings />} />
          <Route path="audit" element={<AdminAudit />} />
        </Route>
      </Route>

      <Route path="home" element={<Navigate to="/" replace />} />
      <Route element={<PublicLayout />}>
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
