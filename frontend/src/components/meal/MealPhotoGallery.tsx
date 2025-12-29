import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Image as ImageIcon, AlertCircle, XCircle, Loader2 } from 'lucide-react';
import type { MealPhoto } from '../../services/api/types';

interface MealPhotoGalleryProps {
    photos: MealPhoto[];
    /** Fallback single photo URL (backward compatibility) */
    fallbackPhotoUrl?: string | null;
    /** Size preset */
    size?: 'sm' | 'md' | 'lg';
    /** Show all photos including FAILED/CANCELLED (default: true) */
    showAllPhotos?: boolean;
}

const SIZE_CLASSES = {
    sm: 'w-12 h-12',
    md: 'w-16 h-16',
    lg: 'w-20 h-20',
};

/**
 * Horizontal swipeable gallery for multi-photo meals.
 * Shows a single image when only one photo exists.
 * Shows ALL photos (including FAILED/CANCELLED) with status badges.
 */
export const MealPhotoGallery: React.FC<MealPhotoGalleryProps> = ({
    photos,
    fallbackPhotoUrl,
    size = 'md',
    showAllPhotos = true,
}) => {
    const [currentIndex, setCurrentIndex] = useState(0);

    // Show all photos with URLs (including FAILED/CANCELLED for sync with details page)
    const displayPhotos = showAllPhotos
        ? photos.filter((p) => p.image_url)
        : photos.filter((p) => p.status === 'SUCCESS' && p.image_url);

    // Use fallback if no multi-photo data
    const hasPhotos = displayPhotos.length > 0;
    const photoList = hasPhotos
        ? displayPhotos
        : fallbackPhotoUrl
        ? [{ id: 0, image_url: fallbackPhotoUrl, status: 'SUCCESS' as const }]
        : [];

    if (photoList.length === 0) {
        // No photos - show placeholder
        return (
            <div
                className={`${SIZE_CLASSES[size]} bg-gray-100 rounded-lg flex items-center justify-center`}
            >
                <ImageIcon size={20} className="text-gray-300" />
            </div>
        );
    }

    const currentPhoto = photoList[currentIndex] || photoList[0];

    // Helper to render mini status badge
    const renderMiniBadge = (status: string) => {
        if (status === 'FAILED') {
            return (
                <div className="absolute top-0.5 left-0.5 bg-red-500 text-white p-0.5 rounded">
                    <AlertCircle size={10} />
                </div>
            );
        }
        if (status === 'CANCELLED') {
            return (
                <div className="absolute top-0.5 left-0.5 bg-gray-500 text-white p-0.5 rounded">
                    <XCircle size={10} />
                </div>
            );
        }
        if (status === 'PROCESSING' || status === 'PENDING') {
            return (
                <div className="absolute top-0.5 left-0.5 bg-blue-500 text-white p-0.5 rounded">
                    <Loader2 size={10} className="animate-spin" />
                </div>
            );
        }
        return null;
    };

    if (photoList.length === 1) {
        // Single photo - show with status badge if needed
        return (
            <div className="relative">
                <img
                    src={currentPhoto.image_url!}
                    alt="Фото еды"
                    className={`${SIZE_CLASSES[size]} object-cover rounded-lg ${
                        currentPhoto.status === 'FAILED' || currentPhoto.status === 'CANCELLED'
                            ? 'opacity-70'
                            : ''
                    }`}
                />
                {renderMiniBadge(currentPhoto.status)}
            </div>
        );
    }

    // Multiple photos - show gallery with navigation
    const goToPrev = (e: React.MouseEvent) => {
        e.stopPropagation();
        setCurrentIndex((prev) => (prev === 0 ? photoList.length - 1 : prev - 1));
    };

    const goToNext = (e: React.MouseEvent) => {
        e.stopPropagation();
        setCurrentIndex((prev) => (prev === photoList.length - 1 ? 0 : prev + 1));
    };

    return (
        <div className="relative group">
            {/* Main image */}
            <img
                src={currentPhoto.image_url!}
                alt={`Фото еды ${currentIndex + 1} из ${photoList.length}`}
                className={`${SIZE_CLASSES[size]} object-cover rounded-lg ${
                    currentPhoto.status === 'FAILED' || currentPhoto.status === 'CANCELLED'
                        ? 'opacity-70'
                        : ''
                }`}
            />

            {/* Status badge */}
            {renderMiniBadge(currentPhoto.status)}

            {/* Photo counter badge */}
            <div className="absolute bottom-0.5 right-0.5 bg-black/60 text-white text-[10px] px-1 rounded">
                {currentIndex + 1}/{photoList.length}
            </div>

            {/* Navigation arrows (visible on hover) */}
            <button
                onClick={goToPrev}
                className="absolute left-0 top-1/2 -translate-y-1/2 bg-black/40 text-white p-0.5 rounded-r opacity-0 group-hover:opacity-100 transition-opacity"
                aria-label="Предыдущее фото"
            >
                <ChevronLeft size={14} />
            </button>
            <button
                onClick={goToNext}
                className="absolute right-0 top-1/2 -translate-y-1/2 bg-black/40 text-white p-0.5 rounded-l opacity-0 group-hover:opacity-100 transition-opacity"
                aria-label="Следующее фото"
            >
                <ChevronRight size={14} />
            </button>
        </div>
    );
};

interface MealPhotoStripProps extends MealPhotoGalleryProps {}

/**
 * Compact photo strip showing all photos in a row.
 * Good for meal cards where space is limited.
 * Shows ALL photos (including FAILED/CANCELLED) with status badges.
 */
export const MealPhotoStrip: React.FC<MealPhotoStripProps> = ({
    photos,
    fallbackPhotoUrl,
    showAllPhotos = true,
}) => {
    // Show all photos with URLs (including FAILED/CANCELLED for sync with details page)
    const allPhotos = showAllPhotos
        ? photos.filter((p) => p.image_url)
        : photos.filter((p) => p.status === 'SUCCESS' && p.image_url);

    // Use fallback if no multi-photo data
    const photoList = allPhotos.length > 0
        ? allPhotos
        : fallbackPhotoUrl
        ? [{ id: 0, image_url: fallbackPhotoUrl, status: 'SUCCESS' as const }]
        : [];

    if (photoList.length === 0) {
        return null;
    }

    // Show up to 3 photos in a strip
    const displayPhotos = photoList.slice(0, 3);
    const remainingCount = photoList.length - displayPhotos.length;

    // Helper to render mini status badge for strip
    const renderStripBadge = (status: string) => {
        if (status === 'FAILED') {
            return (
                <div className="absolute top-0 left-0 bg-red-500 text-white p-0.5 rounded-tl-md rounded-br">
                    <AlertCircle size={8} />
                </div>
            );
        }
        if (status === 'CANCELLED') {
            return (
                <div className="absolute top-0 left-0 bg-gray-500 text-white p-0.5 rounded-tl-md rounded-br">
                    <XCircle size={8} />
                </div>
            );
        }
        if (status === 'PROCESSING' || status === 'PENDING') {
            return (
                <div className="absolute top-0 left-0 bg-blue-500 text-white p-0.5 rounded-tl-md rounded-br">
                    <Loader2 size={8} className="animate-spin" />
                </div>
            );
        }
        return null;
    };

    return (
        <div className="flex items-center gap-1">
            {displayPhotos.map((photo, i) => (
                <div key={photo.id || i} className="relative">
                    <img
                        src={photo.image_url!}
                        alt={`Фото ${i + 1}`}
                        className={`w-10 h-10 object-cover rounded-md ${
                            photo.status === 'FAILED' || photo.status === 'CANCELLED'
                                ? 'opacity-70'
                                : ''
                        }`}
                    />
                    {renderStripBadge(photo.status)}
                </div>
            ))}
            {remainingCount > 0 && (
                <div className="w-10 h-10 bg-gray-100 rounded-md flex items-center justify-center text-xs text-gray-500 font-medium">
                    +{remainingCount}
                </div>
            )}
        </div>
    );
};
