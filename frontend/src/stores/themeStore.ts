import { create } from 'zustand';

type Theme = 'light' | 'dark';

interface ThemeState {
    theme: Theme;
    toggleTheme: () => void;
    initialize: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
    theme: 'light',

    toggleTheme: () => {
        const newTheme = get().theme === 'dark' ? 'light' : 'dark';
        set({ theme: newTheme });
        localStorage.setItem('theme', newTheme);
        document.documentElement.setAttribute('data-theme', newTheme);
    },

    initialize: () => {
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('theme') as Theme | null;
            const theme = saved || 'light';
            set({ theme });
            document.documentElement.setAttribute('data-theme', theme);
        }
    },
}));
