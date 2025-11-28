import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

interface PageHeaderProps {
    title: string;
    showBack?: boolean;
    onBack?: () => void;
    fallbackRoute?: string;
}

const PageHeader: React.FC<PageHeaderProps> = ({
    title,
    showBack = true,
    onBack,
    fallbackRoute = '/'
}) => {
    const navigate = useNavigate();

    const handleBack = () => {
        if (onBack) {
            onBack();
            return;
        }

        // Check if there is a previous entry in the history stack
        // window.history.state.idx > 0 is a common way to check in React Router v6
        // However, it's not always reliable across all environments.
        // A simpler heuristic: if key is 'default', it might be the first page.
        // But let's stick to the user's requirement: "First action is always goBack".
        // "If opened as first screen (no previous screen)... lead to logical root".

        if (window.history.length > 1 && window.history.state?.idx > 0) {
            navigate(-1);
        } else {
            navigate(fallbackRoute);
        }
    };

    return (
        <div className="bg-white px-4 py-3 flex items-center gap-3 shadow-sm sticky top-0 z-10">
            {showBack && (
                <button
                    onClick={handleBack}
                    className="w-11 h-11 flex items-center justify-center -ml-2 text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
                    aria-label="Назад"
                >
                    <ArrowLeft size={24} />
                </button>
            )}
            <h1 className="text-xl font-bold text-gray-900">{title}</h1>
        </div>
    );
};

export default PageHeader;
