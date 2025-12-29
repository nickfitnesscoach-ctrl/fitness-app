import React from 'react';

interface PageContainerProps {
    children: React.ReactNode;
    className?: string;
    /** Whether to add top safe area padding */
    withSafeTop?: boolean;
}

/**
 * Standard container for all app pages.
 * Ensures consistent horizontal padding using design tokens
 * and handles safe area insets.
 */
export const PageContainer: React.FC<PageContainerProps> = ({
    children,
    className = '',
    withSafeTop = false,
}) => {
    return (
        <div
            className={`px-page w-full max-w-2xl mx-auto ${className}`}
            style={{
                paddingTop: withSafeTop ? 'var(--safe-top)' : undefined,
            }}
        >
            {children}
        </div>
    );
};
