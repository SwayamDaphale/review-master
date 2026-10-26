import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navbar, Footer } from './components/layout';
import Home from './routes/Home';
import Catalog from './routes/Catalog';
import ProductDetail from './routes/ProductDetail';
import Compare from './routes/Compare';
import Saved from './routes/Saved';
import AdminLayout from './routes/admin/AdminLayout';
import AdminOverview from './routes/admin/AdminOverview';
import AdminCatalog from './routes/admin/AdminCatalog';
import AdminModels from './routes/admin/AdminModels';
import AdminModeration from './routes/admin/AdminModeration';
import AdminAudit from './routes/admin/AdminAudit';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      refetchOnWindowFocus: false,
      retry: 1
    }
  }
});

function NotFound() {
  return (
    <div className="empty-state">
      <h1>404 — Page Not Found</h1>
      <p className="muted">The page you requested does not exist or has been relocated.</p>
      <Link to="/" className="btn btn-primary mt-2">
        Return to Home
      </Link>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app-shell">
          <Navbar />
          <main className="container main-content">
            <Routes>
              {/* Consumer Routes */}
              <Route path="/" element={<Home />} />
              <Route path="/catalog" element={<Catalog />} />
              <Route path="/product/:id" element={<ProductDetail />} />
              <Route path="/compare" element={<Compare />} />
              <Route path="/saved" element={<Saved />} />

              {/* Admin Console Sub-Routes */}
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<AdminOverview />} />
                <Route path="catalog" element={<AdminCatalog />} />
                <Route path="models" element={<AdminModels />} />
                <Route path="moderation" element={<AdminModeration />} />
                <Route path="audit" element={<AdminAudit />} />
              </Route>

              {/* 404 Fallback */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
