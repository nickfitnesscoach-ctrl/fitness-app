import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ClientsProvider } from './contexts/ClientsContext';
import { initTelegramWebApp } from './lib/telegram';
import { Dashboard } from './components/Dashboard';
import ApplicationsPage from './pages/ApplicationsPage';
import ClientsPage from './pages/ClientsPage';
import InviteClientPage from './pages/InviteClientPage';
import Layout from './components/Layout';
import ClientLayout from './components/ClientLayout';
import ClientDashboard from './pages/ClientDashboard';
import FoodLogPage from './pages/FoodLogPage';
import SubscriptionPage from './pages/SubscriptionPage';
import ProfilePage from './pages/ProfilePage';
import SubscribersPage from './pages/SubscribersPage';
import ErrorBoundary from './components/ErrorBoundary';

function App() {
  useEffect(() => {
    // Инициализация Telegram WebApp через централизованный модуль
    initTelegramWebApp();
  }, []);

  return (
    <ErrorBoundary>
      <AuthProvider>
        <ClientsProvider>
          <Router>
            <Routes>
              {/* Client Routes - КБЖУ трекер на главной (для всех) */}
              <Route path="/" element={<ClientLayout />}>
                <Route index element={<ClientDashboard />} />
                <Route path="log" element={<FoodLogPage />} />
                <Route path="subscription" element={<SubscriptionPage />} />
                <Route path="profile" element={<ProfilePage />} />
              </Route>

              {/* Trainer Panel Routes - панель тренера /panel */}
              <Route path="/panel" element={<Layout />}>
                <Route index element={<Dashboard />} />
                <Route path="applications" element={<ApplicationsPage />} />
                <Route path="clients" element={<ClientsPage />} />
                <Route path="invite-client" element={<InviteClientPage />} />
                <Route path="subscribers" element={<SubscribersPage />} />
              </Route>
            </Routes>
          </Router>
        </ClientsProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
