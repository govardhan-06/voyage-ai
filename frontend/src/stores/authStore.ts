import { create } from 'zustand';
import type { User } from '@/types';
import { authAPI, usersAPI } from '@/lib/api';

interface AuthState {
    user: User | null;
    token: string | null;
    userId: string | null;
    isLoading: boolean;
    isAuthenticated: boolean;

    login: (email: string, password: string) => Promise<void>;
    register: (name: string, email: string, password: string) => Promise<void>;
    logout: () => void;
    fetchUser: () => Promise<void>;
    initialize: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
    user: null,
    token: null,
    userId: null,
    isLoading: true,
    isAuthenticated: false,

    login: async (email: string, password: string) => {
        const res = await authAPI.login({ email, password });
        localStorage.setItem('access_token', res.access_token);
        localStorage.setItem('user_id', res.user_id);
        set({ token: res.access_token, userId: res.user_id, isAuthenticated: true });
        await get().fetchUser();
    },

    register: async (name: string, email: string, password: string) => {
        await authAPI.register({ email, name, password });
        // Auto-login after registration
        await get().login(email, password);
    },

    logout: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_id');
        set({ user: null, token: null, userId: null, isAuthenticated: false });
    },

    fetchUser: async () => {
        try {
            const user = await usersAPI.getMe();
            set({ user, isAuthenticated: true });
        } catch {
            set({ user: null, isAuthenticated: false });
        }
    },

    initialize: async () => {
        const token = localStorage.getItem('access_token');
        const userId = localStorage.getItem('user_id');
        if (token && userId) {
            set({ token, userId, isAuthenticated: true });
            try {
                await get().fetchUser();
            } catch {
                get().logout();
            }
        }
        set({ isLoading: false });
    },
}));
