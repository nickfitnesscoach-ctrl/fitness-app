# FoodMind AI - React/TypeScript Examples

Готовые примеры компонентов для Telegram Mini App на React + TypeScript.

---

## 1. API Service (api.ts)

```typescript
// src/services/api.ts

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api/v1';

interface AuthResponse {
  access: string;
  refresh: string;
  user: {
    id: number;
    username: string;
    telegram_id: number;
    first_name: string;
    last_name?: string;
    completed_ai_test: boolean;
  };
}

interface TelegramProfile {
  telegram_id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  language_code: string;
  is_premium: boolean;
  ai_test_completed: boolean;
  assigned_calories?: number;
  assigned_protein?: number;
  assigned_fat?: number;
  assigned_carbs?: number;
  trainer_plan?: string;
}

class ApiService {
  private accessToken: string | null = null;

  constructor() {
    this.accessToken = localStorage.getItem('access_token');
  }

  setAccessToken(token: string) {
    this.accessToken = token;
    localStorage.setItem('access_token', token);
  }

  async authenticate(initData: string): Promise<AuthResponse> {
    const response = await fetch(`${API_URL}/telegram/auth/`, {
      method: 'POST',
      headers: {
        'X-Telegram-Init-Data': initData,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error('Authentication failed');
    }

    const data = await response.json();
    this.setAccessToken(data.access);
    return data;
  }

  async getProfile(): Promise<TelegramProfile> {
    const response = await fetch(`${API_URL}/telegram/profile/`, {
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch profile');
    }

    return response.json();
  }

  async refreshToken(refreshToken: string): Promise<string> {
    const response = await fetch(`${API_URL}/token/refresh/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    if (!response.ok) {
      throw new Error('Failed to refresh token');
    }

    const data = await response.json();
    this.setAccessToken(data.access);
    return data.access;
  }
}

export const api = new ApiService();
```

---

## 2. Auth Context (AuthContext.tsx)

```typescript
// src/contexts/AuthContext.tsx

import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

interface User {
  id: number;
  username: string;
  telegram_id: number;
  first_name: string;
  last_name?: string;
  completed_ai_test: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  error: string | null;
  authenticate: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const authenticate = async () => {
    try {
      setLoading(true);
      setError(null);

      // Получаем initData из Telegram WebApp
      const initData = window.Telegram?.WebApp?.initData;

      if (!initData) {
        throw new Error('Telegram WebApp not initialized');
      }

      const response = await api.authenticate(initData);
      setUser(response.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    authenticate();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, error, authenticate }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

---

## 3. Profile Hook (useProfile.ts)

```typescript
// src/hooks/useProfile.ts

import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface TelegramProfile {
  telegram_id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  language_code: string;
  is_premium: boolean;
  ai_test_completed: boolean;
  assigned_calories?: number;
  assigned_protein?: number;
  assigned_fat?: number;
  assigned_carbs?: number;
  trainer_plan?: string;
}

export const useProfile = () => {
  const [profile, setProfile] = useState<TelegramProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getProfile();
      setProfile(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  return { profile, loading, error, refetch: fetchProfile };
};
```

---

## 4. Dashboard Component (Dashboard.tsx)

```typescript
// src/components/Dashboard.tsx

import React from 'react';
import { useProfile } from '../hooks/useProfile';
import { MacroChart } from './MacroChart';
import { AIRecommendations } from './AIRecommendations';

export const Dashboard: React.FC = () => {
  const { profile, loading, error } = useProfile();

  if (loading) {
    return <div className="loading">Загрузка...</div>;
  }

  if (error) {
    return <div className="error">Ошибка: {error}</div>;
  }

  if (!profile) {
    return <div>Профиль не найден</div>;
  }

  // Если пользователь не прошел тест
  if (!profile.ai_test_completed) {
    return (
      <div className="test-prompt">
        <h2>Добро пожаловать в FoodMind AI! 👋</h2>
        <p>Для начала работы пройдите AI тест в нашем боте.</p>
        <button
          onClick={() => window.Telegram.WebApp.openTelegramLink('https://t.me/AI_test_bot')}
        >
          Пройти AI тест
        </button>
      </div>
    );
  }

  // Тест пройден, но КБЖУ еще не назначено тренером
  if (!profile.assigned_calories) {
    return (
      <div className="pending-prompt">
        <h2>Привет, {profile.first_name}! 👋</h2>
        <p>Тренер скоро назначит вам персональный план питания.</p>
        <div className="loader">🔄</div>
      </div>
    );
  }

  // Пользователь прошел тест И тренер назначил КБЖУ - показываем дашборд
  return (
    <div className="dashboard">
      <header>
        <h1>Привет, {profile.first_name}! 👋</h1>
        {profile.is_premium && <span className="premium-badge">Premium</span>}
      </header>

      <section className="macros-section">
        <h2>Ваш план питания</h2>
        <MacroChart
          calories={profile.assigned_calories}
          protein={profile.assigned_protein!}
          fat={profile.assigned_fat!}
          carbs={profile.assigned_carbs!}
        />
      </section>

      {profile.trainer_plan && (
        <section className="trainer-plan-section">
          <h2>План от тренера 👨‍⚕️</h2>
          <div className="plan-content">
            <ReactMarkdown>{profile.trainer_plan}</ReactMarkdown>
          </div>
        </section>
      )}
    </div>
  );
};
```

---

## 5. Macro Chart Component (MacroChart.tsx)

```typescript
// src/components/MacroChart.tsx

import React from 'react';
import { Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

interface MacroChartProps {
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
}

export const MacroChart: React.FC<MacroChartProps> = ({
  calories,
  protein,
  fat,
  carbs,
}) => {
  const data = {
    labels: ['Белки', 'Жиры', 'Углеводы'],
    datasets: [
      {
        data: [protein, fat, carbs],
        backgroundColor: [
          'rgba(54, 162, 235, 0.8)',  // Синий для белков
          'rgba(255, 206, 86, 0.8)',  // Желтый для жиров
          'rgba(75, 192, 192, 0.8)',  // Зеленый для углеводов
        ],
        borderColor: [
          'rgba(54, 162, 235, 1)',
          'rgba(255, 206, 86, 1)',
          'rgba(75, 192, 192, 1)',
        ],
        borderWidth: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: 'bottom' as const,
      },
      tooltip: {
        callbacks: {
          label: (context: any) => {
            const label = context.label || '';
            const value = context.parsed || 0;
            return `${label}: ${value}г`;
          },
        },
      },
    },
  };

  return (
    <div className="macro-chart">
      <div className="calories-display">
        <h3>{calories}</h3>
        <p>ккал/день</p>
      </div>

      <Doughnut data={data} options={options} />

      <div className="macro-details">
        <div className="macro-item">
          <span className="label">Белки:</span>
          <span className="value">{protein}г</span>
        </div>
        <div className="macro-item">
          <span className="label">Жиры:</span>
          <span className="value">{fat}г</span>
        </div>
        <div className="macro-item">
          <span className="label">Углеводы:</span>
          <span className="value">{carbs}г</span>
        </div>
      </div>
    </div>
  );
};
```

---

## 6. Trainer Plan Component (Опционально)

Компонент плана уже встроен в Dashboard. Если нужен отдельный компонент:

```typescript
// src/components/TrainerPlan.tsx

import React from 'react';
import ReactMarkdown from 'react-markdown';

interface TrainerPlanProps {
  plan: string;
}

export const TrainerPlan: React.FC<TrainerPlanProps> = ({ plan }) => {
  return (
    <div className="trainer-plan">
      <h2>План от тренера 👨‍⚕️</h2>
      <div className="plan-content">
        <ReactMarkdown>{plan}</ReactMarkdown>
      </div>
    </div>
  );
};
```

---

## 7. App Entry Point (App.tsx)

```typescript
// src/App.tsx

import React, { useEffect } from 'react';
import { AuthProvider } from './contexts/AuthContext';
import { Dashboard } from './components/Dashboard';
import './App.css';

function App() {
  useEffect(() => {
    // Инициализация Telegram WebApp
    const tg = window.Telegram?.WebApp;

    if (tg) {
      tg.ready();
      tg.expand();

      // Настройка темы
      document.documentElement.style.setProperty(
        '--tg-theme-bg-color',
        tg.themeParams.bg_color || '#ffffff'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-text-color',
        tg.themeParams.text_color || '#000000'
      );
    }
  }, []);

  return (
    <AuthProvider>
      <div className="app">
        <Dashboard />
      </div>
    </AuthProvider>
  );
}

export default App;
```

---

## 8. TypeScript Declarations (telegram.d.ts)

```typescript
// src/types/telegram.d.ts

interface TelegramWebApp {
  initData: string;
  initDataUnsafe: any;
  version: string;
  platform: string;
  colorScheme: 'light' | 'dark';
  themeParams: {
    bg_color?: string;
    text_color?: string;
    hint_color?: string;
    link_color?: string;
    button_color?: string;
    button_text_color?: string;
  };
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  headerColor: string;
  backgroundColor: string;
  MainButton: any;
  BackButton: any;

  ready(): void;
  expand(): void;
  close(): void;
  openLink(url: string): void;
  openTelegramLink(url: string): void;
  showPopup(params: any): void;
  showAlert(message: string): void;
  showConfirm(message: string): void;
}

interface Window {
  Telegram?: {
    WebApp: TelegramWebApp;
  };
}
```

---

## 9. CSS Styles (App.css)

```css
/* src/App.css */

:root {
  --tg-theme-bg-color: #ffffff;
  --tg-theme-text-color: #000000;
  --tg-theme-hint-color: #999999;
  --tg-theme-link-color: #2481cc;
  --tg-theme-button-color: #2481cc;
  --tg-theme-button-text-color: #ffffff;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: var(--tg-theme-bg-color);
  color: var(--tg-theme-text-color);
}

.app {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 200px;
  color: var(--tg-theme-hint-color);
}

.error {
  padding: 20px;
  background-color: #ffebee;
  color: #c62828;
  border-radius: 8px;
  margin: 20px 0;
}

/* Dashboard */
.dashboard header {
  margin-bottom: 30px;
}

.dashboard h1 {
  font-size: 24px;
  margin-bottom: 10px;
}

.premium-badge {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  margin-left: 10px;
}

/* Macros Section */
.macros-section {
  background-color: var(--tg-theme-bg-color);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.macros-section h2 {
  font-size: 18px;
  margin-bottom: 20px;
}

.macro-chart {
  text-align: center;
}

.calories-display {
  margin-bottom: 20px;
}

.calories-display h3 {
  font-size: 48px;
  color: var(--tg-theme-button-color);
  margin-bottom: 5px;
}

.calories-display p {
  color: var(--tg-theme-hint-color);
  font-size: 14px;
}

.macro-details {
  margin-top: 20px;
  display: flex;
  justify-content: space-around;
  gap: 15px;
}

.macro-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}

.macro-item .label {
  font-size: 12px;
  color: var(--tg-theme-hint-color);
}

.macro-item .value {
  font-size: 18px;
  font-weight: 600;
}

/* AI Recommendations */
.ai-recommendations {
  background-color: var(--tg-theme-bg-color);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.ai-recommendations h2 {
  font-size: 18px;
  margin-bottom: 15px;
}

.plan-content {
  line-height: 1.6;
  margin-bottom: 20px;
}

.plan-content h1,
.plan-content h2,
.plan-content h3 {
  margin: 15px 0 10px;
}

.plan-content ul,
.plan-content ol {
  margin-left: 20px;
  margin-bottom: 10px;
}

.regenerate-btn {
  width: 100%;
  padding: 12px;
  background-color: var(--tg-theme-button-color);
  color: var(--tg-theme-button-text-color);
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}

.regenerate-btn:hover {
  opacity: 0.9;
}

/* Test Prompt */
.test-prompt {
  text-align: center;
  padding: 40px 20px;
}

.test-prompt h2 {
  font-size: 24px;
  margin-bottom: 15px;
}

.test-prompt p {
  color: var(--tg-theme-hint-color);
  margin-bottom: 30px;
}

.test-prompt button {
  padding: 12px 32px;
  background-color: var(--tg-theme-button-color);
  color: var(--tg-theme-button-text-color);
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}
```

---

## 10. Package.json Dependencies

```json
{
  "name": "foodmind-miniapp",
  "version": "1.0.0",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-chartjs-2": "^5.2.0",
    "chart.js": "^4.4.0",
    "react-markdown": "^9.0.1",
    "typescript": "^5.3.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0"
  }
}
```

---

**Готово для AI Gravity / Google AI!** 🚀

Все компоненты готовы к использованию. Просто скопируй этот файл в промпт для AI, и он поймет структуру проекта.
