/**
 * F-020: Theme context for dark mode support
 * Manages theme state and syncs with localStorage and Telegram theme
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type Theme = 'light' | 'dark' | 'system';

interface ThemeContextType {
    theme: Theme;
    effectiveTheme: 'light' | 'dark';
    setTheme: (theme: Theme) => void;
    toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | null>(null);

const THEME_LOCALSTORAGE_NAME = 'eatfit24_theme';

export const ThemeProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [theme, setThemeState] = useState<Theme>(() => {
        // Check localStorage first
        const stored = localStorage.getItem(THEME_LOCALSTORAGE_NAME);
        if (stored === 'light' || stored === 'dark' || stored === 'system') {
            return stored;
        }
        return 'system';
    });

    const [effectiveTheme, setEffectiveTheme] = useState<'light' | 'dark'>('light');

    // Determine effective theme based on setting and system preference
    useEffect(() => {
        const updateEffectiveTheme = () => {
            let effective: 'light' | 'dark' = 'light';

            if (theme === 'system') {
                // Check Telegram theme first
                const tgColorScheme = window.Telegram?.WebApp?.colorScheme;
                if (tgColorScheme) {
                    effective = tgColorScheme;
                } else {
                    // Fall back to system preference
                    effective = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
                }
            } else {
                effective = theme;
            }

            setEffectiveTheme(effective);

            // Apply theme class to document
            if (effective === 'dark') {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        };

        updateEffectiveTheme();

        // Listen for system theme changes
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        const handler = () => {
            if (theme === 'system') {
                updateEffectiveTheme();
            }
        };
        mediaQuery.addEventListener('change', handler);

        return () => mediaQuery.removeEventListener('change', handler);
    }, [theme]);

    const setTheme = (newTheme: Theme) => {
        setThemeState(newTheme);
        localStorage.setItem(THEME_LOCALSTORAGE_NAME, newTheme);
    };

    const toggleTheme = () => {
        const newTheme = effectiveTheme === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
    };

    return (
        <ThemeContext.Provider value={{ theme, effectiveTheme, setTheme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme = (): ThemeContextType => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};

export default ThemeContext;
