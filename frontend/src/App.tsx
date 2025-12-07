import { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ClientsProvider } from './contexts/ClientsContext';
import { BillingProvider } from './contexts/BillingContext';
import { ToastProvider } from './contexts/ToastContext';
import { ThemeProvider } from './contexts/ThemeContext';
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
import SettingsPage from './pages/SettingsPage';
import SubscriptionDetailsPage from './pages/SubscriptionDetailsPage';
import PaymentHistoryPage from './pages/PaymentHistoryPage';
import SubscribersPage from './pages/SubscribersPage';
import ErrorBoundary from './components/ErrorBoundary';
import AuthErrorModal from './components/AuthErrorModal';
// F-013: Offline indicator
import OfflineIndicator from './components/OfflineIndicator';

import MealDetailsPage from './pages/MealDetailsPage';

function App() {
  useEffect(() => {
    // Условная инициализация Telegram WebApp (только когда работаем как Telegram Mini App)
    if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
      initTelegramWebApp();
    } else if (import.meta.env.DEV) {
      // В DEV режиме пытаемся инициализировать с фейковыми данными
      initTelegramWebApp();
    } else {
      console.log('[App] Запуск вне Telegram WebApp - пропускаем инициализацию');
    }

    // DEBUG: Version marker
    console.log('🚀 EATFIT_FRONT_VERSION = 42');
    console.log('📦 Build timestamp:', new Date().toISOString());
  }, []);

  return (
    <ErrorBoundary>
      {/* F-020: Theme provider for dark mode */}
      <ThemeProvider>
      <AuthProvider>
        <BillingProvider>
          <ClientsProvider>
            {/* F-029: Toast notifications provider */}
            <ToastProvider>
            {/* Глобальный обработчик ошибок авторизации (401/403) */}
            <AuthErrorModal />
            {/* F-013: Offline indicator */}
            <OfflineIndicator />
            <Router basename="/app">
              <Routes>
                {/* Client Routes - КБЖУ трекер на главной (для всех) */}
                <Route path="/" element={<ClientLayout />}>
                  <Route index element={<ClientDashboard />} />
                  <Route path="log" element={<FoodLogPage />} />
                  <Route path="meal/:id" element={<MealDetailsPage />} />
                  <Route path="subscription" element={<SubscriptionPage />} />
                  <Route path="profile" element={<ProfilePage />} />
                  <Route path="settings" element={<SettingsPage />} />
                  <Route path="settings/subscription" element={<SubscriptionDetailsPage />} />
                  <Route path="settings/history" element={<PaymentHistoryPage />} />
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
            </ToastProvider>
          </ClientsProvider>
        </BillingProvider>
      </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
