import { useEffect, useMemo, useState } from 'react';
import type {
    Application,
    ApplicationResponse,
    ApplicationStatusApi,
    ClientDetailsApi,
    ClientDetailsUi,
} from '../types';
import { api } from '../../../services/api';

type ApplicationStatusFilter = 'all' | ApplicationStatusApi;

interface UseApplicationsArgs {
    isClient: (id: number) => boolean;
}

interface UseApplicationsResult {
    applications: Application[];
    filteredApplications: Application[];
    isLoading: boolean;
    searchTerm: string;
    filterStatus: ApplicationStatusFilter;
    selectedApp: Application | null;

    setSearchTerm: (value: string) => void;
    setFilterStatus: (status: ApplicationStatusFilter) => void;
    selectApp: (app: Application | null) => void;

    changeStatus: (id: number, status: Exclude<ApplicationStatusFilter, 'all'>) => Promise<void>;
    deleteApplication: (id: number) => Promise<void>;
    reload: () => Promise<void>;
}

// ---------- Maps (backend -> UI text) ----------
const GENDER_MAP: Record<string, string> = { male: 'Мужской', female: 'Женский' };
const ACTIVITY_MAP: Record<string, string> = {
    minimal: 'Минимальная',
    low: 'Низкая',
    medium: 'Средняя',
    high: 'Высокая',
};
const TRAINING_MAP: Record<string, string> = {
    beginner: 'Новичок',
    intermediate: 'Средний',
    advanced: 'Продвинутый',
    home: 'Домашний формат',
};
const GOALS_MAP: Record<string, string> = {
    weight_loss: 'Снижение веса',
    fat_loss: 'Сжигание жира',
    muscle_gain: 'Набор мышц',
    tighten_body: 'Подтянуть тело',
    belly_sides: 'Убрать живот и бока',
    glutes_shape: 'Округлые ягодицы',
    maintenance: 'Поддержание формы',
};
const RESTRICTIONS_MAP: Record<string, string> = {
    none: 'Нет ограничений',
    back: 'Проблемы со спиной',
    joints: 'Проблемы с суставами',
    heart: 'Сердечно-сосудистые',
    allergy: 'Аллергии',
    stress: 'Высокий стресс',
    diabetes: 'Диабет',
};

function normalizeStringArray(value: string[] | string | undefined): string[] {
    if (!value) return [];
    return Array.isArray(value) ? value : [value];
}

function formatDateRu(createdAt?: string): string {
    if (!createdAt) return '—';
    const d = new Date(createdAt);
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('ru-RU');
}

function buildBodyTypeImageUrl(
    genderApi: ClientDetailsApi['gender'],
    typeId?: number,
    variant: 'current' | 'desired' = 'current'
): string {
    if (!typeId) return '';
    const g = genderApi === 'male' ? 'm' : genderApi === 'female' ? 'f' : 'm';
    return variant === 'current'
        ? `/assets/body_types/${g}_type_${typeId}.jpg`
        : `/assets/body_types/${g}_type_after_${typeId}.jpg`;
}

function mapDetailsApiToUi(details: ClientDetailsApi | undefined): ClientDetailsUi {
    const d = details ?? {};
    const genderUi = d.gender ? (GENDER_MAP[d.gender] ?? '—') : '—';

    const goals = (d.goals ?? []).map((g: string) => GOALS_MAP[g] ?? g);
    const limitations = (d.health_restrictions ?? []).map((r: string) => RESTRICTIONS_MAP[r] ?? r);

    return {
        age: d.age,
        gender: genderUi,
        height: d.height,
        weight: d.weight,
        target_weight: d.target_weight,

        activity_level: d.activity_level ? (ACTIVITY_MAP[d.activity_level] ?? d.activity_level) : 'Не указана',
        training_level: d.training_level ? (TRAINING_MAP[d.training_level] ?? d.training_level) : 'Не указан',

        goals,
        limitations,

        body_type: d.current_body_type
            ? {
                id: d.current_body_type,
                description: 'Текущая форма',
                image_url: buildBodyTypeImageUrl(d.gender, d.current_body_type, 'current'),
            }
            : undefined,

        desired_body_type: d.ideal_body_type
            ? {
                id: d.ideal_body_type,
                description: 'Желаемая форма',
                image_url: buildBodyTypeImageUrl(d.gender, d.ideal_body_type, 'desired'),
            }
            : undefined,

        timezone: d.timezone ?? 'UTC+3',

        diet_type: d.diet_type ?? '',
        meals_per_day: d.meals_per_day ?? 0,
        allergies: normalizeStringArray(d.allergies),
        disliked_food: d.disliked_food ?? '',
        supplements: d.supplements ?? '',
    };
}

function mapApplicationFromApi(item: ApplicationResponse, isClient: (id: number) => boolean): Application {
    return {
        id: item.id,
        telegram_id: item.telegram_id,
        first_name: item.first_name,
        last_name: item.last_name,
        username: item.username,
        photo_url: item.photo_url ?? '',
        created_at: item.created_at,
        date: formatDateRu(item.created_at),
        status: isClient(item.id) ? 'client' : item.status,
        details: mapDetailsApiToUi(item.details),
    };
}

export function useApplications({ isClient }: UseApplicationsArgs): UseApplicationsResult {
    const [applications, setApplications] = useState<Application[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterStatus, setFilterStatus] = useState<ApplicationStatusFilter>('new');
    const [selectedApp, setSelectedApp] = useState<Application | null>(null);

    const loadData = async () => {
        setIsLoading(true);
        try {
            const data = (await api.getApplications()) as ApplicationResponse[];
            const formatted = data.map((item) => mapApplicationFromApi(item, isClient));
            setApplications(formatted);
        } catch (error) {
            console.error('Failed to load applications', error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        void loadData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const filteredApplications = useMemo(() => {
        const q = searchTerm.trim().toLowerCase();

        return applications
            .filter((app) => !isClient(app.id)) // keep behavior: hide if already a client
            .filter((app) => {
                const matchesSearch =
                    app.first_name.toLowerCase().includes(q) ||
                    (app.username ? app.username.toLowerCase().includes(q) : false);

                const matchesStatus = filterStatus === 'all' || app.status === filterStatus;
                return matchesSearch && matchesStatus;
            });
    }, [applications, filterStatus, isClient, searchTerm]);

    const changeStatus = async (appId: number, newStatus: ApplicationStatusApi) => {
        try {
            // optimistic update
            setApplications((prev) => prev.map((app) => (app.id === appId ? { ...app, status: newStatus } : app)));

            if (selectedApp?.id === appId) {
                setSelectedApp({ ...selectedApp, status: newStatus });
            }

            await api.updateApplicationStatus(appId, newStatus);
        } catch (error) {
            console.error('Ошибка при обновлении статуса:', error);
        }
    };

    const deleteApplication = async (appId: number) => {
        try {
            await api.deleteApplication(appId);
            setApplications((prev) => prev.filter((app) => app.id !== appId));
            if (selectedApp?.id === appId) setSelectedApp(null);
        } catch (error) {
            console.error('Ошибка при удалении:', error);
            throw error;
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
        reload: loadData,
    };
}
