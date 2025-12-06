import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './App.css'
import App from './App'
import { mockTelegramEnv } from './mockTelegram'

// Mock Telegram environment in development
if (import.meta.env.DEV) {
  mockTelegramEnv();
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
