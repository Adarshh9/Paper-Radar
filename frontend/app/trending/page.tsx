'use client';

import React, { useState, useEffect } from 'react';
import { TrendingUp, Clock, Zap } from 'lucide-react';
import { Navbar } from '@/components/Navbar';
import { PaperCard, PaperCardSkeleton } from '@/components/PaperCard';
import { fetchTrendingPapers, type PaperListItem } from '@/lib/api';

const TIMEFRAMES = [
    { id: 'day', label: 'Today', icon: Clock },
    { id: 'week', label: 'This Week', icon: TrendingUp },
    { id: 'month', label: 'This Month', icon: Zap },
];

export default function TrendingPage() {
    const [papers, setPapers] = useState<PaperListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [timeframe, setTimeframe] = useState('week');

    useEffect(() => {
        const loadTrending = async () => {
            setLoading(true);
            setError(null);

            try {
                const data = await fetchTrendingPapers(timeframe, 20);
                setPapers(data);
            } catch (err) {
                console.error('Error loading trending papers:', err);
                setError('Failed to load trending papers.');
                // Use empty array if API fails
                setPapers([]);
            } finally {
                setLoading(false);
            }
        };

        loadTrending();
    }, [timeframe]);

    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg">
                        <TrendingUp className="w-6 h-6 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-foreground">Trending Papers</h1>
                </div>
                <p className="text-muted-foreground mb-8">
                    Papers gaining the most traction in the research community
                </p>

                {/* Timeframe Tabs */}
                <div className="flex items-center gap-2 mb-8">
                    {TIMEFRAMES.map((tf) => {
                        const Icon = tf.icon;
                        return (
                            <button
                                key={tf.id}
                                onClick={() => setTimeframe(tf.id)}
                                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${timeframe === tf.id
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                                    }`}
                            >
                                <Icon className="w-4 h-4" />
                                {tf.label}
                            </button>
                        );
                    })}
                </div>

                {/* Error Message */}
                {error && (
                    <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-lg p-4 mb-6">
                        {error}
                    </div>
                )}

                {/* Papers Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {loading
                        ? Array.from({ length: 6 }).map((_, i) => <PaperCardSkeleton key={i} />)
                        : papers.map((paper, index) => (
                            <div key={paper.id} className="relative">
                                {/* Rank Badge */}
                                <div className="absolute -top-2 -left-2 z-10 w-8 h-8 rounded-full bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center text-white font-bold text-sm shadow-lg">
                                    {index + 1}
                                </div>
                                <PaperCard paper={paper} />
                            </div>
                        ))}
                </div>

                {/* Empty State */}
                {!loading && papers.length === 0 && !error && (
                    <div className="text-center py-16">
                        <TrendingUp className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
                        <p className="text-muted-foreground">
                            No trending papers found for this timeframe.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
