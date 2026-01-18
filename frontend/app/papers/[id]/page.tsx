'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
    ArrowLeft,
    ExternalLink,
    FileText,
    Github,
    TrendingUp,
    Quote,
    Calendar,
    Users,
    Bookmark,
    Share2,
    Zap,
    Code,
    ThumbsUp,
    AlertTriangle,
    Lightbulb,
    Target,
    FlaskConical,
    Rocket,
    AlertCircle,
    Network,
} from 'lucide-react';
import { Navbar } from '@/components/Navbar';
import { fetchPaperDetail, savePaper, type PaperDetail } from '@/lib/api';
import { formatDate, getCategoryColor, formatAuthors } from '@/lib/utils';
import { Visualization3DButton } from '@/components/Visualization3DModal';

export default function PaperDetailPage() {
    const params = useParams();
    const router = useRouter();
    const paperId = params?.id as string;

    const [paper, setPaper] = useState<PaperDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        const loadPaper = async () => {
            if (!paperId) return;

            setLoading(true);
            try {
                const data = await fetchPaperDetail(paperId);
                setPaper(data);
                console.log('Paper loaded:', data); // Debug
            } catch (err: any) {
                console.error('Error loading paper:', err);
                const msg = err.response?.data?.detail || 'Failed to load paper details.';
                setError(msg);
            } finally {
                setLoading(false);
            }
        };

        loadPaper();
    }, [paperId]);

    const handleSave = async () => {
        if (!paper) return;
        try {
            await savePaper(paper.id);
            setSaved(true);
        } catch (err) {
            console.error('Error saving paper:', err);
        }
    };

    const handleShare = () => {
        if (navigator.share && paper) {
            navigator.share({
                title: paper.title,
                url: window.location.href,
            });
        } else {
            navigator.clipboard.writeText(window.location.href);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-background">
                <Navbar />
                <div className="max-w-4xl mx-auto px-4 py-8">
                    <div className="animate-pulse space-y-6">
                        <div className="h-8 bg-secondary rounded w-3/4"></div>
                        <div className="h-4 bg-secondary rounded w-1/2"></div>
                        <div className="h-32 bg-secondary rounded"></div>
                    </div>
                </div>
            </div>
        );
    }

    if (error || !paper) {
        return (
            <div className="min-h-screen bg-background">
                <Navbar />
                <div className="max-w-4xl mx-auto px-4 py-8">
                    <button
                        onClick={() => router.back()}
                        className="flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back
                    </button>
                    <div className="text-center py-16">
                        <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-lg p-6 inline-block">
                            <h3 className="font-semibold mb-2">Error</h3>
                            <p>{error || 'Paper not found'}</p>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    const categoryColor = getCategoryColor(paper.primary_category);
    const hasSummary = !!paper.summary;

    return (
        <div className="min-h-screen bg-background">
            <Navbar />

            <div className="max-w-4xl mx-auto px-4 py-8">
                {/* Back Button */}
                <button
                    onClick={() => router.back()}
                    className="flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to papers
                </button>

                {/* Header */}
                <div className="mb-8">
                    {/* Categories */}
                    <div className="flex flex-wrap gap-2 mb-4">
                        <span
                            className={`px-3 py-1 rounded-full text-xs font-medium ${categoryColor}`}
                        >
                            {paper.primary_category}
                        </span>
                        {paper.categories
                            .filter((c) => c !== paper.primary_category)
                            .slice(0, 3)
                            .map((cat) => (
                                <span
                                    key={cat}
                                    className="px-3 py-1 rounded-full text-xs font-medium bg-secondary text-secondary-foreground"
                                >
                                    {cat}
                                </span>
                            ))}
                    </div>

                    {/* Title */}
                    <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-4 leading-tight">
                        {paper.title}
                    </h1>

                    {/* Authors */}
                    <div className="flex items-center gap-2 text-muted-foreground mb-4">
                        <Users className="w-4 h-4" />
                        <span className="text-sm">{formatAuthors(paper.authors)}</span>
                    </div>

                    {/* Date */}
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <Calendar className="w-4 h-4" />
                        <span className="text-sm">
                            Published {formatDate(paper.published_date)}
                            {paper.updated_date && paper.updated_date !== paper.published_date && (
                                <span className="ml-2">(Updated {formatDate(paper.updated_date)})</span>
                            )}
                        </span>
                    </div>
                </div>

                {/* Metrics Cards */}
                {paper.metrics && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                        <div className="bg-card border border-border rounded-lg p-4 text-center">
                            <Quote className="w-5 h-5 mx-auto mb-2 text-blue-500" />
                            <div className="text-2xl font-bold text-foreground">
                                {paper.metrics.citation_count}
                            </div>
                            <div className="text-xs text-muted-foreground">Citations</div>
                        </div>
                        <div className="bg-card border border-border rounded-lg p-4 text-center">
                            <TrendingUp className="w-5 h-5 mx-auto mb-2 text-green-500" />
                            <div className="text-2xl font-bold text-foreground">
                                +{paper.metrics.citation_velocity_7d}
                            </div>
                            <div className="text-xs text-muted-foreground">This Week</div>
                        </div>
                        <div className="bg-card border border-border rounded-lg p-4 text-center">
                            <Github className="w-5 h-5 mx-auto mb-2 text-purple-500" />
                            <div className="text-2xl font-bold text-foreground">
                                {paper.metrics.github_stars}
                            </div>
                            <div className="text-xs text-muted-foreground">GitHub Stars</div>
                        </div>
                        <div className="bg-card border border-border rounded-lg p-4 text-center">
                            <Zap className="w-5 h-5 mx-auto mb-2 text-yellow-500" />
                            <div className="text-2xl font-bold text-foreground">
                                {paper.metrics.overall_rank_score.toFixed(1)}
                            </div>
                            <div className="text-xs text-muted-foreground">Radar Score</div>
                        </div>
                    </div>
                )}

                {/* AI Summary & Deep Dive */}
                {hasSummary ? (
                    <div className="space-y-6 mb-8">
                        {/* Quick Briefing */}
                        <div className="bg-gradient-to-br from-primary/10 to-purple-500/10 border border-primary/20 rounded-xl p-6">
                            <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                                <Zap className="w-5 h-5 text-primary" />
                                Quick Briefing
                            </h2>
                            <p className="text-lg font-medium text-foreground mb-4 leading-relaxed">
                                {paper.summary.one_line_summary}
                            </p>

                            {paper.summary.eli5 && (
                                <div className="bg-background/50 rounded-lg p-4 mb-2">
                                    <div className="text-sm font-semibold text-primary mb-1 flex items-center gap-2">
                                        <Lightbulb className="w-4 h-4" />
                                        Explain Like I'm 5
                                    </div>
                                    <p className="text-foreground/90">{paper.summary.eli5}</p>
                                </div>
                            )}

                            <div className="grid md:grid-cols-2 gap-4 mt-4">
                                {paper.summary.problem_statement && (
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-1 flex items-center gap-1">
                                            <Target className="w-3 h-3" />
                                            The Problem
                                        </div>
                                        <p className="text-sm text-foreground/80">{paper.summary.problem_statement}</p>
                                    </div>
                                )}
                                {paper.summary.real_world_use_cases && (
                                    <div>
                                        <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-1 flex items-center gap-1">
                                            <Rocket className="w-3 h-3" />
                                            Use Cases
                                        </div>
                                        <div className="text-sm text-foreground/80 whitespace-pre-line">
                                            {paper.summary.real_world_use_cases}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Innovation & Methodology */}
                        {(paper.summary.key_innovation || paper.summary.methodology) && (
                            <div className="grid md:grid-cols-2 gap-6">
                                {paper.summary.key_innovation && (
                                    <div className="bg-card border border-border rounded-xl p-5">
                                        <h3 className="font-semibold text-foreground mb-3 flex items-center gap-2">
                                            <TrendingUp className="w-4 h-4 text-green-500" />
                                            Key Innovation
                                        </h3>
                                        <p className="text-sm text-muted-foreground leading-relaxed">
                                            {paper.summary.key_innovation}
                                        </p>
                                    </div>
                                )}

                                {paper.summary.methodology && (
                                    <div className="bg-card border border-border rounded-xl p-5">
                                        <h3 className="font-semibold text-foreground mb-3 flex items-center gap-2">
                                            <FlaskConical className="w-4 h-4 text-blue-500" />
                                            Methodology
                                        </h3>
                                        <p className="text-sm text-muted-foreground leading-relaxed">
                                            {paper.summary.methodology}
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Results */}
                        {paper.summary.results_summary && (
                            <div className="bg-card border border-border rounded-xl p-5">
                                <h3 className="font-semibold text-foreground mb-3 flex items-center gap-2">
                                    <TrendingUp className="w-4 h-4 text-orange-500" />
                                    Key Results
                                </h3>
                                <p className="text-sm text-muted-foreground">
                                    {paper.summary.results_summary}
                                </p>
                            </div>
                        )}

                        {/* Pros and Cons */}
                        {(paper.summary.pros || paper.summary.cons) && (
                            <div className="grid md:grid-cols-2 gap-6">
                                {/* Pros */}
                                {paper.summary.pros && (
                                    <div className="bg-green-500/5 border border-green-500/20 rounded-xl p-5">
                                        <h3 className="font-semibold text-green-700 dark:text-green-400 mb-3 flex items-center gap-2">
                                            <ThumbsUp className="w-5 h-5" />
                                            Advantages & Strengths
                                        </h3>
                                        <div className="text-sm text-foreground/80 whitespace-pre-line">
                                            {paper.summary.pros}
                                        </div>
                                    </div>
                                )}
                                
                                {/* Cons */}
                                {paper.summary.cons && (
                                    <div className="bg-orange-500/5 border border-orange-500/20 rounded-xl p-5">
                                        <h3 className="font-semibold text-orange-700 dark:text-orange-400 mb-3 flex items-center gap-2">
                                            <AlertTriangle className="w-5 h-5" />
                                            Limitations & Challenges
                                        </h3>
                                        <div className="text-sm text-foreground/80 whitespace-pre-line">
                                            {paper.summary.cons}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Limitations / Future Work */}
                        {paper.summary.limitations && (
                            <div className="bg-orange-500/5 border border-orange-500/10 rounded-xl p-5">
                                <h3 className="font-semibold text-orange-700 dark:text-orange-400 mb-2 flex items-center gap-2">
                                    <AlertCircle className="w-4 h-4" />
                                    Limitations & Future Work
                                </h3>
                                <p className="text-sm text-foreground/80">
                                    {paper.summary.limitations}
                                </p>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="bg-card border border-border rounded-xl p-6 mb-8">
                        <p className="text-muted-foreground text-center">
                            🤖 AI summary not yet generated for this paper. 
                            <br />
                            <span className="text-sm">It will be available soon!</span>
                        </p>
                    </div>
                )}

                {/* Abstract */}
                <div className="mb-8">
                    <h2 className="text-lg font-semibold text-foreground mb-3">Abstract</h2>
                    <p className="text-muted-foreground leading-relaxed">{paper.abstract}</p>
                </div>

                {/* Implementations */}
                {paper.implementations && paper.implementations.length > 0 && (
                    <div className="mb-8">
                        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                            <Github className="w-5 h-5" />
                            Implementations ({paper.implementations.length})
                        </h2>
                        <div className="space-y-3">
                            {paper.implementations.map((impl, idx) => (
                                <a
                                    key={idx}
                                    href={impl.repo_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="block bg-card border border-border rounded-lg p-4 hover:border-primary/50 transition-colors"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <Github className="w-5 h-5 text-muted-foreground" />
                                            <span className="font-medium text-foreground">{impl.repo_name}</span>
                                            {impl.language && (
                                                <span className="text-xs px-2 py-0.5 bg-secondary rounded text-secondary-foreground">
                                                    {impl.language}
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2 text-muted-foreground">
                                            <span>⭐ {impl.stars}</span>
                                            <ExternalLink className="w-4 h-4" />
                                        </div>
                                    </div>
                                    {impl.description && (
                                        <p className="text-sm text-muted-foreground mt-2">{impl.description}</p>
                                    )}
                                </a>
                            ))}
                        </div>
                    </div>
                )}

                {/* Actions */}
                <div className="flex flex-wrap gap-3 pt-6 border-t border-border">
                    <a
                        href={paper.pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 bg-primary text-primary-foreground px-6 py-3 rounded-lg font-medium hover:bg-primary/90 transition-colors"
                    >
                        <FileText className="w-4 h-4" />
                        Read PDF
                    </a>
                    <a
                        href={paper.arxiv_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 bg-secondary text-secondary-foreground px-6 py-3 rounded-lg font-medium hover:bg-secondary/80 transition-colors"
                    >
                        <ExternalLink className="w-4 h-4" />
                        View on arXiv
                    </a>
                    
                    <Visualization3DButton 
                        paperId={paper.id}
                        paperTitle={paper.title}
                        className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:opacity-90 transition-all shadow-lg"
                    />
                    
                    <button
                        onClick={handleSave}
                        className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-colors ${saved
                            ? 'bg-green-500/20 text-green-500'
                            : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                            }`}
                    >
                        <Bookmark className={`w-4 h-4 ${saved ? 'fill-current' : ''}`} />
                        {saved ? 'Saved' : 'Save'}
                    </button>
                    <button
                        onClick={handleShare}
                        className="flex items-center gap-2 bg-secondary text-secondary-foreground px-6 py-3 rounded-lg font-medium hover:bg-secondary/80 transition-colors"
                    >
                        <Share2 className="w-4 h-4" />
                        Share
                    </button>
                </div>
            </div>
        </div>
    );
}
