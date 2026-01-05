'use client';

import React from 'react';
import Link from 'next/link';
import { TrendingUp, Code, BookOpen, Star, ExternalLink, Bookmark } from 'lucide-react';
import { cn, formatDate, formatAuthors, formatNumber, getCategoryColor } from '@/lib/utils';
import type { PaperListItem } from '@/lib/api';

interface PaperCardProps {
    paper: PaperListItem;
    onSave?: (id: string) => void;
    isSaved?: boolean;
}

export function PaperCard({ paper, onSave, isSaved = false }: PaperCardProps) {
    const isTrending = paper.citation_velocity_7d > 5;

    return (
        <div className="group relative bg-card rounded-xl border border-border p-5 transition-all duration-200 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5">
            {/* Trending badge */}
            {isTrending && (
                <div className="absolute -top-2 -right-2 flex items-center gap-1 bg-gradient-to-r from-orange-500 to-red-500 text-white text-xs font-semibold px-2 py-1 rounded-full">
                    <TrendingUp className="w-3 h-3" />
                    TRENDING
                </div>
            )}

            {/* Category tag */}
            <div className="flex items-center gap-2 mb-3">
                <span className={cn('text-xs font-medium px-2 py-0.5 rounded-full', getCategoryColor(paper.primary_category))}>
                    {paper.primary_category}
                </span>
                {paper.has_implementation && (
                    <span className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-green-500/20 text-green-400">
                        <Code className="w-3 h-3" />
                        Has Code
                    </span>
                )}
            </div>

            {/* Title */}
            <h3 className="text-lg font-semibold text-foreground mb-2 line-clamp-2 group-hover:text-primary transition-colors">
                <Link href={`/papers/${paper.id}`}>
                    {paper.title}
                </Link>
            </h3>

            {/* Authors & Date */}
            <p className="text-sm text-muted-foreground mb-3">
                {formatAuthors(paper.authors)} • {formatDate(paper.published_date)}
            </p>

            {/* One-line summary */}
            {paper.one_line_summary && (
                <p className="text-sm text-foreground/80 mb-4 line-clamp-2 italic border-l-2 border-primary/50 pl-3">
                    💡 {paper.one_line_summary}
                </p>
            )}

            {/* Metrics */}
            <div className="flex items-center gap-4 mb-4">
                <div className="flex items-center gap-1 text-sm text-muted-foreground">
                    <BookOpen className="w-4 h-4" />
                    <span>{formatNumber(paper.citation_count)}</span>
                    {paper.citation_velocity_7d > 0 && (
                        <span className="text-green-400 text-xs">
                            +{paper.citation_velocity_7d}/wk
                        </span>
                    )}
                </div>

                {paper.github_stars > 0 && (
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                        <Star className="w-4 h-4" />
                        <span>{formatNumber(paper.github_stars)}</span>
                    </div>
                )}
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-3 border-t border-border">
                <div className="flex items-center gap-2">
                    <a
                        href={paper.arxiv_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
                    >
                        <ExternalLink className="w-3 h-3" />
                        arXiv
                    </a>
                    <a
                        href={paper.pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
                    >
                        <ExternalLink className="w-3 h-3" />
                        PDF
                    </a>
                </div>

                <button
                    onClick={() => onSave?.(paper.id)}
                    className={cn(
                        'flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg transition-all',
                        isSaved
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-secondary text-secondary-foreground hover:bg-primary/20'
                    )}
                >
                    <Bookmark className={cn('w-3 h-3', isSaved && 'fill-current')} />
                    {isSaved ? 'Saved' : 'Save'}
                </button>
            </div>
        </div>
    );
}

export function PaperCardSkeleton() {
    return (
        <div className="bg-card rounded-xl border border-border p-5">
            <div className="flex items-center gap-2 mb-3">
                <div className="skeleton h-5 w-16 rounded-full" />
            </div>
            <div className="skeleton h-6 w-full mb-2" />
            <div className="skeleton h-6 w-3/4 mb-2" />
            <div className="skeleton h-4 w-1/2 mb-3" />
            <div className="skeleton h-12 w-full mb-4" />
            <div className="flex items-center gap-4 mb-4">
                <div className="skeleton h-4 w-16" />
                <div className="skeleton h-4 w-12" />
            </div>
            <div className="flex items-center justify-between pt-3 border-t border-border">
                <div className="flex items-center gap-2">
                    <div className="skeleton h-4 w-12" />
                    <div className="skeleton h-4 w-12" />
                </div>
                <div className="skeleton h-7 w-16 rounded-lg" />
            </div>
        </div>
    );
}
