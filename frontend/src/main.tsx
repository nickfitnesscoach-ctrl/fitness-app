import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './App.css'
import App from './App'
import { shouldInitMockTelegram } from './shared/config/debug'
import { setupMockTelegram } from './shared/lib/mockTelegram'

// Initialize mock Telegram WebApp if needed
// Only runs when: (DEV or ?debug=1) AND no real Telegram WebApp exists
if (shouldInitMockTelegram()) {
  setupMockTelegram();
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
