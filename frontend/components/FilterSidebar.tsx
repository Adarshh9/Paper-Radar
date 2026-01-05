'use client';

import React from 'react';
import { Filter, X, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFilterStore } from '@/stores';

const CATEGORIES = [
    { id: 'cs.AI', name: 'Artificial Intelligence', color: 'bg-purple-500' },
    { id: 'cs.LG', name: 'Machine Learning', color: 'bg-blue-500' },
    { id: 'cs.CV', name: 'Computer Vision', color: 'bg-green-500' },
    { id: 'cs.CL', name: 'Computation & Language', color: 'bg-orange-500' },
    { id: 'cs.NE', name: 'Neural & Evolutionary', color: 'bg-pink-500' },
    { id: 'stat.ML', name: 'Statistics ML', color: 'bg-cyan-500' },
];

const SORT_OPTIONS = [
    { id: 'rank_score', name: 'Trending', description: 'By our radar score' },
    { id: 'published_date', name: 'Newest', description: 'Most recent first' },
    { id: 'citations', name: 'Most Cited', description: 'By citation count' },
];

const TIME_FILTERS = [
    { id: 'today', name: 'Today', days: 1 },
    { id: 'week', name: 'This Week', days: 7 },
    { id: 'month', name: 'This Month', days: 30 },
    { id: 'quarter', name: 'Last 3 Months', days: 90 },
    { id: 'all', name: 'All Time', days: null },
];

interface FilterSidebarProps {
    onClose?: () => void;
    className?: string;
}

export function FilterSidebar({ onClose, className }: FilterSidebarProps) {
    const {
        category,
        sortBy,
        hasImplementation,
        dateRange,
        setCategory,
        setSortBy,
        setHasImplementation,
        setDateRange,
        resetFilters,
    } = useFilterStore();

    return (
        <div className={cn('bg-card border border-border rounded-xl p-5', className)}>
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-primary" />
                    <h3 className="font-semibold text-foreground">Filters</h3>
                </div>
                {onClose && (
                    <button onClick={onClose} className="md:hidden">
                        <X className="w-5 h-5" />
                    </button>
                )}
            </div>

            {/* Sort By */}
            <div className="mb-6">
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Sort By</h4>
                <div className="space-y-2">
                    {SORT_OPTIONS.map((option) => (
                        <button
                            key={option.id}
                            onClick={() => setSortBy(option.id)}
                            className={cn(
                                'w-full text-left px-3 py-2 text-sm rounded-lg transition-colors',
                                sortBy === option.id
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-secondary hover:bg-secondary/80'
                            )}
                        >
                            <div className="font-medium">{option.name}</div>
                            <div className={cn(
                                'text-xs',
                                sortBy === option.id ? 'text-primary-foreground/80' : 'text-muted-foreground'
                            )}>
                                {option.description}
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* Time Filter */}
            <div className="mb-6">
                <h4 className="text-sm font-medium text-muted-foreground mb-3 flex items-center gap-2">
                    <Calendar className="w-3 h-3" />
                    Time Range
                </h4>
                <div className="flex flex-wrap gap-2">
                    {TIME_FILTERS.map((tf) => (
                        <button
                            key={tf.id}
                            onClick={() => setDateRange(tf.id)}
                            className={cn(
                                'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
                                dateRange === tf.id
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-secondary hover:bg-secondary/80'
                            )}
                        >
                            {tf.name}
                        </button>
                    ))}
                </div>
            </div>

            {/* Categories */}
            <div className="mb-6">
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Categories</h4>
                <div className="space-y-2">
                    {CATEGORIES.map((cat) => (
                        <button
                            key={cat.id}
                            onClick={() => setCategory(category === cat.id ? null : cat.id)}
                            className={cn(
                                'w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors',
                                category === cat.id
                                    ? 'bg-primary text-primary-foreground'
                                    : 'bg-secondary hover:bg-secondary/80'
                            )}
                        >
                            <div className={cn('w-2 h-2 rounded-full', cat.color)} />
                            {cat.name}
                        </button>
                    ))}
                </div>
            </div>

            {/* Has Implementation */}
            <div className="mb-6">
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Implementation</h4>
                <button
                    onClick={() => setHasImplementation(hasImplementation === true ? null : true)}
                    className={cn(
                        'w-full text-left px-3 py-2 text-sm rounded-lg transition-colors',
                        hasImplementation === true
                            ? 'bg-green-500 text-white'
                            : 'bg-secondary hover:bg-secondary/80'
                    )}
                >
                    ✓ Has Code Available
                </button>
            </div>

            {/* Reset */}
            <button
                onClick={resetFilters}
                className="w-full text-center px-3 py-2 text-sm text-muted-foreground hover:text-foreground border border-border rounded-lg transition-colors"
            >
                Reset Filters
            </button>
        </div>
    );
}
