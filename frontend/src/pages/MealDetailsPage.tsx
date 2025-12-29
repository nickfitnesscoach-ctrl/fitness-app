import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { api, MealAnalysis, MealPhoto } from '../services/api';
import PageHeader from '../components/PageHeader';
import { Flame, Drumstick, Droplets, Wheat, Trash2, Edit2, ChevronLeft, ChevronRight, AlertCircle, Loader2 } from 'lucide-react';
// F-019: Skeleton loaders for better loading UX
import { SkeletonMealDetails } from '../components/Skeleton';
// F-029: Toast notifications
import { useToast } from '../contexts/ToastContext';
// Meal modals
import { DeleteMealModal } from '../components/meal/DeleteMealModal';
import { DeleteFoodItemModal } from '../components/meal/DeleteFoodItemModal';
import { EditFoodItemModal } from '../components/meal/EditFoodItemModal';

const MealDetailsPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const toast = useToast();
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<MealAnalysis | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [deleting, setDeleting] = useState(false);

    // Food item deletion state
    const [itemToDelete, setItemToDelete] = useState<number | null>(null);
    const [showDeleteItemConfirm, setShowDeleteItemConfirm] = useState(false);
    const [deletingItem, setDeletingItem] = useState(false);

    // Food item edit state
    const [itemToEdit, setItemToEdit] = useState<{ id: number; name: string; grams: number } | null>(null);
    const [showEditModal, setShowEditModal] = useState(false);
    const [editing, setEditing] = useState(false);
    const [editName, setEditName] = useState('');
    const [editGrams, setEditGrams] = useState('');

    // Photo gallery state (multi-photo meals)
    const [currentPhotoIndex, setCurrentPhotoIndex] = useState(0);

    // Helper: Navigate back to date from location state
    const navigateBackToDate = () => {
        const returnDate = (location.state as any)?.returnDate;
        if (returnDate) {
            navigate(`/?date=${returnDate}`, { replace: true });
        } else {
            navigate('/', { replace: true });
        }
    };

    // Helper: Reload meal data from API
    const reloadMeal = async (): Promise<MealAnalysis | null> => {
        if (!id) return null;
        const result = await api.getMealAnalysis(parseInt(id));
        setData(result);
        return result;
    };

    useEffect(() => {
        const loadData = async () => {
            if (!id) return;
            try {
                setLoading(true);
                await reloadMeal();
            } catch (err) {
                console.error('Failed to load meal details:', err);
                setError('Не удалось загрузить данные блюда');
            } finally {
                setLoading(false);
            }
        };

        loadData();
    }, [id]);

    const handleDelete = async () => {
        if (!id) return;

        try {
            setDeleting(true);
            await api.deleteMeal(parseInt(id));
            // Success - navigate back with date from location state
            navigateBackToDate();
        } catch (err) {
            console.error('Failed to delete meal:', err);
            const errorMessage = err instanceof Error ? err.message : 'Не удалось удалить приём пищи';
            setError(errorMessage);
            setShowDeleteConfirm(false);
            setDeleting(false);
        }
    };

    const handleDeleteItem = async () => {
        if (!id || !itemToDelete) return;

        try {
            setDeletingItem(true);
            await api.deleteFoodItem(parseInt(id), itemToDelete);

            // Reload meal data to reflect the changes
            const result = await reloadMeal();

            // If no items left, navigate back with date from location state
            if (result && result.recognized_items.length === 0) {
                navigateBackToDate();
                return;
            }

            setShowDeleteItemConfirm(false);
            setItemToDelete(null);
        } catch (err) {
            console.error('Failed to delete food item:', err);
            const errorMessage = err instanceof Error ? err.message : 'Не удалось удалить блюдо';
            setError(errorMessage);
            setShowDeleteItemConfirm(false);
            setItemToDelete(null);
        } finally {
            setDeletingItem(false);
        }
    };

    const handleEditClick = (item: MealAnalysis['recognized_items'][number]) => {
        // F-005 FIX: Backend returns item.grams, not item.amount_grams
        setItemToEdit({ id: item.id, name: item.name, grams: item.grams });
        setEditName(item.name);
        setEditGrams(item.grams.toString());
        setShowEditModal(true);
    };

    const handleUpdateItem = async () => {
        if (!id || !itemToEdit) return;

        const newGrams = parseInt(editGrams);
        if (isNaN(newGrams) || newGrams <= 0) {
            setError('Введите корректное количество граммов (больше 0)');
            return;
        }

        // Max 10kg (10000g) per single food item is reasonable
        if (newGrams > 10000) {
            setError('Максимальное количество - 10000 г (10 кг)');
            return;
        }

        if (!editName.trim()) {
            setError('Введите название блюда');
            return;
        }

        try {
            setEditing(true);
            // F-006 FIX: Backend expects 'grams', not 'amount_grams'
            await api.updateFoodItem(parseInt(id), itemToEdit.id, {
                name: editName.trim(),
                grams: newGrams
            });

            // Reload meal data
            await reloadMeal();

            setShowEditModal(false);
            setItemToEdit(null);
            setEditName('');
            setEditGrams('');
            // F-029: Show success toast
            toast.success('Блюдо обновлено');
        } catch (err) {
            console.error('Failed to update food item:', err);
            const errorMessage = err instanceof Error ? err.message : 'Не удалось обновить блюдо';
            setError(errorMessage);
            toast.error(errorMessage);
        } finally {
            setEditing(false);
        }
    };

    // F-019: Show skeleton loader while loading
    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50">
                <PageHeader title="Детали блюда" />
                <SkeletonMealDetails />
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="min-h-screen bg-white p-4">
                <PageHeader title="Детали блюда" />
                <div className="flex flex-col items-center justify-center h-[80vh] text-center">
                    <p className="text-red-500 font-medium mb-4">{error || 'Блюдо не найдено'}</p>
                    <button
                        onClick={() => navigate(-1)}
                        className="text-blue-600 font-medium"
                    >
                        Вернуться назад
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 pb-8">
            <PageHeader title="Детали блюда" />

            {/* Large Photo Gallery (supports multi-photo meals) */}
            {(() => {
                // Show ALL photos (including FAILED/CANCELLED) - not just SUCCESS
                // This ensures sync with diary card which also shows all photos
                const allPhotos: MealPhoto[] = data.photos?.filter((p) => p.image_url) || [];

                // Build display list: use photos array or fallback to single photo_url
                const displayPhotos: { url: string; status?: string; error?: string | null }[] =
                    allPhotos.length > 0
                        ? allPhotos.map((p) => ({
                            url: p.image_url!,
                            status: p.status,
                            error: p.error_message
                        }))
                        : data.photo_url
                        ? [{ url: data.photo_url, status: 'SUCCESS' }]
                        : [];

                const hasMultiplePhotos = displayPhotos.length > 1;
                const safeIndex = Math.min(currentPhotoIndex, Math.max(0, displayPhotos.length - 1));
                const currentPhoto = displayPhotos[safeIndex];

                // Meal-level processing badge (shown once, not per-photo)
                const isMealProcessing = data.status === 'PROCESSING';

                return (
                    <div className="w-full aspect-[4/3] bg-gray-200 relative">
                        {displayPhotos.length > 0 && currentPhoto ? (
                            <>
                                <img
                                    src={currentPhoto.url}
                                    alt={`${data.label} - фото ${safeIndex + 1}`}
                                    className="w-full h-full object-cover"
                                />

                                {/* Meal-level processing badge (only for PROCESSING status) */}
                                {isMealProcessing && (
                                    <div className="absolute top-4 left-4 bg-blue-500 text-white px-3 py-1.5 rounded-full text-sm font-medium flex items-center gap-1.5 shadow-lg">
                                        <Loader2 size={16} className="animate-spin" />
                                        Обработка...
                                    </div>
                                )}

                                {/* Photo navigation for multi-photo meals */}
                                {hasMultiplePhotos && (
                                    <>
                                        {/* Photo counter */}
                                        <div className="absolute top-4 right-4 bg-black/60 text-white px-3 py-1 rounded-full text-sm font-medium">
                                            {safeIndex + 1} / {displayPhotos.length}
                                        </div>

                                        {/* Navigation arrows */}
                                        <button
                                            onClick={() => setCurrentPhotoIndex((prev) =>
                                                prev === 0 ? displayPhotos.length - 1 : prev - 1
                                            )}
                                            className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white p-2 rounded-full transition-colors"
                                            aria-label="Предыдущее фото"
                                        >
                                            <ChevronLeft size={24} />
                                        </button>
                                        <button
                                            onClick={() => setCurrentPhotoIndex((prev) =>
                                                prev === displayPhotos.length - 1 ? 0 : prev + 1
                                            )}
                                            className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white p-2 rounded-full transition-colors"
                                            aria-label="Следующее фото"
                                        >
                                            <ChevronRight size={24} />
                                        </button>

                                        {/* Dot indicators with status colors */}
                                        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 flex gap-1.5">
                                            {displayPhotos.map((photo, i) => {
                                                // Color dot based on photo status (no blue for PROCESSING - use meal-level)
                                                let dotColor = 'bg-white';
                                                if (photo.status === 'FAILED') dotColor = 'bg-red-400';
                                                else if (photo.status === 'CANCELLED') dotColor = 'bg-gray-400';
                                                // PROCESSING/PENDING show as white (meal-level spinner handles this)

                                                return (
                                                    <button
                                                        key={i}
                                                        onClick={() => setCurrentPhotoIndex(i)}
                                                        className={`w-2.5 h-2.5 rounded-full transition-all ${dotColor} ${
                                                            i === safeIndex
                                                                ? 'ring-2 ring-white ring-offset-1 ring-offset-black/20'
                                                                : 'opacity-60'
                                                        }`}
                                                        aria-label={`Перейти к фото ${i + 1}`}
                                                    />
                                                );
                                            })}
                                        </div>
                                    </>
                                )}
                            </>
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-gray-400">
                                Нет фото
                            </div>
                        )}

                        {/* Badge Overlay */}
                        <div className="absolute bottom-4 left-4">
                            <span className="bg-white/90 backdrop-blur-sm text-gray-900 px-4 py-2 rounded-full font-bold shadow-lg">
                                {data.label}
                            </span>
                        </div>
                    </div>
                );
            })()}

            {/* Info message if some photos failed */}
            {(() => {
                const failedCount = data.photos?.filter(p => p.status === 'FAILED' || p.status === 'CANCELLED').length || 0;
                if (failedCount === 0) return null;

                return (
                    <div className="mx-4 mt-4 bg-yellow-50 border border-yellow-200 rounded-xl p-3 flex items-start gap-2">
                        <AlertCircle size={16} className="text-yellow-600 mt-0.5 shrink-0" />
                        <p className="text-sm text-yellow-800">
                            {failedCount === 1
                                ? 'Одно из фото не удалось обработать и не учтено в расчётах'
                                : `${failedCount} фото не удалось обработать и не учтены в расчётах`
                            }
                        </p>
                    </div>
                );
            })()}

            <div className="p-4 space-y-6">
                {/* Recognized Dishes Block */}
                <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">
                        Распознанные блюда ({data.recognized_items.length})
                    </h2>

                    <div className="space-y-3">
                        {data.recognized_items.map((item) => (
                            <div key={item.id} className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 group relative">
                                <div className="flex justify-between items-start mb-3">
                                    <div className="flex-1">
                                        <h3 className="font-bold text-gray-900 text-lg leading-tight">
                                            {item.name}
                                        </h3>
                                        <p className="text-gray-500 text-sm mt-1">
                                            {item.grams} г
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="flex items-center gap-1 bg-orange-50 px-3 py-1.5 rounded-xl">
                                            <Flame size={16} className="text-orange-500" />
                                            <span className="font-bold text-orange-700">
                                                {Math.round(item.calories)}
                                            </span>
                                        </div>
                                        <button
                                            onClick={() => handleEditClick(item)}
                                            className="p-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                                            aria-label="Редактировать блюдо"
                                        >
                                            <Edit2 size={16} />
                                        </button>
                                        <button
                                            onClick={() => {
                                                setItemToDelete(item.id);
                                                setShowDeleteItemConfirm(true);
                                            }}
                                            className="p-2 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                                            aria-label="Удалить блюдо"
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </div>

                                {/* Macros */}
                                <div className="grid grid-cols-3 gap-2">
                                    <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
                                        <div className="flex items-center gap-1 text-gray-500 text-xs mb-1">
                                            <Drumstick size={12} />
                                            <span>Белки</span>
                                        </div>
                                        <span className="font-bold text-gray-900">{item.protein}</span>
                                    </div>
                                    <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
                                        <div className="flex items-center gap-1 text-gray-500 text-xs mb-1">
                                            <Droplets size={12} />
                                            <span>Жиры</span>
                                        </div>
                                        <span className="font-bold text-gray-900">{item.fat}</span>
                                    </div>
                                    <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
                                        <div className="flex items-center gap-1 text-gray-500 text-xs mb-1">
                                            <Wheat size={12} />
                                            <span>Угл.</span>
                                        </div>
                                        <span className="font-bold text-gray-900">{item.carbohydrates}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Delete Button */}
                <div className="px-4 pb-8">
                    <button
                        onClick={() => setShowDeleteConfirm(true)}
                        className="w-full bg-red-50 hover:bg-red-100 text-red-600 font-bold py-4 rounded-2xl transition-colors flex items-center justify-center gap-2"
                    >
                        <Trash2 size={20} />
                        Удалить приём пищи
                    </button>
                </div>
            </div>

            {/* Modals */}
            <DeleteMealModal
                isOpen={showDeleteConfirm}
                onClose={() => setShowDeleteConfirm(false)}
                onConfirm={handleDelete}
                loading={deleting}
            />

            <DeleteFoodItemModal
                isOpen={showDeleteItemConfirm}
                onClose={() => {
                    setShowDeleteItemConfirm(false);
                    setItemToDelete(null);
                }}
                onConfirm={handleDeleteItem}
                loading={deletingItem}
            />

            <EditFoodItemModal
                isOpen={showEditModal}
                onClose={() => {
                    setShowEditModal(false);
                    setItemToEdit(null);
                    setEditName('');
                    setEditGrams('');
                }}
                onConfirm={handleUpdateItem}
                loading={editing}
                itemName={editName}
                itemGrams={editGrams}
                onNameChange={setEditName}
                onGramsChange={setEditGrams}
            />
        </div>
    );
};

export default MealDetailsPage;
