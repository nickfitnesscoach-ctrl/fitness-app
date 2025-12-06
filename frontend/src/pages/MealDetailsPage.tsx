import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { api, MealAnalysis } from '../services/api';
import PageHeader from '../components/PageHeader';
import { Flame, Drumstick, Droplets, Wheat, Trash2, Edit2 } from 'lucide-react';

const MealDetailsPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
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


    useEffect(() => {
        const loadData = async () => {
            if (!id) return;
            try {
                setLoading(true);
                const result = await api.getMealAnalysis(parseInt(id));
                setData(result);
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
            const returnDate = (location.state as any)?.returnDate;
            if (returnDate) {
                navigate(`/?date=${returnDate}`, { replace: true });
            } else {
                navigate('/', { replace: true });
            }
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
            const result = await api.getMealAnalysis(parseInt(id));
            setData(result);

            // If no items left, navigate back with date from location state
            if (result.recognized_items.length === 0) {
                const returnDate = (location.state as any)?.returnDate;
                if (returnDate) {
                    navigate(`/?date=${returnDate}`, { replace: true });
                } else {
                    navigate('/', { replace: true });
                }
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

    const handleEditClick = (item: any) => {
        setItemToEdit({ id: item.id, name: item.name, grams: item.amount_grams });
        setEditName(item.name);
        setEditGrams(item.amount_grams.toString());
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
            await api.updateFoodItem(parseInt(id), itemToEdit.id, {
                name: editName.trim(),
                amount_grams: newGrams
            });

            // Reload meal data
            const result = await api.getMealAnalysis(parseInt(id));
            setData(result);

            setShowEditModal(false);
            setItemToEdit(null);
            setEditName('');
            setEditGrams('');
        } catch (err) {
            console.error('Failed to update food item:', err);
            const errorMessage = err instanceof Error ? err.message : 'Не удалось обновить блюдо';
            setError(errorMessage);
        } finally {
            setEditing(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-white flex items-center justify-center">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
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

            {/* Large Photo */}
            <div className="w-full aspect-[4/3] bg-gray-200 relative">
                {data.photo_url ? (
                    <img
                        src={data.photo_url}
                        alt={data.label}
                        className="w-full h-full object-cover"
                    />
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
                                            {item.amount_grams} г
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
                                        <span className="font-bold text-gray-900">{item.carbs}</span>
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

            {/* Delete Meal Confirmation Modal */}
            {showDeleteConfirm && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl">
                        <div className="text-center mb-4">
                            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                                <Trash2 className="text-red-600" size={32} />
                            </div>
                            <h3 className="text-xl font-bold text-gray-900 mb-2">
                                Удалить приём пищи?
                            </h3>
                            <p className="text-gray-600">
                                Это действие нельзя будет отменить. Все блюда в этом приёме пищи будут удалены.
                            </p>
                        </div>

                        <div className="space-y-3">
                            <button
                                onClick={handleDelete}
                                disabled={deleting}
                                className="w-full bg-red-600 hover:bg-red-700 text-white py-3 rounded-xl font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {deleting ? 'Удаление...' : 'Да, удалить'}
                            </button>
                            <button
                                onClick={() => setShowDeleteConfirm(false)}
                                disabled={deleting}
                                className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Delete Food Item Confirmation Modal */}
            {showDeleteItemConfirm && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl">
                        <div className="text-center mb-4">
                            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                                <Trash2 className="text-red-600" size={32} />
                            </div>
                            <h3 className="text-xl font-bold text-gray-900 mb-2">
                                Удалить блюдо?
                            </h3>
                            <p className="text-gray-600">
                                Это действие нельзя будет отменить. Блюдо будет удалено из приёма пищи.
                            </p>
                        </div>

                        <div className="space-y-3">
                            <button
                                onClick={handleDeleteItem}
                                disabled={deletingItem}
                                className="w-full bg-red-600 hover:bg-red-700 text-white py-3 rounded-xl font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {deletingItem ? 'Удаление...' : 'Да, удалить'}
                            </button>
                            <button
                                onClick={() => {
                                    setShowDeleteItemConfirm(false);
                                    setItemToDelete(null);
                                }}
                                disabled={deletingItem}
                                className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Edit Food Item Modal */}
            {showEditModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl">
                        <div className="mb-4">
                            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
                                <Edit2 className="text-blue-600" size={32} />
                            </div>
                            <h3 className="text-xl font-bold text-gray-900 text-center mb-2">
                                Редактировать блюдо
                            </h3>
                        </div>

                        <div className="space-y-4 mb-6">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Название
                                </label>
                                <input
                                    type="text"
                                    value={editName}
                                    onChange={(e) => setEditName(e.target.value)}
                                    className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                                    placeholder="Название блюда"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Вес (граммы)
                                </label>
                                <input
                                    type="number"
                                    value={editGrams}
                                    onChange={(e) => setEditGrams(e.target.value)}
                                    className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                                    placeholder="Вес в граммах"
                                    min="1"
                                    max="10000"
                                />
                            </div>
                        </div>

                        <div className="space-y-3">
                            <button
                                onClick={handleUpdateItem}
                                disabled={editing}
                                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-xl font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {editing ? 'Сохранение...' : 'Сохранить'}
                            </button>
                            <button
                                onClick={() => {
                                    setShowEditModal(false);
                                    setItemToEdit(null);
                                    setEditName('');
                                    setEditGrams('');
                                }}
                                disabled={editing}
                                className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MealDetailsPage;
