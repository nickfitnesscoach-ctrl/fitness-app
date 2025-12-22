/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    // F-020: Enable dark mode with class strategy
    // This allows programmatic control via ThemeContext
    darkMode: 'class',
    theme: {
        extend: {
            // F-021: Support for 100dvh (dynamic viewport height)
            minHeight: {
                'dvh': '100dvh',
                'screen-safe': 'calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom))',
            },
            height: {
                'dvh': '100dvh',
            },
            // Custom colors for dark mode
            colors: {
                dark: {
                    bg: '#0f172a',
                    card: '#1e293b',
                    border: '#334155',
                    text: '#f1f5f9',
                    muted: '#94a3b8',
                }
            }
        },
    },
    plugins: [],
}
