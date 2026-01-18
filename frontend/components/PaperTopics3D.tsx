'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Loader2, Info, ZoomIn, ZoomOut, RotateCcw, List, X, Focus, Layers } from 'lucide-react';
import { getPaperTopics3D } from '@/lib/api';
import * as THREE from 'three';

const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), {
    ssr: false,
    loading: () => (
        <div className="flex items-center justify-center h-[600px]">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
    ),
});

interface Node {
    id: string;
    label: string;
    category: string;
    x: number;
    y: number;
    z: number;
    size: number;
    color: string;
    layer: number;
}

interface Link {
    source: string;
    target: string;
    type: string;
    strength: number;
}

interface Layer {
    name: string;
    radius: number;
    color: string;
}

interface TopicGraphData {
    nodes: Node[];
    links: Link[];
    layers: Layer[];
    stats?: any;
}

interface PaperTopics3DProps {
    paperId: string;
    height?: number;
}

export function PaperTopics3D({ paperId, height = 600 }: PaperTopics3DProps) {
    const fgRef = useRef<any>();
    const [graphData, setGraphData] = useState<TopicGraphData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [hoveredNode, setHoveredNode] = useState<Node | null>(null);
    const [focusedNode, setFocusedNode] = useState<Node | null>(null);
    const [showConceptList, setShowConceptList] = useState(false);
    const [showLabels, setShowLabels] = useState(true);

    // Focus on a specific node
    const focusOnNode = useCallback((node: Node) => {
        if (fgRef.current && node) {
            setFocusedNode(node);
            // Animate camera to focus on node
            const distance = 200;
            fgRef.current.cameraPosition(
                {
                    x: (node.x || 0) + distance * 0.5,
                    y: (node.y || 0) + distance * 0.3,
                    z: (node.z || 0) + distance * 0.8,
                },
                { x: node.x || 0, y: node.y || 0, z: node.z || 0 },
                1500
            );
        }
    }, []);

    // Get link color based on type
    const getLinkColor = useCallback((link: Link) => {
        switch (link.type) {
            case 'uses': return '#3B82F6';
            case 'enables': return '#22C55E';
            case 'applies': return '#F59E0B';
            case 'involves': return '#EC4899';
            default: return '#6B7280';
        }
    }, []);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const result = await getPaperTopics3D(paperId);
                setGraphData(result);
            } catch (err: any) {
                console.error('Error loading topic graph:', err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [paperId]);

    useEffect(() => {
        if (fgRef.current && graphData) {
            // Position camera farther back for better overview
            fgRef.current.cameraPosition({ x: 0, y: 200, z: 600 });
            
            // Gentle rotation for first 10 seconds
            let angle = 0;
            const rotateInterval = setInterval(() => {
                if (fgRef.current && !focusedNode) {
                    angle += 0.003;
                    fgRef.current.cameraPosition({
                        x: 600 * Math.sin(angle),
                        y: 200,
                        z: 600 * Math.cos(angle),
                    });
                }
            }, 50);

            setTimeout(() => clearInterval(rotateInterval), 10000);
            return () => clearInterval(rotateInterval);
        }
    }, [graphData, focusedNode]);

    const handleZoomIn = () => {
        if (fgRef.current) {
            const pos = fgRef.current.camera().position;
            const distance = Math.sqrt(pos.x*pos.x + pos.z*pos.z);
            fgRef.current.cameraPosition({ 
                x: pos.x * 0.7, 
                y: pos.y, 
                z: pos.z * 0.7 
            }, undefined, 500);
        }
    };

    const handleZoomOut = () => {
        if (fgRef.current) {
            const pos = fgRef.current.camera().position;
            fgRef.current.cameraPosition({ 
                x: pos.x * 1.4, 
                y: pos.y, 
                z: pos.z * 1.4 
            }, undefined, 500);
        }
    };

    const handleResetView = () => {
        setFocusedNode(null);
        if (fgRef.current) {
            fgRef.current.cameraPosition({ x: 0, y: 200, z: 600 }, { x: 0, y: 0, z: 0 }, 1000);
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-[600px] bg-card rounded-xl border border-border">
                <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
                <p className="text-muted-foreground">Analyzing paper topics...</p>
            </div>
        );
    }

    if (error || !graphData) {
        return (
            <div className="flex items-center justify-center h-[600px] bg-card rounded-xl border border-border">
                <div className="text-center">
                    <p className="text-destructive mb-2">Failed to load visualization</p>
                    <p className="text-sm text-muted-foreground">{error || 'No data available'}</p>
                </div>
            </div>
        );
    }

    // Group nodes by category
    const nodesByCategory = graphData ? {
        main_concept: graphData.nodes.filter(n => n.category === 'main_concept'),
        technique: graphData.nodes.filter(n => n.category === 'technique'),
        application: graphData.nodes.filter(n => n.category === 'application'),
        detail: graphData.nodes.filter(n => n.category === 'detail'),
    } : { main_concept: [], technique: [], application: [], detail: [] };

    return (
        <div className="relative bg-gradient-to-br from-background to-card/50 rounded-xl border border-border overflow-hidden">
            {/* Info panel */}
            <div className="absolute top-4 left-4 z-10 bg-background/90 backdrop-blur-sm rounded-lg p-4 border border-border max-w-xs">
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                        <Info className="w-4 h-4 text-primary" />
                        <h3 className="text-sm font-semibold text-foreground">Paper Structure</h3>
                    </div>
                    <button 
                        onClick={() => setShowConceptList(!showConceptList)}
                        className="p-1 hover:bg-secondary rounded transition-colors"
                        title="Show concept list"
                    >
                        <List className="w-4 h-4" />
                    </button>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                    AI-extracted concepts organized by importance.
                </p>
                
                {graphData.stats && (
                    <div className="space-y-1 text-xs">
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Core Concepts:</span>
                            <span className="font-medium text-foreground">{graphData.stats.main_concepts}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Techniques:</span>
                            <span className="font-medium text-foreground">{graphData.stats.techniques}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Applications:</span>
                            <span className="font-medium text-foreground">{graphData.stats.applications}</span>
                        </div>
                    </div>
                )}

                {/* Focused concept info */}
                {focusedNode && (
                    <div className="mt-3 pt-3 border-t border-border">
                        <div className="flex items-center justify-between">
                            <span className="text-xs text-primary font-medium">Focused</span>
                            <button 
                                onClick={handleResetView}
                                className="text-xs text-muted-foreground hover:text-foreground"
                            >
                                Clear
                            </button>
                        </div>
                        <p className="text-xs text-foreground mt-1 line-clamp-2">
                            {focusedNode.label}
                        </p>
                        <span className="text-[10px] text-muted-foreground">{focusedNode.category}</span>
                    </div>
                )}
            </div>

            {/* Concept List Sidebar */}
            {showConceptList && (
                <div className="absolute top-4 left-4 z-20 bg-background/95 backdrop-blur-sm rounded-lg border border-border w-80 max-h-[500px] overflow-hidden flex flex-col">
                    <div className="flex items-center justify-between p-4 border-b border-border">
                        <h3 className="font-semibold text-foreground flex items-center gap-2">
                            <Layers className="w-4 h-4" />
                            All Concepts
                        </h3>
                        <button onClick={() => setShowConceptList(false)} className="p-1 hover:bg-secondary rounded">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                    <div className="overflow-y-auto flex-1 p-2">
                        {/* Main concepts */}
                        {nodesByCategory.main_concept.length > 0 && (
                            <div className="mb-3">
                                <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
                                    <div className="w-2 h-2 rounded-full bg-purple-500"></div>
                                    Core Concepts ({nodesByCategory.main_concept.length})
                                </div>
                                {nodesByCategory.main_concept.map(node => (
                                    <button
                                        key={node.id}
                                        onClick={() => focusOnNode(node)}
                                        className="w-full text-left px-2 py-2 text-sm hover:bg-secondary rounded-lg transition-colors group"
                                    >
                                        <div className="flex items-center gap-2">
                                            <span className="flex-1 truncate">{node.label}</span>
                                            <Focus className="w-3 h-3 opacity-0 group-hover:opacity-100 text-primary" />
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}
                        
                        {/* Techniques */}
                        {nodesByCategory.technique.length > 0 && (
                            <div className="mb-3">
                                <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
                                    <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                                    Techniques ({nodesByCategory.technique.length})
                                </div>
                                {nodesByCategory.technique.map(node => (
                                    <button
                                        key={node.id}
                                        onClick={() => focusOnNode(node)}
                                        className="w-full text-left px-2 py-2 text-sm hover:bg-secondary rounded-lg transition-colors group"
                                    >
                                        <div className="flex items-center gap-2">
                                            <span className="flex-1 truncate text-xs">{node.label}</span>
                                            <Focus className="w-3 h-3 opacity-0 group-hover:opacity-100 text-primary" />
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Applications */}
                        {nodesByCategory.application.length > 0 && (
                            <div className="mb-3">
                                <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
                                    <div className="w-2 h-2 rounded-full bg-green-500"></div>
                                    Applications ({nodesByCategory.application.length})
                                </div>
                                {nodesByCategory.application.map(node => (
                                    <button
                                        key={node.id}
                                        onClick={() => focusOnNode(node)}
                                        className="w-full text-left px-2 py-2 text-sm hover:bg-secondary rounded-lg transition-colors group"
                                    >
                                        <div className="flex items-center gap-2">
                                            <span className="flex-1 truncate text-xs">{node.label}</span>
                                            <Focus className="w-3 h-3 opacity-0 group-hover:opacity-100 text-primary" />
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Details */}
                        {nodesByCategory.detail.length > 0 && (
                            <div className="mb-3">
                                <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
                                    <div className="w-2 h-2 rounded-full bg-amber-500"></div>
                                    Details ({nodesByCategory.detail.length})
                                </div>
                                {nodesByCategory.detail.slice(0, 10).map(node => (
                                    <button
                                        key={node.id}
                                        onClick={() => focusOnNode(node)}
                                        className="w-full text-left px-2 py-2 text-sm hover:bg-secondary rounded-lg transition-colors group"
                                    >
                                        <div className="flex items-center gap-2">
                                            <span className="flex-1 truncate text-xs">{node.label}</span>
                                            <Focus className="w-3 h-3 opacity-0 group-hover:opacity-100 text-primary" />
                                        </div>
                                    </button>
                                ))}
                                {nodesByCategory.detail.length > 10 && (
                                    <p className="text-xs text-muted-foreground px-2 py-1">
                                        +{nodesByCategory.detail.length - 10} more...
                                    </p>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Zoom controls */}
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex gap-2">
                <button 
                    onClick={handleZoomIn}
                    className="p-2.5 bg-background/90 backdrop-blur-sm rounded-lg border border-border hover:bg-secondary transition-colors"
                    title="Zoom In"
                >
                    <ZoomIn className="w-5 h-5" />
                </button>
                <button 
                    onClick={handleZoomOut}
                    className="p-2.5 bg-background/90 backdrop-blur-sm rounded-lg border border-border hover:bg-secondary transition-colors"
                    title="Zoom Out"
                >
                    <ZoomOut className="w-5 h-5" />
                </button>
                <button 
                    onClick={handleResetView}
                    className="p-2.5 bg-background/90 backdrop-blur-sm rounded-lg border border-border hover:bg-secondary transition-colors"
                    title="Reset View"
                >
                    <RotateCcw className="w-5 h-5" />
                </button>
                <button 
                    onClick={() => setShowLabels(!showLabels)}
                    className={`p-2.5 backdrop-blur-sm rounded-lg border transition-colors ${showLabels ? 'bg-primary text-primary-foreground border-primary' : 'bg-background/90 border-border hover:bg-secondary'}`}
                    title={showLabels ? "Hide Labels" : "Show Labels"}
                >
                    <span className="text-xs font-bold">Aa</span>
                </button>
            </div>

            {/* Layer legend */}
            <div className="absolute top-4 right-4 z-10 bg-background/90 backdrop-blur-sm rounded-lg p-4 border border-border">
                <h3 className="text-sm font-semibold text-foreground mb-2">Concept Layers</h3>
                <div className="space-y-2 text-xs">
                    {graphData.layers.map((layer, idx) => (
                        <div key={idx} className="flex items-center gap-2">
                            <div 
                                className="w-3 h-3 rounded-full" 
                                style={{ backgroundColor: layer.color }}
                            ></div>
                            <span className="text-muted-foreground">{layer.name}</span>
                        </div>
                    ))}
                </div>
                
                <h3 className="text-sm font-semibold text-foreground mb-2 mt-3 pt-3 border-t border-border">Connection Types</h3>
                <div className="space-y-2 text-xs">
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-1.5 rounded" style={{ backgroundColor: '#3B82F6' }}></div>
                        <span className="text-muted-foreground">Uses</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-1.5 rounded" style={{ backgroundColor: '#22C55E' }}></div>
                        <span className="text-muted-foreground">Enables</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-1.5 rounded" style={{ backgroundColor: '#F59E0B' }}></div>
                        <span className="text-muted-foreground">Applies</span>
                    </div>
                </div>
            </div>

            {/* Hovered node info */}
            {hoveredNode && !showConceptList && (
                <div className="absolute bottom-20 left-4 z-10 bg-background/95 backdrop-blur-sm rounded-lg p-4 border border-border max-w-sm" style={{ borderLeftColor: hoveredNode.color, borderLeftWidth: 3 }}>
                    <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: hoveredNode.color }}></div>
                                <span className="text-xs text-muted-foreground">{hoveredNode.category}</span>
                            </div>
                            <h4 className="font-semibold text-foreground text-sm">
                                {hoveredNode.label}
                            </h4>
                        </div>
                        <button 
                            onClick={() => focusOnNode(hoveredNode)}
                            className="p-1.5 bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors"
                            title="Focus on this node"
                        >
                            <Focus className="w-4 h-4 text-primary" />
                        </button>
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-2">Click focus to zoom in</p>
                </div>
            )}

            {/* Controls hint */}
            <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-10 bg-background/90 backdrop-blur-sm rounded-lg px-4 py-2 border border-border">
                <p className="text-xs text-muted-foreground">
                    🖱️ Drag to rotate • Scroll to zoom • Click concept list for navigation
                </p>
            </div>

            <ForceGraph3D
                ref={fgRef}
                graphData={graphData}
                nodeLabel={() => ''} // Using custom hover
                nodeVal={(node: any) => node.size}
                nodeColor={(node: any) => node.color}
                nodeRelSize={4}
                nodeOpacity={0.9}
                nodeThreeObject={(node: any) => {
                    const group = new THREE.Group();
                    
                    // Sphere - smaller for less clutter
                    const baseSize = Math.max(5, (node.size || 8) * 0.8);
                    const geometry = new THREE.SphereGeometry(baseSize);
                    const material = new THREE.MeshLambertMaterial({
                        color: node.color,
                        transparent: true,
                        opacity: focusedNode && focusedNode.id !== node.id ? 0.35 : 0.85,
                    });
                    const sphere = new THREE.Mesh(geometry, material);
                    group.add(sphere);
                    
                    // Add glow for core concepts or focused node
                    if (node.layer === 0 || (focusedNode && focusedNode.id === node.id)) {
                        const glowGeometry = new THREE.SphereGeometry(baseSize * 1.5);
                        const glowMaterial = new THREE.MeshBasicMaterial({
                            color: node.color,
                            transparent: true,
                            opacity: 0.2,
                        });
                        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
                        group.add(glow);
                    }

                    // Text label (only if showLabels is true)
                    if (showLabels) {
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
                        if (ctx) {
                            canvas.width = 512;
                            canvas.height = 64;
                            ctx.fillStyle = 'transparent';
                            ctx.fillRect(0, 0, canvas.width, canvas.height);
                            ctx.font = 'bold 26px Arial';
                            ctx.fillStyle = focusedNode && focusedNode.id !== node.id ? 'rgba(255,255,255,0.35)' : 'white';
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            
                            let label = node.label || '';
                            if (label.length > 28) {
                                label = label.substring(0, 25) + '...';
                            }
                            ctx.fillText(label, canvas.width / 2, canvas.height / 2);
                            
                            const texture = new THREE.CanvasTexture(canvas);
                            const spriteMaterial = new THREE.SpriteMaterial({ 
                                map: texture, 
                                transparent: true,
                                opacity: focusedNode && focusedNode.id !== node.id ? 0.3 : 0.9,
                            });
                            const sprite = new THREE.Sprite(spriteMaterial);
                            sprite.scale.set(90, 12, 1);
                            sprite.position.set(0, baseSize + 14, 0);
                            group.add(sprite);
                        }
                    }
                    
                    return group;
                }}
                linkWidth={(link: any) => (link.strength || 0.5) * 2.5 + 0.5}
                linkOpacity={0.5}
                linkColor={(link: any) => getLinkColor(link)}
                linkDirectionalParticles={(link: any) => (link.strength || 0.5) > 0.5 ? 2 : 1}
                linkDirectionalParticleWidth={2}
                linkDirectionalParticleSpeed={0.004}
                linkDirectionalParticleColor={(link: any) => getLinkColor(link)}
                backgroundColor="rgba(0,0,0,0)"
                height={height}
                d3AlphaDecay={0.01}
                d3VelocityDecay={0.3}
                enableNodeDrag={false}
                onNodeClick={(node: any) => focusOnNode(node)}
                onNodeHover={(node: any) => {
                    setHoveredNode(node || null);
                    document.body.style.cursor = node ? 'pointer' : 'default';
                }}
            />
        </div>
    );
}

export default PaperTopics3D;
