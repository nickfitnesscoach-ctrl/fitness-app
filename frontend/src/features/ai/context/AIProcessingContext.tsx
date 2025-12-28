import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import { useFoodBatchAnalysis } from '../hooks/useFoodBatchAnalysis';
import type { PhotoQueueItem, FileWithComment } from '../model';

interface AIProcessingContextType {
    // State
    isProcessing: boolean;
    photoQueue: PhotoQueueItem[];
    showResults: boolean;

    // Helpers
    hasActiveQueue: boolean;
    hasInFlight: boolean;
    allDone: boolean;

    // Actions
    startBatch: (files: FileWithComment[], context: { date: string; mealType: string }) => Promise<void>;
    retryPhoto: (id: string) => void;
    retrySelected: (ids: string[]) => void;
    removePhoto: (id: string) => void;
    cancelBatch: () => void;

    // Cleanup / Results flow
    openResults: () => void;
    closeResults: () => void;
    cleanup: () => void;
}

const AIProcessingContext = createContext<AIProcessingContextType | null>(null);

export const AIProcessingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    // Lift local state that needs to persist across navigation
    const [showResults, setShowResults] = useState(false);

    // Use existing hook for core logic
    const {
        isProcessing,
        photoQueue,
        startBatch: hookStartBatch,
        retryPhoto,
        retrySelected,
        removePhoto,
        cancelBatch,
        cleanup: hookCleanup,
    } = useFoodBatchAnalysis({
        // Callbacks that don't depend on page context can go here if needed
        onDailyLimitReached: () => {
            // We might need a global way to show this modal, or expose an event
            // For now, let's expose the state/event via context if needed, or handle in UI components
            window.dispatchEvent(new CustomEvent('ai:daily-limit-reached'));
        }
    });

    // Derived state
    const hasActiveQueue = photoQueue.length > 0;

    const hasInFlight = useMemo(() => {
        return isProcessing || photoQueue.some(p =>
            ['pending', 'compressing', 'uploading', 'processing', 'retrying'].includes(p.status)
        );
    }, [isProcessing, photoQueue]);

    const allDone = useMemo(() => {
        return photoQueue.length > 0 && photoQueue.every(p =>
            ['success', 'error'].includes(p.status)
        );
    }, [photoQueue]);

    // Enhanced actions
    const startBatch = useCallback(async (files: FileWithComment[], context: { date: string; mealType: string }) => {
        // Reset results view when starting new batch
        setShowResults(false);
        await hookStartBatch(files, context);
    }, [hookStartBatch]);

    const cleanup = useCallback(() => {
        setShowResults(false);
        hookCleanup();
    }, [hookCleanup]);

    const openResults = useCallback(() => setShowResults(true), []);
    const closeResults = useCallback(() => setShowResults(false), []);

    const value = useMemo<AIProcessingContextType>(() => ({
        isProcessing,
        photoQueue,
        showResults,
        hasActiveQueue,
        hasInFlight,
        allDone,
        startBatch,
        retryPhoto,
        retrySelected,
        removePhoto,
        cancelBatch,
        openResults,
        closeResults,
        cleanup
    }), [
        isProcessing,
        photoQueue,
        showResults,
        hasActiveQueue,
        hasInFlight,
        allDone,
        startBatch,
        retryPhoto,
        retrySelected,
        removePhoto,
        cancelBatch,
        openResults,
        closeResults,
        cleanup
    ]);

    return (
        <AIProcessingContext.Provider value={value}>
            {children}
        </AIProcessingContext.Provider>
    );
};

export const useAIProcessing = () => {
    const context = useContext(AIProcessingContext);
    if (!context) {
        throw new Error('useAIProcessing must be used within an AIProcessingProvider');
    }
    return context;
};
