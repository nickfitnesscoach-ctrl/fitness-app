import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { api, MealAnalysis, MealPhoto } from '../services/api';
import PageHeader from '../components/PageHeader';
import { Flame, Drumstick, Droplets, Wheat, Trash2, Edit2, AlertCircle, Loader2 } from 'lucide-react';
import { SkeletonMealDetails } from '../components/Skeleton';
import { useToast } from '../contexts/ToastContext';
import { DeleteMealModal } from '../components/meal/DeleteMealModal';
import { DeleteFoodItemModal } from '../components/meal/DeleteFoodItemModal';
import { EditFoodItemModal } from '../components/meal/EditFoodItemModal';
import { PageContainer } from '../components/shared/PageContainer';

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

    const [itemToDelete, setItemToDelete] = useState<number | null>(null);
    const [showDeleteItemConfirm, setShowDeleteItemConfirm] = useState(false);
    const [deletingItem, setDeletingItem] = useState(false);

    const [itemToEdit, setItemToEdit] = useState<{ id: number; name: string; grams: number } | null>(null);
    const [showEditModal, setShowEditModal] = useState(false);
    const [editing, setEditing] = useState(false);
    const [editName, setEditName] = useState('');
    const [editGrams, setEditGrams] = useState('');

    const [currentPhotoIndex, setCurrentPhotoIndex] = useState(0);
    const [touchStart, setTouchStart] = useState<number | null>(null);
    const [touchEnd, setTouchEnd] = useState<number | null>(null);
    const minSwipeDistance = 50;

    const onTouchStart = (e: React.TouchEvent) => {
        setTouchEnd(null);
        setTouchStart(e.targetTouches[0].clientX);
    };

    const onTouchMove = (e: React.TouchEvent) => {
        setTouchEnd(e.targetTouches[0].clientX);
    };

    const onTouchEnd = (displayPhotosLength: number) => {
        if (!touchStart || !touchEnd) return;
        const distance = touchStart - touchEnd;
        const isLeftSwipe = distance > minSwipeDistance;
        const isRightSwipe = distance < -minSwipeDistance;
        if (isLeftSwipe) {
            setCurrentPhotoIndex((prev) => prev === displayPhotosLength - 1 ? 0 : prev + 1);
        }
        if (isRightSwipe) {
            setCurrentPhotoIndex((prev) => prev === 0 ? displayPhotosLength - 1 : prev - 1);
        }
    };

    const navigateBackToDate = () => {
        const returnDate = (location.state as any)?.returnDate;
        if (returnDate) {
            navigate(`/?date=${returnDate}`, { replace: true });
        } else {
            navigate('/', { replace: true });
        }
    };

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
            const result = await reloadMeal();
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
        setItemToEdit({ id: item.id, name: item.name, grams: item.grams });
        setEditName(item.name);
        setEditGrams(item.grams.toString());
        setShowEditModal(true);
    };

    const handleUpdateItem = async () => {
        if (!id || !itemToEdit) return;
        const newGrams = parseInt(editGrams);
        if (isNaN(newGrams) || newGrams <= 0 || newGrams > 10000) {
            setError('Введите корректное количество граммов (1-10000)');
            return;
        }
        if (!editName.trim()) {
            setError('Введите название блюда');
            return;
        }
        try {
            setEditing(true);
            await api.updateFoodItem(parseInt(id), itemToEdit.id, {
                name: editName.trim(),
                grams: newGrams
            });
            await reloadMeal();
            setShowEditModal(false);
            setItemToEdit(null);
            setEditName('');
            setEditGrams('');
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
            <div className="min-h-screen bg-white">
                <PageHeader title="Детали блюда" />
                <div className="flex flex-col items-center justify-center h-[80vh] text-center p-4">
                    <p className="text-red-500 font-medium mb-4">{error || 'Блюдо не найдено'}</p>
                    <button onClick={() => navigate(-1)} className="text-blue-600 font-medium">Вернуться назад</button>
                </div>
            </div>
        );
    }

    const allPhotos: MealPhoto[] = data.photos?.filter((p) => p.image_url) || [];
    const displayPhotos: { url: string; status?: string; error?: string | null }[] =
        allPhotos.length > 0
            ? allPhotos.map((p) => ({ url: p.image_url!, status: p.status, error: p.error_message }))
            : data.photo_url ? [{ url: data.photo_url, status: 'SUCCESS' }] : [];
    const hasMultiplePhotos = displayPhotos.length > 1;
    const safeIndex = Math.min(currentPhotoIndex, Math.max(0, displayPhotos.length - 1));
    const currentPhoto = displayPhotos[safeIndex];
    const isMealProcessing = data.status === 'PROCESSING';

    return (
        <div className="min-h-screen bg-gray-50">
            <PageHeader title="Детали блюда" />

            {/* Large Photo Gallery */}
            <div
                className="w-full aspect-[4/3] bg-gray-200 relative overflow-hidden"
                onTouchStart={hasMultiplePhotos ? onTouchStart : undefined}
                onTouchMove={hasMultiplePhotos ? onTouchMove : undefined}
                onTouchEnd={hasMultiplePhotos ? () => onTouchEnd(displayPhotos.length) : undefined}
            >
                {displayPhotos.length > 0 && currentPhoto ? (
                    <>
                        <img src={currentPhoto.url} alt={`${data.label} - фото ${safeIndex + 1}`} className="w-full h-full object-cover" />
                        {isMealProcessing && (
                            <div className="absolute top-4 left-4 bg-blue-500 text-white px-3 py-1.5 rounded-full text-sm font-medium flex items-center gap-1.5 shadow-lg">
                                <Loader2 size={16} className="animate-spin" />
                                Обработка...
                            </div>
                        )}
                        {hasMultiplePhotos && (
                            <>
                                <div className="absolute top-4 right-4 bg-black/60 text-white px-3 py-1 rounded-full text-sm font-medium">
                                    {safeIndex + 1} / {displayPhotos.length}
                                </div>
                                <div className="absolute bottom-16 left-1/2 -translate-x-1/2 flex gap-1.5">
                                    {displayPhotos.map((photo, i) => {
                                        let dotColor = 'bg-white';
                                        if (photo.status === 'FAILED') dotColor = 'bg-red-400';
                                        else if (photo.status === 'CANCELLED') dotColor = 'bg-gray-400';
                                        return (
                                            <button
                                                key={i}
                                                onClick={() => setCurrentPhotoIndex(i)}
                                                className={`w-2.5 h-2.5 rounded-full transition-all ${dotColor} ${i === safeIndex ? 'ring-2 ring-white ring-offset-1 ring-offset-black/20' : 'opacity-60'}`}
                                            />
                                        );
                                    })}
                                </div>
                            </>
                        )}
                    </>
                ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-400">Нет фото</div>
                )}
                <div className="absolute bottom-4 left-4">
                    <span className="bg-white/90 backdrop-blur-sm text-gray-900 px-4 py-2 rounded-full font-bold shadow-lg">{data.label}</span>
                </div>
            </div>

            {(() => {
                const failedCount = data.photos?.filter(p => p.status === 'FAILED' || p.status === 'CANCELLED').length || 0;
                if (failedCount === 0) return null;
                return (
                    <PageContainer className="mt-4">
                        <div className="bg-yellow-50 border border-yellow-200 rounded-[var(--radius-card)] p-[var(--card-p)] flex items-start gap-2 shadow-sm">
                            <AlertCircle size={16} className="text-yellow-600 mt-0.5 shrink-0" />
                            <p className="text-sm text-yellow-800">
                                {failedCount === 1 ? 'Одно из фото не удалось обработать' : `${failedCount} фото не удалось обработать`}
                            </p>
                        </div>
                    </PageContainer>
                );
            })()}

            <PageContainer className="py-6 space-y-[var(--section-gap)]">
                <div>
                    <h2 className="text-lg font-bold text-gray-900 mb-4">Распознанные блюда ({data.recognized_items.length})</h2>
                    <div className="space-y-3">
                        {data.recognized_items.map((item) => (
                            <div key={item.id} className="bg-white rounded-[var(--radius-card)] p-[var(--card-p)] shadow-sm border border-gray-100">
                                <div className="flex justify-between items-start mb-3">
                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-bold text-gray-900 text-lg leading-tight truncate">{item.name}</h3>
                                        <p className="text-gray-500 text-sm mt-1">{item.grams} г</p>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <div className="flex items-center gap-1 bg-orange-50 px-3 py-1.5 rounded-xl">
                                            <Flame size={16} className="text-orange-500" />
                                            <span className="font-bold text-orange-700">{Math.round(item.calories)}</span>
                                        </div>
                                        <button onClick={() => handleEditClick(item)} className="p-2 bg-blue-50 text-blue-600 rounded-lg"><Edit2 size={16} /></button>
                                    </div>
                                </div>
                                <div className="grid grid-cols-3 gap-2">
                                    <MacroItem label="Белки" value={item.protein} icon={<Drumstick size={12} />} />
                                    <MacroItem label="Жиры" value={item.fat} icon={<Droplets size={12} />} />
                                    <MacroItem label="Угл." value={item.carbohydrates} icon={<Wheat size={12} />} />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
                <button onClick={() => setShowDeleteConfirm(true)} className="w-full bg-red-50 text-red-600 font-bold py-4 rounded-[var(--radius-card)] flex items-center justify-center gap-2"><Trash2 size={20} />Удалить приём пищи</button>
            </PageContainer>

            <DeleteMealModal isOpen={showDeleteConfirm} onClose={() => setShowDeleteConfirm(false)} onConfirm={handleDelete} loading={deleting} />
            <DeleteFoodItemModal isOpen={showDeleteItemConfirm} onClose={() => { setShowDeleteItemConfirm(false); setItemToDelete(null); }} onConfirm={handleDeleteItem} loading={deletingItem} />
            <EditFoodItemModal isOpen={showEditModal} onClose={() => { setShowEditModal(false); setItemToEdit(null); }} onConfirm={handleUpdateItem} loading={editing} itemName={editName} itemGrams={editGrams} onNameChange={setEditName} onGramsChange={setEditGrams} />
        </div>
    );
};

const MacroItem: React.FC<{ label: string, value: number, icon: React.ReactNode }> = ({ label, value, icon }) => (
    <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
        <div className="flex items-center gap-1 text-gray-500 text-xs mb-1 font-medium">{icon}<span>{label}</span></div>
        <span className="font-bold text-gray-900 tabular-nums">{value}</span>
    </div>
);

export default MealDetailsPage;
