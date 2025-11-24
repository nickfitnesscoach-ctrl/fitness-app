import { buildTelegramHeaders } from '../lib/telegram';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

interface RequestOptions extends RequestInit {
    json?: unknown;
}

const withBaseUrl = (path: string) => {
    if (path.startsWith('http')) return path;
    return `${API_BASE}${path}`;
};

const defaultHeaders = () => ({
    'Content-Type': 'application/json',
    ...buildTelegramHeaders(),
});

export const requestJson = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
    const response = await fetch(withBaseUrl(path), {
        ...options,
        headers: {
            ...defaultHeaders(),
            ...(options.headers || {}),
        },
        body: options.json ? JSON.stringify(options.json) : options.body,
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `Request failed with status ${response.status}`);
    }

    return response.json();
};
