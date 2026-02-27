import axios from 'axios';
import type {
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    User,
    UserPreferences,
    ChatRequest,
    ChatResponse,
    Trip,
    ItineraryVersion,
    ConversationHistory,
    TripsListResponse,
    TripsListParams,
    ItinerariesListResponse,
    ItinerariesListParams,
    ItineraryExport,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// JWT interceptor
api.interceptors.request.use((config) => {
    if (typeof window !== 'undefined') {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
    }
    return config;
});

// Response interceptor for 401 handling
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401 && typeof window !== 'undefined') {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_id');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

// ==================== Auth ====================

export const authAPI = {
    register: async (data: RegisterRequest): Promise<User> => {
        const res = await api.post('/auth/register', data);
        return res.data;
    },

    login: async (data: LoginRequest): Promise<AuthResponse> => {
        const res = await api.post('/auth/login', data);
        return res.data;
    },
};

// ==================== Users ====================

export const usersAPI = {
    getMe: async (): Promise<User> => {
        const res = await api.get('/users/me');
        return res.data;
    },

    getPreferences: async (): Promise<UserPreferences> => {
        const res = await api.get('/users/me/preferences');
        return res.data;
    },

    updatePreferences: async (data: Partial<UserPreferences>): Promise<UserPreferences> => {
        const res = await api.patch('/users/me/preferences', data);
        return res.data;
    },
};

// ==================== Trips ====================

export const tripsAPI = {
    chat: async (data: ChatRequest): Promise<ChatResponse> => {
        const res = await api.post('/trips/chat', data);
        return res.data;
    },

    getUserTrips: async (userId: string, params?: TripsListParams): Promise<TripsListResponse> => {
        const res = await api.get(`/trips/user/${userId}`, { params });
        return res.data;
    },

    getUserItineraries: async (userId: string, params?: ItinerariesListParams): Promise<ItinerariesListResponse> => {
        const res = await api.get(`/trips/user/${userId}/itineraries`, { params });
        return res.data;
    },

    getTrip: async (tripId: string): Promise<Trip> => {
        const res = await api.get(`/trips/${tripId}`);
        return res.data;
    },

    getItinerary: async (tripId: string): Promise<ItineraryVersion> => {
        const res = await api.get(`/trips/${tripId}/itinerary`);
        return res.data;
    },

    getConversations: async (tripId: string): Promise<ConversationHistory> => {
        const res = await api.get(`/trips/${tripId}/conversations`);
        return res.data;
    },

    exportItinerary: async (tripId: string, format: 'json' | 'text' = 'json'): Promise<ItineraryExport | { text: string }> => {
        const res = await api.get(`/trips/${tripId}/export`, { params: { format } });
        return res.data;
    },

    downloadItinerary: (tripId: string, format: 'json' | 'text' = 'json'): void => {
        const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
        const headers = token ? `?format=${format}` : `?format=${format}`;
        window.open(`${API_BASE_URL}/trips/${tripId}/export${headers}`, '_blank');
    },
};

export default api;
