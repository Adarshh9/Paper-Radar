'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { Loader2, ZoomIn, ZoomOut, RotateCcw, Focus, List, X, ExternalLink, ChevronRight } from 'lucide-react';
import { getPaperNetwork3D } from '@/lib/api';
import * as THREE from 'three';

// Dynamically import ForceGraph3D to avoid SSR issues
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
    fullTitle?: string;
    type: string;
    x: number;
    y: number;
    z: number;
    size: number;
    color: string;
    category?: string;
    metrics?: any;
}

interface Link {
    source: string;
    target: string;
    type: string;
    strength: number;
}

interface GraphData {
    nodes: Node[];
    links: Link[];
    stats?: any;
}

interface PaperNetwork3DProps {
    paperId: string;
    data?: GraphData;
    height?: number;
}

export function PaperNetwork3D({ paperId, data, height = 600 }: PaperNetwork3DProps) {
    const fgRef = useRef<any>();
    const [graphData, setGraphData] = useState<GraphData | null>(data || null);
    const [loading, setLoading] = useState(!data);
    const [error, setError] = useState<string | null>(null);
    const [hoveredNode, setHoveredNode] = useState<Node | null>(null);
    const [focusedNode, setFocusedNode] = useState<Node | null>(null);
    const [showNodeList, setShowNodeList] = useState(false);
    const [showLabels, setShowLabels] = useState(true);

    // Get link color based on strength
    const getLinkColor = useCallback((link: Link) => {
        const strength = link.strength || 0.5;
        if (strength > 0.8) return '#22C55E'; // Strong - green
        if (strength > 0.5) return '#3B82F6'; // Medium - blue
        if (strength > 0.3) return '#F59E0B'; // Weak - orange
        return '#6B7280'; // Very weak - gray
    }, []);

    useEffect(() => {
        if (data) {
            setGraphData(data);
            setLoading(false);
            return;
        }

        const fetchData = async () => {
            setLoading(true);
            try {
                // Fetch more nodes for better visualization
                const result = await getPaperNetwork3D(paperId, 2, 60);
                setGraphData(result);
            } catch (err: any) {
                console.error('Error loading 3D graph:', err);
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [paperId, data]);

    useEffect(() => {
        if (fgRef.current && graphData) {
            // Set initial camera position - further back for better overview
            fgRef.current.cameraPosition({ z: 800 });
            
            // Gentle rotation animation
            let angle = 0;
            const rotateInterval = setInterval(() => {
                if (fgRef.current && !focusedNode) {
                    angle += 0.002;
                    fgRef.current.cameraPosition({
                        x: 800 * Math.sin(angle),
                        z: 800 * Math.cos(angle),
                    });
                }
            }, 50);

            // Stop rotation after 10 seconds
            setTimeout(() => clearInterval(rotateInterval), 10000);

            return () => clearInterval(rotateInterval);
        }
    }, [graphData, focusedNode]);

    const handleZoomIn = () => {
        if (fgRef.current) {
            const distance = fgRef.current.camera().position.length();
            fgRef.current.cameraPosition({ z: distance * 0.6 }, undefined, 500);
        }
    };

    const handleZoomOut = () => {
        if (fgRef.current) {
            const distance = fgRef.current.camera().position.length();
            fgRef.current.cameraPosition({ z: distance * 1.5 }, undefined, 500);
        }
    };

    const handleResetView = () => {
        setFocusedNode(null);
        if (fgRef.current) {
            fgRef.current.cameraPosition({ x: 0, y: 0, z: 800 }, { x: 0, y: 0, z: 0 }, 1000);
        }
    };

    // Focus camera on a specific node
    const focusOnNode = useCallback((node: Node) => {
        setFocusedNode(node);
        if (fgRef.current) {
            // Move camera to focus on node
            const distance = 150;
            fgRef.current.cameraPosition(
                { x: node.x + distance, y: node.y + distance, z: node.z + distance },
                { x: node.x, y: node.y, z: node.z },
                1500
            );
        }
    }, []);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-[600px] bg-card rounded-xl border border-border">
                <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
                <p className="text-muted-foreground">Loading 3D visualization...</p>
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

    // Group nodes by type for the sidebar
    const nodesByType = graphData ? {
        center: graphData.nodes.filter(n => n.type === 'center'),
        cited: graphData.nodes.filter(n => n.type === 'cited'),
        citing: graphData.nodes.filter(n => n.type === 'citing'),
        related: graphData.nodes.filter(n => n.type === 'related'),
    } : { center: [], cited: [], citing: [], related: [] };

    return (
        <div className="relative bg-gradient-to-br from-background to-card/50 rounded-xl border border-border overflow-hidden">
            {/* Stats & Node List toggle */}
            <div className="absolute top-4 left-4 z-10 bg-background/90 backdrop-blur-sm rounded-lg p-4 border border-border">
                <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-foreground">Graph Stats</h3>
                    <button 
                        onClick={() => setShowNodeList(!showNodeList)}
                        className="p-1 hover:bg-secondary rounded transition-colors"
                        title="Show node list"
                    >
                        <List className="w-4 h-4" />
                    </button>
                </div>
                <div className="space-y-1 text-xs text-muted-foreground">
                    <div>Papers: {graphData.stats?.total_nodes || 0}</div>
                    <div>Connections: {graphData.stats?.total_links || 0}</div>
                </div>
                
                {/* Focused node info */}
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
                    </div>
                )}
            </div>

            {/* Node List Sidebar */}
            {showNodeList && (
                <div className="absolute top-4 left-4 z-20 bg-background/95 backdrop-blur-sm rounded-lg border border-border w-80 max-h-[500px] overflow-hidden flex flex-col">
                    <div className="flex items-center justify-between p-4 border-b border-border">
                        <h3 className="font-semibold text-foreground">All Papers</h3>
                        <button onClick={() => setShowNodeList(false)} className="p-1 hover:bg-secondary rounded">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                    <div className="overflow-y-auto flex-1 p-2">
                        {/* Center paper */}
                        {nodesByType.center.length > 0 && (
                            <div className="mb-3">
                                <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
                                    <div className="w-2 h-2 rounded-full bg-purple-500"></div>
                                    This Paper
                                </div>
                                {nodesByType.center.map(node => (
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
                        
                        {/* Related papers */}
                        {nodesByType.related.length > 0 && (
                            <div className="mb-3">
                                <div className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-muted-foreground">
                                    <div className="w-2 h-2 rounded-full bg-amber-500"></div>
                                    Related ({nodesByType.related.length})
                                </div>
                                {nodesByType.related.slice(0, 15).map(node => (
                                    <button
                                        key={node.id}
                                        onClick={() => focusOnNode(node)}
                                        className="w-full text-left px-2 py-2 text-sm hover:bg-secondary rounded-lg transition-colors group"
                                    >
                                        <div className="flex items-center gap-2">
                                            <span className="flex-1 truncate text-xs">{node.label}</span>
                                            <Focus className="w-3 h-3 opacity-0 group-hover:opacity-100 text-primary" />
                                        </div>
                                        {node.metrics && (
                                            <span className="text-[10px] text-muted-foreground">
                                                {node.metrics.citations} citations
                                            </span>
                                        )}
                                    </button>
                                ))}
                                {nodesByType.related.length > 15 && (
                                    <p className="text-xs text-muted-foreground px-2 py-1">
                                        +{nodesByType.related.length - 15} more...
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

            {/* Legend */}
            <div className="absolute top-4 right-4 z-10 bg-background/90 backdrop-blur-sm rounded-lg p-4 border border-border">
                <h3 className="text-sm font-semibold text-foreground mb-2">Node Types</h3>
                <div className="space-y-2 text-xs mb-3">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#8B5CF6' }}></div>
                        <span className="text-muted-foreground">This Paper</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#3B82F6' }}></div>
                        <span className="text-muted-foreground">Cited Papers</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#10B981' }}></div>
                        <span className="text-muted-foreground">Citing Papers</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#F59E0B' }}></div>
                        <span className="text-muted-foreground">Related Papers</span>
                    </div>
                </div>
                <h3 className="text-sm font-semibold text-foreground mb-2 pt-2 border-t border-border">Connection Strength</h3>
                <div className="space-y-2 text-xs">
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-1.5 rounded" style={{ backgroundColor: '#22C55E' }}></div>
                        <span className="text-muted-foreground">Strong</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-1.5 rounded" style={{ backgroundColor: '#3B82F6' }}></div>
                        <span className="text-muted-foreground">Medium</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-6 h-1.5 rounded" style={{ backgroundColor: '#F59E0B' }}></div>
                        <span className="text-muted-foreground">Weak</span>
                    </div>
                </div>
            </div>

            {/* Hovered node info */}
            {hoveredNode && !showNodeList && (
                <div className="absolute bottom-20 left-4 z-10 bg-background/95 backdrop-blur-sm rounded-lg p-4 border border-border max-w-sm" style={{ borderLeftColor: hoveredNode.color, borderLeftWidth: 3 }}>
                    <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                            <h4 className="font-semibold text-foreground text-sm line-clamp-2 mb-1">
                                {hoveredNode.fullTitle || hoveredNode.label}
                            </h4>
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span className="px-1.5 py-0.5 bg-secondary rounded">{hoveredNode.type}</span>
                                <span>{hoveredNode.category}</span>
                            </div>
                            {hoveredNode.metrics && (
                                <p className="text-xs text-primary mt-2">
                                    📊 {hoveredNode.metrics.citations} citations • Score: {(hoveredNode.metrics.rank * 100).toFixed(0)}
                                </p>
                            )}
                        </div>
                        {hoveredNode.type !== 'center' && (
                            <button 
                                onClick={() => focusOnNode(hoveredNode)}
                                className="p-1.5 bg-primary/10 rounded-lg hover:bg-primary/20 transition-colors"
                                title="Focus on this node"
                            >
                                <Focus className="w-4 h-4 text-primary" />
                            </button>
                        )}
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-2">Click to visit paper • Click focus to zoom</p>
                </div>
            )}

            {/* Controls hint */}
            <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-10 bg-background/90 backdrop-blur-sm rounded-lg px-4 py-2 border border-border">
                <p className="text-xs text-muted-foreground">
                    🖱️ Drag to rotate • Scroll to zoom • Click node to visit • Double-click to focus
                </p>
            </div>

            <ForceGraph3D
                ref={fgRef}
                graphData={graphData}
                nodeLabel={() => ''} // We use custom hover instead
                nodeVal={(node: any) => node.size || 10}
                nodeColor={(node: any) => node.color}
                nodeRelSize={5}
                nodeOpacity={0.9}
                nodeThreeObject={(node: any) => {
                    // Create sphere with label
                    const group = new THREE.Group();
                    
                    // Sphere - slightly smaller for less clutter
                    const baseSize = Math.max(6, (node.size || 8) * 0.8);
                    const geometry = new THREE.SphereGeometry(baseSize);
                    const material = new THREE.MeshLambertMaterial({
                        color: node.color,
                        transparent: true,
                        opacity: focusedNode && focusedNode.id !== node.id ? 0.4 : 0.9,
                    });
                    const sphere = new THREE.Mesh(geometry, material);
                    group.add(sphere);
                    
                    // Add glow for center node or focused node
                    if (node.type === 'center' || (focusedNode && focusedNode.id === node.id)) {
                        const glowGeometry = new THREE.SphereGeometry(baseSize * 1.5);
                        const glowMaterial = new THREE.MeshBasicMaterial({
                            color: node.color,
                            transparent: true,
                            opacity: 0.25,
                        });
                        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
                        group.add(glow);
                    }

                    // Text label (only show if showLabels is true)
                    if (showLabels) {
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
                        if (ctx) {
                            canvas.width = 512;
                            canvas.height = 64;
                            ctx.fillStyle = 'transparent';
                            ctx.fillRect(0, 0, canvas.width, canvas.height);
                            ctx.font = 'bold 28px Arial';
                            ctx.fillStyle = focusedNode && focusedNode.id !== node.id ? 'rgba(255,255,255,0.4)' : 'white';
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            
                            // Truncate label
                            let label = node.label || '';
                            if (label.length > 30) {
                                label = label.substring(0, 27) + '...';
                            }
                            ctx.fillText(label, canvas.width / 2, canvas.height / 2);
                            
                            const texture = new THREE.CanvasTexture(canvas);
                            const spriteMaterial = new THREE.SpriteMaterial({ 
                                map: texture, 
                                transparent: true,
                                opacity: focusedNode && focusedNode.id !== node.id ? 0.3 : 0.9,
                            });
                            const sprite = new THREE.Sprite(spriteMaterial);
                            sprite.scale.set(100, 13, 1);
                            sprite.position.set(0, baseSize + 15, 0);
                            group.add(sprite);
                        }
                    }
                    
                    return group;
                }}
                linkWidth={(link: any) => (link.strength || 0.5) * 2.5 + 0.5}
                linkOpacity={0.5}
                linkColor={(link: any) => getLinkColor(link)}
                linkDirectionalParticles={(link: any) => (link.strength || 0.5) > 0.6 ? 3 : 1}
                linkDirectionalParticleWidth={2}
                linkDirectionalParticleSpeed={0.004}
                linkDirectionalParticleColor={(link: any) => getLinkColor(link)}
                backgroundColor="rgba(0,0,0,0)"
                height={height}
                d3AlphaDecay={0.01}
                d3VelocityDecay={0.3}
                warmupTicks={100}
                onNodeClick={(node: any) => {
                    if (node.id && node.type !== 'center') {
                        window.location.href = `/papers/${node.id}`;
                    }
                }}
                onNodeRightClick={(node: any) => {
                    // Right-click to focus
                    focusOnNode(node);
                }}
                onNodeHover={(node: any) => {
                    setHoveredNode(node || null);
                    document.body.style.cursor = node ? 'pointer' : 'default';
                }}
            />
        </div>
    );
}

export default PaperNetwork3D;
