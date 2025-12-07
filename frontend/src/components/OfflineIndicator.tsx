/**
 * F-013: Offline indicator component
 * Shows a banner when the user loses internet connection
 */

import React from 'react';
import { WifiOff } from 'lucide-react';
import { useOnlineStatus } from '../hooks/useOnlineStatus';

const OfflineIndicator: React.FC = () => {
    const isOnline = useOnlineStatus();

    if (isOnline) {
        return null;
    }

    return (
        <div className="fixed top-0 left-0 right-0 z-50 bg-red-500 text-white py-2 px-4 flex items-center justify-center gap-2 shadow-lg animate-in slide-in-from-top duration-300">
            <WifiOff size={18} />
            <span className="font-medium text-sm">Нет подключения к интернету</span>
        </div>
    );
};

export default OfflineIndicator;
