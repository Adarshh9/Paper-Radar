import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
    id: string;
    email: string;
    full_name?: string;
}

interface AuthState {
    user: User | null;
    isAuthenticated: boolean;
    setUser: (user: User | null) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            user: null,
            isAuthenticated: false,
            setUser: (user) => set({ user, isAuthenticated: !!user }),
            logout: () => {
                localStorage.removeItem('token');
                set({ user: null, isAuthenticated: false });
            },
        }),
        {
            name: 'auth-store',
        }
    )
);

// Time range to days mapping
const TIME_RANGE_DAYS: Record<string, number | null> = {
    today: 1,
    week: 7,
    month: 30,
    quarter: 90,
    all: null,
};

interface FilterState {
    category: string | null;
    sortBy: string;
    hasImplementation: boolean | null;
    dateRange: string; // 'today' | 'week' | 'month' | 'quarter' | 'all'
    setCategory: (category: string | null) => void;
    setSortBy: (sortBy: string) => void;
    setHasImplementation: (value: boolean | null) => void;
    setDateRange: (range: string) => void;
    resetFilters: () => void;
    // Computed getters
    getDateFrom: () => string | undefined;
}

export const useFilterStore = create<FilterState>((set, get) => ({
    category: null,
    sortBy: 'rank_score',
    hasImplementation: null,
    dateRange: 'week', // Default to this week
    setCategory: (category) => set({ category }),
    setSortBy: (sortBy) => set({ sortBy }),
    setHasImplementation: (hasImplementation) => set({ hasImplementation }),
    setDateRange: (dateRange) => set({ dateRange }),
    resetFilters: () => set({
        category: null,
        sortBy: 'rank_score',
        hasImplementation: null,
        dateRange: 'week',
    }),
    getDateFrom: () => {
        const days = TIME_RANGE_DAYS[get().dateRange];
        if (days === null) return undefined;
        const date = new Date();
        date.setDate(date.getDate() - days);
        return date.toISOString().split('T')[0];
    },
}));
