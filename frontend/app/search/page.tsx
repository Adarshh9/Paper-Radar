'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Search, ArrowLeft } from 'lucide-react';
import { Navbar } from '@/components/Navbar';
import { PaperCard, PaperCardSkeleton } from '@/components/PaperCard';
import { searchPapers, type PaperListItem } from '@/lib/api';

function SearchContent() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const query = searchParams.get('q') || '';

    const [papers, setPapers] = useState<PaperListItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [searchInput, setSearchInput] = useState(query);

    useEffect(() => {
        if (!query) {
            setPapers([]);
            return;
        }

        const performSearch = async () => {
            setLoading(true);
            setError(null);

            try {
                const response = await searchPapers(query);
                setPapers(response.items || []);
            } catch (err) {
                console.error('Search error:', err);
                setError('Search failed. Please try again.');
                setPapers([]);
            } finally {
                setLoading(false);
            }
        };

        performSearch();
    }, [query]);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (searchInput.trim()) {
            router.push(`/search?q=${encodeURIComponent(searchInput.trim())}`);
        }
    };

    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            <div className="max-w-5xl mx-auto px-4 py-8">
                {/* Search Header */}
                <div className="mb-8">
                    <button
                        onClick={() => router.push('/papers')}
                        className="flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4 transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back to papers
                    </button>

                    <h1 className="text-2xl font-bold text-foreground mb-4">
                        Search Papers
                    </h1>

                    {/* Search Form */}
                    <form onSubmit={handleSearch} className="relative">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                        <input
                            type="text"
                            value={searchInput}
                            onChange={(e) => setSearchInput(e.target.value)}
                            placeholder="Search by title, abstract, or keywords..."
                            className="w-full pl-12 pr-4 py-4 bg-secondary border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
                        />
                        <button
                            type="submit"
                            className="absolute right-2 top-1/2 -translate-y-1/2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:bg-primary/90 transition-colors"
                        >
                            Search
                        </button>
                    </form>
                </div>

                {/* Search Results */}
                {query && (
                    <div className="mb-4">
                        <p className="text-muted-foreground">
                            {loading ? (
                                'Searching...'
                            ) : (
                                <>
                                    Found <span className="text-foreground font-medium">{papers.length}</span> results for{' '}
                                    <span className="text-primary font-medium">"{query}"</span>
                                </>
                            )}
                        </p>
                    </div>
                )}

                {error && (
                    <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-lg p-4 mb-6">
                        {error}
                    </div>
                )}

                {/* Results Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {loading
                        ? Array.from({ length: 4 }).map((_, i) => <PaperCardSkeleton key={i} />)
                        : papers.map((paper) => (
                            <PaperCard key={paper.id} paper={paper} />
                        ))}
                </div>

                {/* Empty State */}
                {!loading && query && papers.length === 0 && !error && (
                    <div className="text-center py-16">
                        <Search className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
                        <p className="text-muted-foreground mb-2">
                            No papers found for "{query}"
                        </p>
                        <p className="text-sm text-muted-foreground">
                            Try different keywords or check the spelling
                        </p>
                    </div>
                )}

                {/* Initial State */}
                {!query && (
                    <div className="text-center py-16">
                        <Search className="w-12 h-12 text-muted-foreground/50 mx-auto mb-4" />
                        <p className="text-muted-foreground">
                            Enter a search term to find papers
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}

export default function SearchPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        }>
            <SearchContent />
        </Suspense>
    );
}
