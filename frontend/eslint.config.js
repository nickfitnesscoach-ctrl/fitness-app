import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
      'react-hooks/exhaustive-deps': 'error',
      // Guard: Prevent static imports from __mocks__ directories (P0 prevention)
      // Mocks MUST be imported dynamically via import() inside import.meta.env.DEV guards
      'no-restricted-imports': ['error', {
        patterns: [{
          group: ['**/__mocks__/*', '**/__mocks__/**'],
          message: 'Static imports from __mocks__ are forbidden. Use dynamic import() inside import.meta.env.DEV guard to prevent mock code in production bundle.',
        }],
      }],
    },
  },
  // Node.js config files (vite.config.js, etc.)
  {
    files: ['vite.config.js', 'eslint.config.js'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
])
