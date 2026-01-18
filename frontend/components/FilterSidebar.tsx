'use client';

import React, { useState } from 'react';
import { Filter, X, Calendar, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFilterStore } from '@/stores';

// Category groups for better organization
const CATEGORY_GROUPS = [
    {
        name: 'Core AI/ML',
        categories: [
            { id: 'cs.AI', name: 'Artificial Intelligence', color: 'bg-purple-500' },
            { id: 'cs.LG', name: 'Machine Learning', color: 'bg-blue-500' },
            { id: 'cs.CV', name: 'Computer Vision', color: 'bg-green-500' },
            { id: 'cs.CL', name: 'NLP & Language', color: 'bg-orange-500' },
            { id: 'cs.NE', name: 'Neural & Evolutionary', color: 'bg-pink-500' },
            { id: 'stat.ML', name: 'Statistics ML', color: 'bg-cyan-500' },
        ]
    },
    {
        name: 'Related CS',
        categories: [
            { id: 'cs.RO', name: 'Robotics', color: 'bg-red-500' },
            { id: 'cs.HC', name: 'Human-Computer Interaction', color: 'bg-amber-500' },
            { id: 'cs.IR', name: 'Information Retrieval', color: 'bg-teal-500' },
            { id: 'cs.SE', name: 'Software Engineering', color: 'bg-indigo-500' },
            { id: 'cs.CR', name: 'Security & Crypto', color: 'bg-rose-500' },
            { id: 'cs.DC', name: 'Distributed Computing', color: 'bg-violet-500' },
            { id: 'cs.DB', name: 'Databases', color: 'bg-lime-500' },
            { id: 'cs.PL', name: 'Programming Languages', color: 'bg-fuchsia-500' },
        ]
    },
    {
        name: 'Emerging',
        categories: [
            { id: 'cs.MA', name: 'Multiagent Systems', color: 'bg-sky-500' },
            { id: 'cs.SI', name: 'Social Networks', color: 'bg-emerald-500' },
            { id: 'cs.CY', name: 'Computers & Society', color: 'bg-yellow-500' },
            { id: 'cs.GT', name: 'Game Theory', color: 'bg-stone-500' },
        ]
    }
];

// Flatten for easier lookup
const ALL_CATEGORIES = CATEGORY_GROUPS.flatMap(g => g.categories);

const SORT_OPTIONS = [
    { id: 'rank_score', name: 'Trending', description: 'By our radar score' },
    { id: 'published_date', name: 'Newest', description: 'Most recent first' },
    { id: 'citations', name: 'Most Cited', description: 'By citation count' },
];

const TIME_FILTERS = [
    { id: 'week', name: 'This Week', days: 7 },
    { id: 'month', name: 'This Month', days: 30 },
    { id: 'quarter', name: 'Last 3 Months', days: 90 },
    { id: 'half_year', name: 'Last 6 Months', days: 180 },
    { id: 'year', name: 'Last 1 Year', days: 365 },
];

interface FilterSidebarProps {
    onClose?: () => void;
    className?: string;
}

export function FilterSidebar({ onClose, className }: FilterSidebarProps) {
    const [expandedGroups, setExpandedGroups] = useState<string[]>(['Core AI/ML']);
    
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

    const toggleGroup = (groupName: string) => {
        setExpandedGroups(prev => 
            prev.includes(groupName) 
                ? prev.filter(g => g !== groupName)
                : [...prev, groupName]
        );
    };

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

            {/* Categories - Grouped & Collapsible */}
            <div className="mb-6">
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Categories</h4>
                <div className="space-y-3">
                    {CATEGORY_GROUPS.map((group) => (
                        <div key={group.name}>
                            <button
                                onClick={() => toggleGroup(group.name)}
                                className="w-full flex items-center justify-between text-xs font-medium text-muted-foreground mb-2 hover:text-foreground transition-colors"
                            >
                                <span>{group.name}</span>
                                {expandedGroups.includes(group.name) ? (
                                    <ChevronUp className="w-3 h-3" />
                                ) : (
                                    <ChevronDown className="w-3 h-3" />
                                )}
                            </button>
                            {expandedGroups.includes(group.name) && (
                                <div className="space-y-1.5">
                                    {group.categories.map((cat) => (
                                        <button
                                            key={cat.id}
                                            onClick={() => setCategory(category === cat.id ? null : cat.id)}
                                            className={cn(
                                                'w-full flex items-center gap-2 px-3 py-2 text-xs rounded-lg transition-colors',
                                                category === cat.id
                                                    ? 'bg-primary text-primary-foreground'
                                                    : 'bg-secondary hover:bg-secondary/80'
                                            )}
                                        >
                                            <div className={cn('w-2 h-2 rounded-full flex-shrink-0', cat.color)} />
                                            <span className="truncate">{cat.name}</span>
                                            <span className="ml-auto text-[10px] opacity-60">{cat.id}</span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
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
