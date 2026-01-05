'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Filter } from 'lucide-react';
import { Navbar } from '@/components/Navbar';
import { PaperCard, PaperCardSkeleton } from '@/components/PaperCard';
import { FilterSidebar } from '@/components/FilterSidebar';
import { fetchPapers, savePaper, unsavePaper, type PaperListItem } from '@/lib/api';
import { useFilterStore, useAuthStore } from '@/stores';

export default function PapersPage() {
    const router = useRouter();
    const searchParams = useSearchParams();

    const [papers, setPapers] = useState<PaperListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
    const [showMobileFilter, setShowMobileFilter] = useState(false);

    const { category, sortBy, hasImplementation, dateRange, getDateFrom } = useFilterStore();
    const { isAuthenticated } = useAuthStore();

    // Load papers
    useEffect(() => {
        const loadPapers = async () => {
            setLoading(true);
            setError(null);

            try {
                const urlCategory = searchParams.get('category') || category || undefined;
                const dateFrom = getDateFrom(); // This uses current dateRange from store

                const response = await fetchPapers({
                    category: urlCategory,
                    sort_by: sortBy,
                    has_implementation: hasImplementation ?? undefined,
                    date_from: dateFrom,
                    page,
                    page_size: 20,
                });

                setPapers(response.items);
                setTotalPages(response.total_pages);
            } catch (err) {
                console.error('Error loading papers:', err);
                setError('Failed to load papers. Please try again.');
            } finally {
                setLoading(false);
            }
        };

        loadPapers();
    }, [category, sortBy, hasImplementation, dateRange, page, searchParams, getDateFrom]);

    const handleSave = async (paperId: string) => {
        if (!isAuthenticated) {
            router.push('/auth/login');
            return;
        }

        try {
            if (savedIds.has(paperId)) {
                await unsavePaper(paperId);
                setSavedIds((prev) => {
                    const next = new Set(prev);
                    next.delete(paperId);
                    return next;
                });
            } else {
                await savePaper(paperId);
                setSavedIds((prev) => new Set(prev).add(paperId));
            }
        } catch (err) {
            console.error('Error saving paper:', err);
        }
    };

    const handleSearch = (query: string) => {
        router.push(`/papers?q=${encodeURIComponent(query)}`);
    };

    return (
        <div className="min-h-screen bg-background">
            <Navbar onSearch={handleSearch} />

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-2xl font-bold text-foreground">Papers</h1>
                        <p className="text-muted-foreground">
                            Discover the latest research in AI and Machine Learning
                        </p>
                    </div>

                    {/* Mobile filter toggle */}
                    <button
                        onClick={() => setShowMobileFilter(true)}
                        className="md:hidden flex items-center gap-2 bg-secondary px-4 py-2 rounded-lg"
                    >
                        <Filter className="w-4 h-4" />
                        Filters
                    </button>
                </div>

                <div className="flex gap-8">
                    {/* Desktop Sidebar */}
                    <div className="hidden md:block w-64 flex-shrink-0">
                        <FilterSidebar className="sticky top-24" />
                    </div>

                    {/* Mobile Sidebar Overlay */}
                    {showMobileFilter && (
                        <div className="md:hidden fixed inset-0 z-50 bg-background/80 backdrop-blur-sm">
                            <div className="fixed inset-y-0 right-0 w-80 bg-background shadow-xl p-4">
                                <FilterSidebar onClose={() => setShowMobileFilter(false)} />
                            </div>
                        </div>
                    )}

                    {/* Papers Grid */}
                    <div className="flex-1">
                        {error && (
                            <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-lg p-4 mb-6">
                                {error}
                            </div>
                        )}

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {loading
                                ? Array.from({ length: 6 }).map((_, i) => (
                                    <PaperCardSkeleton key={i} />
                                ))
                                : papers.map((paper) => (
                                    <PaperCard
                                        key={paper.id}
                                        paper={paper}
                                        onSave={handleSave}
                                        isSaved={savedIds.has(paper.id)}
                                    />
                                ))}
                        </div>

                        {/* Empty State */}
                        {!loading && papers.length === 0 && (
                            <div className="text-center py-16">
                                <p className="text-muted-foreground">No papers found matching your criteria.</p>
                            </div>
                        )}

                        {/* Pagination */}
                        {totalPages > 1 && (
                            <div className="flex items-center justify-center gap-2 mt-8">
                                <button
                                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                                    disabled={page === 1}
                                    className="px-4 py-2 bg-secondary rounded-lg disabled:opacity-50"
                                >
                                    Previous
                                </button>
                                <span className="text-muted-foreground">
                                    Page {page} of {totalPages}
                                </span>
                                <button
                                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                                    disabled={page === totalPages}
                                    className="px-4 py-2 bg-secondary rounded-lg disabled:opacity-50"
                                >
                                    Next
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
