'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import ThemeToggle from './ThemeToggle';
import { Compass, Home, MessageSquare, User, LogOut, Menu, X } from 'lucide-react';
import { useState } from 'react';
import styles from './Navbar.module.css';

export default function Navbar() {
    const { isAuthenticated, user, logout } = useAuthStore();
    const pathname = usePathname();
    const router = useRouter();
    const [mobileOpen, setMobileOpen] = useState(false);

    const handleLogout = () => {
        logout();
        router.push('/login');
    };

    // Hide navbar on auth pages
    if (['/login', '/signup', '/'].includes(pathname)) return null;

    return (
        <nav className={styles.navbar}>
            <div className={styles.navContent}>
                <Link href="/dashboard" className={styles.logo}>
                    <Compass size={28} className={styles.logoIcon} />
                    <span className={styles.logoText}>Voyage<span className={styles.logoAccent}>AI</span></span>
                </Link>

                <div className={`${styles.navLinks} ${mobileOpen ? styles.navLinksOpen : ''}`}>
                    <Link
                        href="/dashboard"
                        className={`${styles.navLink} ${pathname === '/dashboard' ? styles.navLinkActive : ''}`}
                        onClick={() => setMobileOpen(false)}
                    >
                        <Home size={18} />
                        <span>Dashboard</span>
                    </Link>
                    <Link
                        href="/chat"
                        className={`${styles.navLink} ${pathname === '/chat' ? styles.navLinkActive : ''}`}
                        onClick={() => setMobileOpen(false)}
                    >
                        <MessageSquare size={18} />
                        <span>Plan Trip</span>
                    </Link>
                    <Link
                        href="/preferences"
                        className={`${styles.navLink} ${pathname === '/preferences' ? styles.navLinkActive : ''}`}
                        onClick={() => setMobileOpen(false)}
                    >
                        <User size={18} />
                        <span>Preferences</span>
                    </Link>
                </div>

                <div className={styles.navActions}>
                    <ThemeToggle />
                    {isAuthenticated && (
                        <div className={styles.userMenu}>
                            <div className={styles.userAvatar}>
                                {user?.name?.charAt(0).toUpperCase() || 'U'}
                            </div>
                            <button className="btn btn-ghost btn-sm" onClick={handleLogout}>
                                <LogOut size={16} />
                                <span className={styles.logoutText}>Logout</span>
                            </button>
                        </div>
                    )}
                    <button
                        className={`${styles.menuToggle} btn btn-icon btn-ghost`}
                        onClick={() => setMobileOpen(!mobileOpen)}
                    >
                        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
                    </button>
                </div>
            </div>
        </nav>
    );
}
