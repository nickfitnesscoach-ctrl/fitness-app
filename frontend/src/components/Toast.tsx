/**
 * F-029: Toast notification component
 * Shows temporary messages for user feedback
 */

import React, { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertCircle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastData {
    id: string;
    type: ToastType;
    message: string;
    duration?: number;
}

interface ToastProps extends ToastData {
    onClose: (id: string) => void;
}

const iconMap = {
    success: CheckCircle,
    error: XCircle,
    warning: AlertCircle,
    info: Info,
};

const colorMap = {
    success: 'bg-green-50 border-green-200 text-green-800',
    error: 'bg-red-50 border-red-200 text-red-800',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
};

const iconColorMap = {
    success: 'text-green-500',
    error: 'text-red-500',
    warning: 'text-yellow-500',
    info: 'text-blue-500',
};

const Toast: React.FC<ToastProps> = ({ id, type, message, duration = 4000, onClose }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [isLeaving, setIsLeaving] = useState(false);

    const Icon = iconMap[type];

    useEffect(() => {
        // Trigger enter animation
        requestAnimationFrame(() => setIsVisible(true));

        // Auto-dismiss
        const timer = setTimeout(() => {
            handleClose();
        }, duration);

        return () => clearTimeout(timer);
    }, [duration]);

    const handleClose = () => {
        setIsLeaving(true);
        setTimeout(() => {
            onClose(id);
        }, 300);
    };

    return (
        <div
            className={`
                transform transition-all duration-300 ease-out
                ${isVisible && !isLeaving ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'}
                flex items-center gap-3 p-4 rounded-xl border shadow-lg
                ${colorMap[type]}
            `}
        >
            <Icon className={`shrink-0 ${iconColorMap[type]}`} size={20} />
            <p className="flex-1 text-sm font-medium">{message}</p>
            <button
                onClick={handleClose}
                className="shrink-0 p-1 hover:bg-black/5 rounded-full transition-colors"
            >
                <X size={16} />
            </button>
        </div>
    );
};

// Toast Container - renders all active toasts
interface ToastContainerProps {
    toasts: ToastData[];
    onClose: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onClose }) => {
    if (toasts.length === 0) return null;

    return (
        <div className="fixed bottom-20 left-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
            {toasts.map((toast) => (
                <div key={toast.id} className="pointer-events-auto">
                    <Toast {...toast} onClose={onClose} />
                </div>
            ))}
        </div>
    );
};

export default Toast;
