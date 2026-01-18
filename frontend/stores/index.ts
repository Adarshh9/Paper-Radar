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
    week: 7,
    month: 30,
    quarter: 90,
    half_year: 180,
    year: 365,
};

interface FilterState {
    category: string | null;
    sortBy: string;
    hasImplementation: boolean | null;
    dateRange: string; // 'week' | 'month' | 'quarter' | 'half_year' | 'year'
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
    dateRange: 'quarter', // Default to last 3 months
    setCategory: (category) => set({ category }),
    setSortBy: (sortBy) => set({ sortBy }),
    setHasImplementation: (hasImplementation) => set({ hasImplementation }),
    setDateRange: (dateRange) => set({ dateRange }),
    resetFilters: () => set({
        category: null,
        sortBy: 'rank_score',
        hasImplementation: null,
        dateRange: 'quarter',
    }),
    getDateFrom: () => {
        const days = TIME_RANGE_DAYS[get().dateRange];
        if (days === null || days === undefined) return undefined;
        const date = new Date();
        date.setHours(0, 0, 0, 0);
        date.setDate(date.getDate() - days);
        return date.toISOString().split('T')[0];
    },
}));
