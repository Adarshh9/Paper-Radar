'use client';

import React, { useState } from 'react';
import { Plus, Link2, Loader2, CheckCircle, AlertCircle, X, Sparkles } from 'lucide-react';
import { submitPaper, type PaperSubmitResponse } from '@/lib/api';
import { cn } from '@/lib/utils';

interface PaperSubmitModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess?: (response: PaperSubmitResponse) => void;
}

export function PaperSubmitModal({ isOpen, onClose, onSuccess }: PaperSubmitModalProps) {
    const [url, setUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<PaperSubmitResponse | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!url.trim()) return;
        
        setLoading(true);
        setResult(null);
        
        try {
            const response = await submitPaper(url.trim());
            setResult(response);
            
            if (response.success && onSuccess) {
                onSuccess(response);
            }
            
            if (response.success) {
                setUrl('');
            }
        } catch (err) {
            setResult({
                success: false,
                error: 'Failed to submit paper. Please try again.',
                already_exists: false,
            });
        } finally {
            setLoading(false);
        }
    };

    const handleClose = () => {
        setUrl('');
        setResult(null);
        onClose();
    };

    if (!isOpen) return null;

    return (
        <div 
            className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            onClick={(e) => e.target === e.currentTarget && handleClose()}
        >
            <div 
                className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-md animate-in fade-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-5 border-b border-border">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-primary to-purple-600 rounded-xl flex items-center justify-center">
                            <Plus className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-foreground">Submit a Paper</h2>
                            <p className="text-xs text-muted-foreground">Help grow the research database</p>
                        </div>
                    </div>
                    <button 
                        onClick={handleClose}
                        className="p-2 hover:bg-secondary rounded-lg transition-colors text-muted-foreground hover:text-foreground"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-5">
                    <form onSubmit={handleSubmit} className="space-y-4">
                        {/* URL Input */}
                        <div>
                            <label htmlFor="paper-url" className="block text-sm font-medium text-foreground mb-2">
                                arXiv Paper URL
                            </label>
                            <div className="relative">
                                <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                <input
                                    id="paper-url"
                                    type="text"
                                    value={url}
                                    onChange={(e) => setUrl(e.target.value)}
                                    placeholder="https://arxiv.org/abs/2512.24880"
                                    className="w-full pl-10 pr-4 py-3 bg-background border border-border rounded-xl text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
                                    disabled={loading}
                                    autoFocus
                                />
                            </div>
                            
                            {/* URL Format Hint */}
                            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                                <span>Supported:</span>
                                <code className="px-1.5 py-0.5 bg-secondary rounded text-[10px]">arxiv.org/abs/...</code>
                                <code className="px-1.5 py-0.5 bg-secondary rounded text-[10px]">arxiv.org/pdf/...</code>
                            </div>
                        </div>

                        {/* Result Message */}
                        {result && (
                            <div className={cn(
                                'p-4 rounded-xl flex items-start gap-3',
                                result.success 
                                    ? 'bg-green-500/10 border border-green-500/30' 
                                    : 'bg-red-500/10 border border-red-500/30'
                            )}>
                                {result.success ? (
                                    <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                                ) : (
                                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                )}
                                <div className="flex-1 min-w-0">
                                    <p className={cn(
                                        'text-sm font-medium',
                                        result.success ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                                    )}>
                                        {result.success ? (result.already_exists ? 'Paper already exists!' : 'Paper added successfully!') : 'Submission failed'}
                                    </p>
                                    {result.title && (
                                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                            {result.title}
                                        </p>
                                    )}
                                    {result.error && (
                                        <p className="text-xs text-red-500 mt-1">
                                            {result.error}
                                        </p>
                                    )}
                                    {result.success && result.paper_id && !result.already_exists && (
                                        <p className="text-xs text-muted-foreground mt-2">
                                            ✨ AI summaries & implementations will be generated shortly
                                        </p>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={loading || !url.trim()}
                            className={cn(
                                'w-full py-3 rounded-xl font-medium transition-all flex items-center justify-center gap-2',
                                loading || !url.trim()
                                    ? 'bg-secondary text-muted-foreground cursor-not-allowed'
                                    : 'bg-gradient-to-r from-primary to-purple-600 text-white hover:opacity-90 shadow-lg shadow-primary/25'
                            )}
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Fetching from arXiv...
                            </>
                        ) : (
                            <>
                                <Plus className="w-4 h-4" />
                                Submit Paper
                            </>
                        )}
                    </button>
                </form>
                </div>

                {/* Footer Info */}
                <div className="px-5 pb-5">
                    <div className="p-4 bg-secondary/50 rounded-xl">
                        <div className="flex items-start gap-3">
                            <Sparkles className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                            <div className="text-xs text-muted-foreground space-y-1">
                                <p className="font-medium text-foreground">What happens next?</p>
                                <ul className="space-y-0.5 list-disc list-inside">
                                    <li>Paper metadata fetched from arXiv</li>
                                    <li>AI generates summaries, pros/cons, ELI5</li>
                                    <li>GitHub implementations discovered</li>
                                    <li>Paper ranked and added to database</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

// Button to trigger the modal
export function PaperSubmitButton({ className }: { className?: string }) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <>
            <button
                onClick={() => setIsOpen(true)}
                className={cn(
                    'flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-primary to-purple-600 text-white rounded-lg font-medium hover:opacity-90 transition-all shadow-lg shadow-primary/25',
                    className
                )}
            >
                <Plus className="w-4 h-4" />
                Submit Paper
            </button>
            
            <PaperSubmitModal 
                isOpen={isOpen} 
                onClose={() => setIsOpen(false)}
            />
        </>
    );
}
