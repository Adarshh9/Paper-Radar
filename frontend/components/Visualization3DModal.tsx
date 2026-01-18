'use client';

import React, { useState } from 'react';
import { Network, Layers, GraduationCap, X } from 'lucide-react';
import dynamic from 'next/dynamic';

// Dynamic imports for 3D components
const PaperNetwork3D = dynamic(() => import('./PaperNetwork3D'), { ssr: false });
const PaperTopics3D = dynamic(() => import('./PaperTopics3D'), { ssr: false });

interface Visualization3DModalProps {
    paperId: string;
    paperTitle: string;
    isOpen: boolean;
    onClose: () => void;
}

type VisualizationType = 'network' | 'topics' | 'learning';

export function Visualization3DModal({ paperId, paperTitle, isOpen, onClose }: Visualization3DModalProps) {
    const [activeTab, setActiveTab] = useState<VisualizationType>('topics');

    if (!isOpen) return null;

    const tabs = [
        { id: 'topics', label: 'Paper Topics', icon: Layers, description: 'Concepts & techniques' },
        { id: 'network', label: 'Paper Network', icon: Network, description: 'Related papers' },
        { id: 'learning', label: 'Learning Path', icon: GraduationCap, description: 'Prerequisites & outcomes' },
    ] as const;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="bg-background rounded-2xl shadow-2xl w-full max-w-7xl h-[90vh] flex flex-col overflow-hidden border border-border">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-border">
                    <div>
                        <h2 className="text-xl font-bold text-foreground mb-1">3D Visualizations</h2>
                        <p className="text-sm text-muted-foreground line-clamp-1">{paperTitle}</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-secondary rounded-lg transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex gap-2 px-6 pt-4 border-b border-border">
                    {tabs.map((tab) => {
                        const Icon = tab.icon;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id as VisualizationType)}
                                className={`
                                    flex items-center gap-2 px-4 py-3 rounded-t-lg transition-all
                                    ${activeTab === tab.id
                                        ? 'bg-background border border-b-0 border-border text-foreground'
                                        : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
                                    }
                                `}
                            >
                                <Icon className="w-4 h-4" />
                                <div className="text-left">
                                    <div className="text-sm font-medium">{tab.label}</div>
                                    <div className="text-xs opacity-70">{tab.description}</div>
                                </div>
                            </button>
                        );
                    })}
                </div>

                {/* Content */}
                <div className="flex-1 p-6 overflow-auto">
                    {activeTab === 'topics' && (
                        <div className="h-full">
                            <PaperTopics3D paperId={paperId} height={600} />
                        </div>
                    )}
                    
                    {activeTab === 'network' && (
                        <div className="h-full">
                            <PaperNetwork3D paperId={paperId} height={600} />
                        </div>
                    )}
                    
                    {activeTab === 'learning' && (
                        <div className="h-full flex items-center justify-center">
                            <div className="text-center text-muted-foreground">
                                <GraduationCap className="w-16 h-16 mx-auto mb-4 opacity-50" />
                                <p>Learning path visualization coming soon!</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// Button to trigger the modal
export function Visualization3DButton({ paperId, paperTitle, className }: { paperId: string; paperTitle: string; className?: string }) {
    const [isOpen, setIsOpen] = useState(false);

    return (
        <>
            <button
                onClick={() => setIsOpen(true)}
                className={className}
            >
                <Network className="w-4 h-4 mr-2" />
                3D Visualization
            </button>

            <Visualization3DModal
                paperId={paperId}
                paperTitle={paperTitle}
                isOpen={isOpen}
                onClose={() => setIsOpen(false)}
            />
        </>
    );
}
