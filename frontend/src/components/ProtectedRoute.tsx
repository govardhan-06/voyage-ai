'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';

const PUBLIC_ROUTES = ['/login', '/signup', '/'];

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading } = useAuthStore();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        if (!isLoading && !isAuthenticated && !PUBLIC_ROUTES.includes(pathname)) {
            router.push('/login');
        }
    }, [isAuthenticated, isLoading, pathname, router]);

    if (isLoading) {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100vh',
                background: 'var(--bg-primary)',
            }}>
                <div className="loading-spinner" />
            </div>
        );
    }

    if (!isAuthenticated && !PUBLIC_ROUTES.includes(pathname)) {
        return null;
    }

    return <>{children}</>;
}
