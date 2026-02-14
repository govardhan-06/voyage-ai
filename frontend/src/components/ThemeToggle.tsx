'use client';

import { useThemeStore } from '@/stores/themeStore';
import { Sun, Moon } from 'lucide-react';
import { motion } from 'framer-motion';

export default function ThemeToggle() {
    const { theme, toggleTheme } = useThemeStore();

    return (
        <button
            className="btn btn-icon btn-ghost"
            onClick={toggleTheme}
            aria-label="Toggle theme"
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
            <motion.div
                key={theme}
                initial={{ rotate: -90, opacity: 0 }}
                animate={{ rotate: 0, opacity: 1 }}
                exit={{ rotate: 90, opacity: 0 }}
                transition={{ duration: 0.2 }}
            >
                {theme === 'dark' ? (
                    <Sun size={18} style={{ color: 'var(--warning-500)' }} />
                ) : (
                    <Moon size={18} style={{ color: 'var(--primary-400)' }} />
                )}
            </motion.div>
        </button>
    );
}
