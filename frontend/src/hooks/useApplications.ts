import { useState, useEffect } from 'react';
import { Application } from '../types/application';
import { api } from '../services/api';

type ApplicationStatus = 'all' | 'new' | 'viewed' | 'contacted';

interface UseApplicationsArgs {
    isClient: (id: number) => boolean;
}

interface UseApplicationsResult {
    applications: Application[];
    filteredApplications: Application[];
    isLoading: boolean;
    searchTerm: string;
    filterStatus: ApplicationStatus;
    selectedApp: Application | null;

    setSearchTerm: (value: string) => void;
    setFilterStatus: (status: ApplicationStatus) => void;
    selectApp: (app: Application | null) => void;

    changeStatus: (id: number, status: Exclude<ApplicationStatus, 'all'>) => Promise<void>;
    deleteApplication: (id: number) => Promise<void>;

    reload: () => Promise<void>;
}

// Mapping functions for backend data transformation
const GENDER_MAP: Record<string, string> = {
    'male': 'Мужской',
    'female': 'Женский'
};

const ACTIVITY_MAP: Record<string, string> = {
    'minimal': 'Минимальная',
    'low': 'Низкая',
    'medium': 'Средняя',
    'high': 'Высокая'
};

const TRAINING_MAP: Record<string, string> = {
    'beginner': 'Новичок',
    'intermediate': 'Средний',
    'advanced': 'Продвинутый',
    'home': 'Домашний формат'
};

const GOALS_MAP: Record<string, string> = {
    'weight_loss': 'Снижение веса',
    'fat_loss': 'Сжигание жира',
    'muscle_gain': 'Набор мышц',
    'tighten_body': 'Подтянуть тело',
    'belly_sides': 'Убрать живот и бока',
    'glutes_shape': 'Округлые ягодицы',
    'maintenance': 'Поддержание формы'
};

const RESTRICTIONS_MAP: Record<string, string> = {
    'none': 'Нет ограничений',
    'back': 'Проблемы со спиной',
    'joints': 'Проблемы с суставами',
    'heart': 'Сердечно-сосудистые',
    'allergy': 'Аллергии',
    'stress': 'Высокий стресс',
    'diabetes': 'Диабет'
};

function mapBackendApplication(item: any): Application {
    const details = item.details || {};
    return {
        id: item.id,
        first_name: item.first_name,
        username: item.username || 'anon',
        photo_url: item.photo_url || '',
        status: item.status || 'new',
        date: new Date(item.created_at).toLocaleDateString('ru-RU'),
        details: {
            age: details.age || 0,
            gender: (GENDER_MAP[details.gender] || 'Мужской') as 'Мужской' | 'Женский',
            height: details.height || 0,
            weight: details.weight || 0,
            target_weight: details.target_weight || 0,
            activity_level: ACTIVITY_MAP[details.activity_level] || 'Не указана',
            training_level: TRAINING_MAP[details.training_level] || 'Не указан',
            goals: (details.goals || []).map((g: string) => GOALS_MAP[g] || g),
            limitations: (details.health_restrictions || []).map((r: string) => RESTRICTIONS_MAP[r] || r),
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
            diet_type: details.diet_type || '',
            meals_per_day: details.meals_per_day || 0,
            allergies: details.allergies || '',
            disliked_food: details.disliked_food || '',
            supplements: details.supplements || '',
            timezone: details.timezone || 'UTC+3'
        }
    };
}

export function useApplications({ isClient }: UseApplicationsArgs): UseApplicationsResult {
    const [applications, setApplications] = useState<Application[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterStatus, setFilterStatus] = useState<ApplicationStatus>('new');
    const [selectedApp, setSelectedApp] = useState<Application | null>(null);

    const loadData = async () => {
        setIsLoading(true);
        try {
            const data = await api.getApplications();
            const formattedData: Application[] = data.map(mapBackendApplication);
            setApplications(formattedData);
        } catch (error) {
            console.error("Failed to load applications", error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    // Filter applications
    const filteredApplications = applications
        .filter(app => !isClient(app.id)) // Hide if already a client
        .filter(app => {
            const matchesSearch = app.first_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                app.username.toLowerCase().includes(searchTerm.toLowerCase());
            const matchesStatus = filterStatus === 'all' || app.status === filterStatus;
            return matchesSearch && matchesStatus;
        });

    const changeStatus = async (appId: number, newStatus: 'new' | 'viewed' | 'contacted') => {
        try {
            // Optimistic update
            setApplications(prev => prev.map(app =>
                app.id === appId ? { ...app, status: newStatus } : app
            ));
            // Update selectedApp if it's open
            if (selectedApp && selectedApp.id === appId) {
                setSelectedApp({ ...selectedApp, status: newStatus });
            }
            // Save to backend
            await api.updateApplicationStatus(appId, newStatus);
        } catch (error) {
            console.error('Ошибка при обновлении статуса:', error);
        }
    };

    const deleteApplication = async (appId: number) => {
        try {
            // Delete from backend
            await api.deleteApplication(appId);
            // Remove from local state
            setApplications(prev => prev.filter(app => app.id !== appId));
            // Clear selectedApp if it was deleted
            if (selectedApp && selectedApp.id === appId) {
                setSelectedApp(null);
            }
        } catch (error) {
            console.error('Ошибка при удалении:', error);
            throw error; // Re-throw to allow UI to handle error display
        }
    };

    return {
        applications,
        filteredApplications,
        isLoading,
        searchTerm,
        filterStatus,
        selectedApp,
        setSearchTerm,
        setFilterStatus,
        selectApp: setSelectedApp,
        changeStatus,
        deleteApplication,
        reload: loadData
    };
}
