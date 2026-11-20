import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { CounterPage } from './pages/CounterPage';
import { CustomersPage } from './pages/CustomersPage';
import { DashboardPage } from './pages/DashboardPage';
import { InventoryPage } from './pages/InventoryPage';
import { LandingLoginPage } from './pages/LandingLoginPage';
import { ReportsPage } from './pages/ReportsPage';
import { RescueCashPage } from './pages/RescueCashPage';
import { RestockPage } from './pages/RestockPage';
import { useLedgerStore } from './store/useLedgerStore';

/**
 * Frontend prototype route guard.
 * Note: For production deployment, route access MUST be enforced via backend
 * session cookies / server-side authentication rather than client state alone.
 */
function AppRoutes() {
  const location = useLocation();
  const isAuthenticated = useLedgerStore((s) => s.isAuthenticated);
  const initialized = useLedgerStore((s) => s.initialized);
  const init = useLedgerStore((s) => s.init);

  useEffect(() => {
    if (isAuthenticated && !initialized) {
      void init();
    }
  }, [isAuthenticated, initialized, init]);

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/" element={<LandingLoginPage />} />
        <Route
          path="*"
          element={<Navigate to="/" replace state={{ from: location.pathname }} />}
        />
      </Routes>
    );
  }

  return (
    <AppShell>
      {!initialized ? (
        <div className="space-y-6 animate-pulse">
          <div className="h-28 rounded-xl bg-[#E5EAE5]/70" />
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 h-96 rounded-xl bg-[#E5EAE5]/70" />
            <div className="lg:col-span-4 h-96 rounded-xl bg-[#E5EAE5]/70" />
          </div>
        </div>
      ) : (
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/dashboard" element={<Navigate to="/" replace />} />
          <Route path="/counter" element={<CounterPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/rescue" element={<RescueCashPage />} />
          <Route path="/restock" element={<RestockPage />} />
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      )}
    </AppShell>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
