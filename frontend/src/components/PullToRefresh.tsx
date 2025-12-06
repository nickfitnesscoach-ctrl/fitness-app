/**
 * F-033: Pull-to-refresh component for mobile UX
 * Provides native-like pull-down gesture to refresh content
 */

import React, { useState, useRef, useCallback, ReactNode } from 'react';
import { RefreshCw } from 'lucide-react';

interface PullToRefreshProps {
    children: ReactNode;
    onRefresh: () => Promise<void>;
    disabled?: boolean;
    pullThreshold?: number; // pixels to pull before triggering refresh
    maxPull?: number; // maximum pull distance
}

const PullToRefresh: React.FC<PullToRefreshProps> = ({
    children,
    onRefresh,
    disabled = false,
    pullThreshold = 80,
    maxPull = 120,
}) => {
    const [pullDistance, setPullDistance] = useState(0);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [isPulling, setIsPulling] = useState(false);
    
    const containerRef = useRef<HTMLDivElement>(null);
    const startYRef = useRef<number>(0);
    const currentYRef = useRef<number>(0);

    const handleTouchStart = useCallback((e: React.TouchEvent) => {
        if (disabled || isRefreshing) return;
        
        // Only start pull if at top of scroll
        const container = containerRef.current;
        if (!container || container.scrollTop > 0) return;
        
        startYRef.current = e.touches[0].clientY;
        setIsPulling(true);
    }, [disabled, isRefreshing]);

    const handleTouchMove = useCallback((e: React.TouchEvent) => {
        if (!isPulling || disabled || isRefreshing) return;
        
        currentYRef.current = e.touches[0].clientY;
        const diff = currentYRef.current - startYRef.current;
        
        if (diff > 0) {
            // Apply resistance - pull gets harder as you go
            const resistance = 0.5;
            const pull = Math.min(diff * resistance, maxPull);
            setPullDistance(pull);
            
            // Prevent scroll while pulling
            if (pull > 10) {
                e.preventDefault();
            }
        }
    }, [isPulling, disabled, isRefreshing, maxPull]);

    const handleTouchEnd = useCallback(async () => {
        if (!isPulling) return;
        
        setIsPulling(false);
        
        if (pullDistance >= pullThreshold && !isRefreshing) {
            // Trigger refresh
            setIsRefreshing(true);
            setPullDistance(60); // Keep indicator visible during refresh
            
            try {
                await onRefresh();
            } catch (error) {
                console.error('Refresh failed:', error);
            } finally {
                setIsRefreshing(false);
                setPullDistance(0);
            }
        } else {
            // Snap back
            setPullDistance(0);
        }
    }, [isPulling, pullDistance, pullThreshold, isRefreshing, onRefresh]);

    const progress = Math.min(pullDistance / pullThreshold, 1);
    const rotation = progress * 180;
    const shouldTrigger = pullDistance >= pullThreshold;

    return (
        <div
            ref={containerRef}
            className="relative overflow-auto h-full"
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
            onTouchCancel={handleTouchEnd}
        >
            {/* Pull indicator */}
            <div
                className="absolute left-0 right-0 flex justify-center items-center pointer-events-none z-10 transition-transform"
                style={{
                    transform: `translateY(${pullDistance - 50}px)`,
                    opacity: pullDistance > 10 ? 1 : 0,
                }}
            >
                <div
                    className={`
                        w-10 h-10 rounded-full flex items-center justify-center
                        shadow-lg transition-colors
                        ${shouldTrigger || isRefreshing ? 'bg-blue-500 text-white' : 'bg-white text-gray-500'}
                    `}
                >
                    <RefreshCw
                        size={20}
                        className={isRefreshing ? 'animate-spin' : ''}
                        style={{
                            transform: isRefreshing ? 'none' : `rotate(${rotation}deg)`,
                            transition: isPulling ? 'none' : 'transform 0.2s',
                        }}
                    />
                </div>
            </div>

            {/* Content with pull transform */}
            <div
                className="transition-transform"
                style={{
                    transform: `translateY(${pullDistance}px)`,
                    transition: isPulling ? 'none' : 'transform 0.3s ease-out',
                }}
            >
                {children}
            </div>
        </div>
    );
};

export default PullToRefresh;
