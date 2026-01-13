import React, { createContext, useContext, useState, ReactNode, useRef, useEffect } from 'react';
import type { Application } from '../features/trainer-panel/types';
import { api } from '../services/api';
import { useAuth } from './AuthContext';

interface ClientsContextType {
    clients: Application[];
    addClient: (application: Application) => void;
    removeClient: (clientId: number) => void;
    isClient: (applicationId: number) => boolean;
    refreshClients: () => void;
}

const ClientsContext = createContext<ClientsContextType | undefined>(undefined);

// Маппинг данных с бекенда
const genderMap: Record<string, string> = {
    'male': 'Мужской',
    'female': 'Женский'
};
const activityMap: Record<string, string> = {
    'minimal': 'Минимальная',
    'low': 'Низкая',
    'medium': 'Средняя',
    'high': 'Высокая'
};
const trainingMap: Record<string, string> = {
    'beginner': 'Новичок',
    'intermediate': 'Средний',
    'advanced': 'Продвинутый',
    'home': 'Домашний формат'
};
const goalsMap: Record<string, string> = {
    'weight_loss': 'Снижение веса',
    'fat_loss': 'Сжигание жира',
    'muscle_gain': 'Набор мышц',
    'tighten_body': 'Подтянуть тело',
    'belly_sides': 'Убрать живот и бока',
    'glutes_shape': 'Округлые ягодицы',
    'maintenance': 'Поддержание формы'
};
const restrictionsMap: Record<string, string> = {
    'none': 'Нет ограничений',
    'back': 'Проблемы со спиной',
    'joints': 'Проблемы с суставами',
    'heart': 'Сердечно-сосудистые',
    'allergy': 'Аллергии',
    'stress': 'Высокий стресс',
    'diabetes': 'Диабет'
};

export const ClientsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const { isAdmin } = useAuth();
    const [clients, setClients] = useState<Application[]>([]);

    const loadClients = async () => {
        try {
            const data = await api.getClients();
            const formattedClients: Application[] = data.map((item: any) => {
                const details = item.details || {};
                return {
                    id: item.id,
                    first_name: item.first_name,
                    username: item.username || 'anon',
                    photo_url: item.photo_url || '',
                    status: 'client',
                    date: new Date(item.created_at).toLocaleDateString('ru-RU'),
                    details: {
                        age: details.age || 0,
                        gender: genderMap[details.gender] || details.gender || 'Не указан',
                        height: details.height || 0,
                        weight: details.weight || 0,
                        target_weight: details.target_weight || 0,
                        activity_level: activityMap[details.activity_level] || details.activity_level || 'Не указана',
                        training_level: trainingMap[details.training_level] || details.training_level || 'Не указан',
                        goals: (details.goals || []).map((g: string) => goalsMap[g] || g),
                        limitations: (details.health_restrictions || []).map((r: string) => restrictionsMap[r] || r),
                        body_type: {
                            id: details.current_body_type || 1,
                            description: 'Текущая форма',
                            image_url: details.current_body_type ? `/assets/body_types/${details.gender === 'male' ? 'm' : 'f'}_type_${details.current_body_type}.jpg` : ''
                        },
                        desired_body_type: {
                            id: details.ideal_body_type || 1,
                            description: 'Желаемая форма',
                            image_url: details.ideal_body_type ? `/assets/body_types/${details.gender === 'male' ? 'm' : 'f'}_type_after_${details.ideal_body_type}.jpg` : ''
                        },
                        timezone: details.timezone || 'UTC+3',
                        allergies: Array.isArray(details.allergies) ? details.allergies : (details.allergies ? [details.allergies] : [])
                    }
                };
            });
            setClients(formattedClients);
        } catch (error) {
            console.error("Failed to load clients", error);
        }
    };

    // Guard for clients loading
    const didLoadRef = useRef(false);

    // Load clients when admin becomes available
    useEffect(() => {
        // Reset if no longer admin (e.g. logout)
        if (!isAdmin) {
            didLoadRef.current = false;
            setClients([]);
            return;
        }

        if (didLoadRef.current) return;
        didLoadRef.current = true;

        void loadClients();
    }, [isAdmin]);

    const addClient = async (application: Application) => {
        try {
            // Optimistic update
            setClients(prev => {
                if (prev.some(c => c.id === application.id)) return prev;
                return [...prev, application];
            });

            // Call API with client ID
            await api.addClient(application.id);
        } catch (error) {
            console.error("Failed to add client", error);
            // Revert optimistic update
            setClients(prev => prev.filter(c => c.id !== application.id));
        }
    };

    const removeClient = async (clientId: number) => {
        const removedClient = clients.find(c => c.id === clientId);
        try {
            // Optimistic update
            setClients(prev => prev.filter(c => c.id !== clientId));

            // Call API
            await api.removeClient(clientId);
        } catch (error) {
            console.error("Failed to remove client", error);
            // Revert optimistic update
            if (removedClient) {
                setClients(prev => [...prev, removedClient]);
            }
        }
    };

    const isClient = (applicationId: number) => {
        return clients.some(c => c.id === applicationId);
    };

    const refreshClients = () => {
        loadClients();
    };

    return (
        <ClientsContext.Provider value={{ clients, addClient, removeClient, isClient, refreshClients }}>
            {children}
        </ClientsContext.Provider>
    );
};

export const useClients = () => {
    const context = useContext(ClientsContext);
    if (!context) {
        throw new Error('useClients must be used within ClientsProvider');
    }
    return context;
};
