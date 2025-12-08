import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { Home, Camera, CreditCard, User } from 'lucide-react';
import { DebugBanner } from '../features/debug';

/**
 * ClientLayout - Persistent layout wrapper
 * 
 * This component:
 * - Mounts ONCE and stays mounted throughout the app session
 * - Contains DebugBanner (fixed position, no layout reflow)
 * - Contains bottom navigation
 * - Renders page content via <Outlet />
 * 
 * NO artificial delays, overlays or transitions that mask loading states.
 */
const ClientLayout: React.FC = () => {
    return (
        <div className="min-h-screen bg-gray-50 flex flex-col">
            {/* Debug Mode Banner - fixed position, no layout reflow */}
            <DebugBanner />

            <main className="flex-1 pb-16 md:pb-20">
                <Outlet />
            </main>

            {/* Bottom Navigation Bar */}
            <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-6 py-3 pb-[calc(12px+env(safe-area-inset-bottom))] flex justify-between items-center z-50">
                <NavLink
                    to="/"
                    end
                    className={({ isActive }) =>
                        `flex flex-col items-center gap-1 ${isActive ? 'text-blue-600' : 'text-gray-400'}`
                    }
                >
                    <Home size={24} />
                    <span className="text-xs font-medium">Дневник</span>
                </NavLink>

                <NavLink
                    to="/log"
                    className={({ isActive }) =>
                        `flex flex-col items-center gap-1 ${isActive ? 'text-blue-600' : 'text-gray-400'}`
                    }
                >
                    <Camera size={24} />
                    <span className="text-xs font-medium">Камера</span>
                </NavLink>

                <NavLink
                    to="/subscription"
                    className={({ isActive }) =>
                        `flex flex-col items-center gap-1 ${isActive ? 'text-blue-600' : 'text-gray-400'}`
                    }
                >
                    <CreditCard size={24} />
                    <span className="text-xs font-medium">Подписка</span>
                </NavLink>

                <NavLink
                    to="/profile"
                    className={({ isActive }) =>
                        `flex flex-col items-center gap-1 ${isActive ? 'text-blue-600' : 'text-gray-400'}`
                    }
                >
                    <User size={24} />
                    <span className="text-xs font-medium">Профиль</span>
                </NavLink>

                {/* Settings Link - Hidden for normal users */}
                {/* TODO: Implement proper admin check */}
                {false && (
                    <NavLink
                        to="/settings"
                        className={({ isActive }) =>
                            `flex flex-col items-center gap-1 ${isActive ? 'text-blue-600' : 'text-gray-400'}`
                        }
                    >
                        <User size={24} /> {/* Placeholder icon */}
                        <span className="text-xs font-medium">Настройки</span>
                    </NavLink>
                )}
            </nav>
        </div>
    );
};

export default ClientLayout;
