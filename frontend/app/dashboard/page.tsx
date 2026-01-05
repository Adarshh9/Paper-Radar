'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Bookmark, Settings, TrendingUp } from 'lucide-react';
import { Navbar } from '@/components/Navbar';
import { PaperCard, PaperCardSkeleton } from '@/components/PaperCard';
import { getSavedPapers, fetchRecommendations, unsavePaper, type PaperListItem } from '@/lib/api';
import { useAuthStore } from '@/stores';

export default function DashboardPage() {
    const router = useRouter();
    const { isAuthenticated, user } = useAuthStore();

    const [activeTab, setActiveTab] = useState<'feed' | 'saved' | 'settings'>('feed');
    const [papers, setPapers] = useState<PaperListItem[]>([]);
    const [savedPapers, setSavedPapers] = useState<PaperListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [savedIds, setSavedIds] = useState<Set<string>>(new Set());

    // Redirect if not authenticated
    useEffect(() => {
        if (!isAuthenticated) {
            router.push('/auth/login');
        }
    }, [isAuthenticated, router]);

    // Load data
    useEffect(() => {
        const loadData = async () => {
            if (!isAuthenticated) return;

            setLoading(true);
            try {
                if (activeTab === 'feed') {
                    const recommendations = await fetchRecommendations(20);
                    setPapers(recommendations);
                } else if (activeTab === 'saved') {
                    const saved = await getSavedPapers();
                    setSavedPapers(saved);
                    setSavedIds(new Set(saved.map((p) => p.id)));
                }
            } catch (err) {
                console.error('Error loading data:', err);
            } finally {
                setLoading(false);
            }
        };

        loadData();
    }, [activeTab, isAuthenticated]);

    const handleUnsave = async (paperId: string) => {
        try {
            await unsavePaper(paperId);
            setSavedPapers((prev) => prev.filter((p) => p.id !== paperId));
            setSavedIds((prev) => {
                const next = new Set(prev);
                next.delete(paperId);
                return next;
            });
        } catch (err) {
            console.error('Error unsaving paper:', err);
        }
    };

    if (!isAuthenticated) {
        return null;
    }

    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="mb-8">
                    <h1 className="text-2xl font-bold text-foreground">
                        Welcome back, {user?.full_name || user?.email?.split('@')[0]}
                    </h1>
                    <p className="text-muted-foreground">
                        Your personalized research dashboard
                    </p>
                </div>

                {/* Tabs */}
                <div className="flex items-center gap-1 bg-secondary rounded-lg p-1 mb-8 w-fit">
                    <button
                        onClick={() => setActiveTab('feed')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'feed'
                                ? 'bg-background text-foreground shadow-sm'
                                : 'text-muted-foreground hover:text-foreground'
                            }`}
                    >
                        <TrendingUp className="w-4 h-4" />
                        For You
                    </button>
                    <button
                        onClick={() => setActiveTab('saved')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'saved'
                                ? 'bg-background text-foreground shadow-sm'
                                : 'text-muted-foreground hover:text-foreground'
                            }`}
                    >
                        <Bookmark className="w-4 h-4" />
                        Saved
                    </button>
                    <button
                        onClick={() => setActiveTab('settings')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'settings'
                                ? 'bg-background text-foreground shadow-sm'
                                : 'text-muted-foreground hover:text-foreground'
                            }`}
                    >
                        <Settings className="w-4 h-4" />
                        Settings
                    </button>
                </div>

                {/* Content */}
                {activeTab === 'feed' && (
                    <div>
                        <h2 className="text-lg font-semibold text-foreground mb-4">
                            Recommended for you
                        </h2>
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {loading
                                ? Array.from({ length: 4 }).map((_, i) => <PaperCardSkeleton key={i} />)
                                : papers.map((paper) => (
                                    <PaperCard key={paper.id} paper={paper} />
                                ))}
                        </div>
                        {!loading && papers.length === 0 && (
                            <div className="text-center py-12">
                                <p className="text-muted-foreground">
                                    No recommendations yet. Try saving some papers to improve suggestions!
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'saved' && (
                    <div>
                        <h2 className="text-lg font-semibold text-foreground mb-4">
                            Saved Papers ({savedPapers.length})
                        </h2>
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {loading
                                ? Array.from({ length: 4 }).map((_, i) => <PaperCardSkeleton key={i} />)
                                : savedPapers.map((paper) => (
                                    <PaperCard
                                        key={paper.id}
                                        paper={paper}
                                        onSave={handleUnsave}
                                        isSaved={true}
                                    />
                                ))}
                        </div>
                        {!loading && savedPapers.length === 0 && (
                            <div className="text-center py-12">
                                <Bookmark className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
                                <p className="text-muted-foreground">
                                    No saved papers yet. Start exploring and save papers you find interesting!
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'settings' && (
                    <div className="max-w-xl">
                        <h2 className="text-lg font-semibold text-foreground mb-6">
                            Preferences
                        </h2>

                        <div className="space-y-6">
                            {/* Interested Categories */}
                            <div>
                                <label className="block text-sm font-medium text-foreground mb-2">
                                    Interested Categories
                                </label>
                                <div className="flex flex-wrap gap-2">
                                    {['cs.AI', 'cs.LG', 'cs.CV', 'cs.CL', 'cs.NE', 'stat.ML'].map((cat) => (
                                        <button
                                            key={cat}
                                            className="px-3 py-1.5 text-sm bg-secondary hover:bg-primary hover:text-primary-foreground rounded-full transition-colors"
                                        >
                                            {cat}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Paper Maturity */}
                            <div>
                                <label className="block text-sm font-medium text-foreground mb-2">
                                    Paper Types
                                </label>
                                <select className="w-full bg-secondary rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary">
                                    <option value="all">All papers</option>
                                    <option value="with_implementation">With code only</option>
                                    <option value="preprint_only">Preprints only</option>
                                </select>
                            </div>

                            <button className="bg-primary text-primary-foreground px-6 py-2.5 rounded-lg font-medium hover:bg-primary/90 transition-colors">
                                Save Preferences
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
