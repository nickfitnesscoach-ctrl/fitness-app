import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { AppDataProvider } from './contexts/AppDataContext';
import { ClientsProvider } from './contexts/ClientsContext';
import { BillingProvider } from './contexts/BillingContext';
import { ToastProvider } from './contexts/ToastContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { initTelegramWebApp } from './lib/telegram'
import { Dashboard } from './features/trainer-panel/components/Dashboard';
import ApplicationsPage from './features/trainer-panel/pages/ApplicationsPage';
import ClientsPage from './features/trainer-panel/pages/ClientsPage';
import InviteClientPage from './features/trainer-panel/pages/InviteClientPage';
import Layout from './features/trainer-panel/components/Layout';
import ClientLayout from './components/ClientLayout';
import ClientDashboard from './pages/ClientDashboard';
import FoodLogPage from './pages/FoodLogPage';
import ProfilePage from './pages/ProfilePage';
import SettingsPage from './pages/SettingsPage';
import SubscribersPage from './features/trainer-panel/pages/SubscribersPage';
import ErrorBoundary from './components/ErrorBoundary';
import OfflineIndicator from './components/OfflineIndicator';
import MealDetailsPage from './pages/MealDetailsPage';
// Billing feature module
import { SubscriptionPage, SubscriptionDetailsPage, PaymentHistoryPage } from './features/billing';
// AI Context
import { AIProcessingProvider } from './features/ai/context/AIProcessingContext';

function App() {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    // Initialize Telegram WebApp
    const init = async () => {
      // Always initialize Telegram WebApp
      // In DEV: mock will be used if no real Telegram
      // In PROD: only real Telegram WebApp
      await initTelegramWebApp();

      // Mark app as ready to prevent flash
      setIsReady(true);
    };

    init();
  }, []);

  // Wait for initialization to prevent debug banner flash
  // This ensures mock Telegram is set up before rendering
  if (!isReady) {
    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#ffffff',
        zIndex: 9999
      }}>
        <div style={{
          width: '40px',
          height: '40px',
          border: '4px solid #e5e7eb',
          borderTopColor: '#3b82f6',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }} />
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      {/* F-020: Theme provider for dark mode */}
      <ThemeProvider>
        <AuthProvider>
          <AppDataProvider>
            <BillingProvider>
              <ClientsProvider>
                {/* F-029: Toast notifications provider */}
                <ToastProvider>
                  {/* Глобальный обработчик ошибок авторизации (401/403) - DISABLED */}
                  {/* Pages show "Open via Telegram" message instead of modal */}
                  {/* F-013: Offline indicator */}
                  <OfflineIndicator />
                  <AIProcessingProvider>
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
                  </AIProcessingProvider>
                </ToastProvider>
              </ClientsProvider>
            </BillingProvider>
          </AppDataProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
