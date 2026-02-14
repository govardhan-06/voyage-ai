'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useThemeStore } from '@/stores/themeStore';
import Navbar from '@/components/Navbar';
import ProtectedRoute from '@/components/ProtectedRoute';

export default function ClientLayout({ children }: { children: React.ReactNode }) {
    const initialize = useAuthStore((s) => s.initialize);
    const initTheme = useThemeStore((s) => s.initialize);

    useEffect(() => {
        initialize();
        initTheme();
    }, [initialize, initTheme]);

    return (
        <ProtectedRoute>
            <Navbar />
            <main>{children}</main>
        </ProtectedRoute>
    );
}
