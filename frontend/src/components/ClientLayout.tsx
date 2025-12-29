import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { Home, Camera, CreditCard, User } from 'lucide-react';

/**
 * ClientLayout - Persistent layout wrapper
 *
 * This component:
 * - Mounts ONCE and stays mounted throughout the app session
 * - Contains bottom navigation
 * - Renders page content via <Outlet />
 *
 * NO artificial delays, overlays or transitions that mask loading states.
 */
const ClientLayout: React.FC = () => {
    return (
        <div className="min-h-screen bg-gray-50 flex flex-col">
            <main className="flex-1" style={{ paddingBottom: 'calc(var(--tap-h) + var(--safe-bottom) + 12px)' }}>
                <Outlet />
            </main>

            {/* Bottom Navigation Bar */}
            <nav
                className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur-sm border-t border-gray-100 flex justify-between items-center z-50 px-page"
                style={{
                    paddingBottom: 'var(--safe-bottom)',
                    height: 'calc(var(--tap-h) + var(--safe-bottom) + 12px)',
                }}
            >
                <NavLink
                    to="/"
                    end
                    className={({ isActive }) =>
                        `flex-1 flex flex-col items-center justify-center gap-1 h-full transition-colors ${isActive ? 'text-blue-600' : 'text-gray-400'}`
                    }
                >
                    <Home size={22} />
                    <span className="text-[10px] font-semibold uppercase tracking-wider">Дневник</span>
                </NavLink>

                <NavLink
                    to="/log"
                    className={({ isActive }) =>
                        `flex-1 flex flex-col items-center justify-center gap-1 h-full transition-colors ${isActive ? 'text-blue-600' : 'text-gray-400'}`
                    }
                >
                    <Camera size={22} />
                    <span className="text-[10px] font-semibold uppercase tracking-wider">Камера</span>
                </NavLink>

                <NavLink
                    to="/subscription"
                    className={({ isActive }) =>
                        `flex-1 flex flex-col items-center justify-center gap-1 h-full transition-colors ${isActive ? 'text-blue-600' : 'text-gray-400'}`
                    }
                >
                    <CreditCard size={22} />
                    <span className="text-[10px] font-semibold uppercase tracking-wider">Тариф</span>
                </NavLink>

                <NavLink
                    to="/profile"
                    className={({ isActive }) =>
                        `flex-1 flex flex-col items-center justify-center gap-1 h-full transition-colors ${isActive ? 'text-blue-600' : 'text-gray-400'}`
                    }
                >
                    <User size={22} />
                    <span className="text-[10px] font-semibold uppercase tracking-wider">Профиль</span>
                </NavLink>
            </nav>
        </div>
    );
};

export default ClientLayout;
