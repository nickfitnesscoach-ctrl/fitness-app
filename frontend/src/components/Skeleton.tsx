/**
 * F-019: Skeleton loader components for better loading UX
 * Provides visual placeholder while content is loading
 */

import React from 'react';

interface SkeletonProps {
    className?: string;
    width?: string | number;
    height?: string | number;
    rounded?: 'none' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full';
}

const roundedClasses = {
    none: 'rounded-none',
    sm: 'rounded-sm',
    md: 'rounded-md',
    lg: 'rounded-lg',
    xl: 'rounded-xl',
    '2xl': 'rounded-2xl',
    full: 'rounded-full',
};

export const Skeleton: React.FC<SkeletonProps> = ({
    className = '',
    width,
    height,
    rounded = 'md',
}) => {
    const style: React.CSSProperties = {};
    if (width) style.width = typeof width === 'number' ? `${width}px` : width;
    if (height) style.height = typeof height === 'number' ? `${height}px` : height;

    return (
        <div
            className={`animate-pulse bg-gray-200 ${roundedClasses[rounded]} ${className}`}
            style={style}
        />
    );
};

// Card skeleton for meal cards, stats cards etc.
export const SkeletonCard: React.FC<{ className?: string }> = ({ className = '' }) => (
    <div className={`bg-white rounded-2xl p-4 shadow-sm ${className}`}>
        <div className="flex items-center gap-3 mb-3">
            <Skeleton width={48} height={48} rounded="xl" />
            <div className="flex-1">
                <Skeleton height={16} width="60%" className="mb-2" />
                <Skeleton height={12} width="40%" />
            </div>
        </div>
        <Skeleton height={12} width="80%" className="mb-2" />
        <Skeleton height={12} width="60%" />
    </div>
);

// Meal card skeleton
export const SkeletonMealCard: React.FC = () => (
    <div className="bg-white rounded-2xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
                <Skeleton width={40} height={40} rounded="lg" />
                <div>
                    <Skeleton height={16} width={80} className="mb-1" />
                    <Skeleton height={12} width={50} />
                </div>
            </div>
            <Skeleton width={24} height={24} rounded="md" />
        </div>
        <div className="flex gap-4">
            <Skeleton height={12} width={60} />
            <Skeleton height={12} width={60} />
            <Skeleton height={12} width={60} />
        </div>
    </div>
);

// Stats/Progress skeleton
export const SkeletonProgress: React.FC = () => (
    <div className="bg-white rounded-2xl p-4 shadow-sm">
        <div className="flex justify-between items-center mb-3">
            <Skeleton height={20} width={120} />
            <Skeleton height={16} width={60} />
        </div>
        <Skeleton height={8} rounded="full" className="mb-4" />
        <div className="grid grid-cols-4 gap-2">
            {[1, 2, 3, 4].map((i) => (
                <div key={i} className="text-center">
                    <Skeleton height={24} width={40} className="mx-auto mb-1" />
                    <Skeleton height={10} width={30} className="mx-auto" />
                </div>
            ))}
        </div>
    </div>
);

// Food item skeleton
export const SkeletonFoodItem: React.FC = () => (
    <div className="flex items-center gap-3 py-3 border-b border-gray-100 last:border-0">
        <Skeleton width={56} height={56} rounded="xl" />
        <div className="flex-1">
            <Skeleton height={16} width="70%" className="mb-2" />
            <Skeleton height={12} width="40%" />
        </div>
        <Skeleton height={16} width={50} />
    </div>
);

// Profile avatar skeleton
export const SkeletonAvatar: React.FC<{ size?: number }> = ({ size = 80 }) => (
    <Skeleton width={size} height={size} rounded="full" />
);

// Text line skeleton
export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({
    lines = 3,
    className = '',
}) => (
    <div className={className}>
        {Array.from({ length: lines }).map((_, i) => (
            <Skeleton
                key={i}
                height={12}
                width={i === lines - 1 ? '60%' : '100%'}
                className="mb-2 last:mb-0"
            />
        ))}
    </div>
);

// Meals list skeleton - only for the meals area (not full dashboard)
export const SkeletonMealsList: React.FC = () => (
    <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
        <div className="flex items-center justify-between mb-4">
            <Skeleton height={20} width={100} />
            <Skeleton height={16} width={80} />
        </div>
        <div className="space-y-3">
            <SkeletonMealCard />
            <SkeletonMealCard />
            <SkeletonMealCard />
        </div>
    </div>
);

// Dashboard skeleton (full page)
export const SkeletonDashboard: React.FC = () => (
    <div className="space-y-4 p-4">
        {/* Calendar placeholder */}
        <Skeleton height={60} rounded="2xl" />

        {/* Progress card */}
        <SkeletonProgress />

        {/* Meals */}
        <div className="space-y-3">
            <Skeleton height={20} width={100} className="mb-2" />
            <SkeletonMealCard />
            <SkeletonMealCard />
            <SkeletonMealCard />
        </div>
    </div>
);

// Meal details skeleton
export const SkeletonMealDetails: React.FC = () => (
    <div className="space-y-4 p-4">
        {/* Photo */}
        <Skeleton height={200} rounded="2xl" />

        {/* Title and stats */}
        <div className="flex justify-between items-center">
            <Skeleton height={24} width={120} />
            <Skeleton height={16} width={80} />
        </div>

        {/* Nutrition summary */}
        <div className="grid grid-cols-4 gap-2">
            {[1, 2, 3, 4].map((i) => (
                <div key={i} className="bg-white rounded-xl p-3">
                    <Skeleton height={20} width={40} className="mx-auto mb-1" />
                    <Skeleton height={10} width={30} className="mx-auto" />
                </div>
            ))}
        </div>

        {/* Food items */}
        <div className="bg-white rounded-2xl p-4">
            <Skeleton height={18} width={150} className="mb-4" />
            <SkeletonFoodItem />
            <SkeletonFoodItem />
            <SkeletonFoodItem />
        </div>
    </div>
);

export default Skeleton;
