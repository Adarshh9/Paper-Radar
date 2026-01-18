"""
3D Paper Relationship Graph Service.
Generates data for interactive 3D visualizations of paper relationships.
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

import numpy as np
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from loguru import logger

from app.core.database import SessionLocal
from app.core.intelligent_cache import intelligent_cache, DataType
from app.models import Paper, PaperMetrics, PaperRelationship


class PaperRelationship3DService:
    """Generate 3D graph data for paper relationships."""
    
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour cache
    
    async def get_paper_network_3d(
        self,
        paper_id: str,
        depth: int = 2,
        max_nodes: int = 50,
    ) -> Dict[str, Any]:
        """
        Generate 3D network graph for a paper and its relationships.
        
        Args:
            paper_id: Center paper ID
            depth: How many citation hops to traverse
            max_nodes: Maximum nodes to return
        
        Returns:
            {
                "nodes": [
                    {
                        "id": "uuid",
                        "label": "Paper Title",
                        "type": "center|cited|citing|related",
                        "x": float, "y": float, "z": float,
                        "size": int,
                        "color": "#hex",
                        "metrics": {...}
                    }
                ],
                "links": [
                    {
                        "source": "uuid1",
                        "target": "uuid2",
                        "type": "cites|cited_by|related",
                        "strength": float
                    }
                ],
                "stats": {...}
            }
        """
        cache_key = f"3d_network:{paper_id}:{depth}:{max_nodes}"
        cached = intelligent_cache.get(cache_key, DataType.VISUALIZATIONS.value)
        if cached:
            return cached
        
        db = SessionLocal()
        
        try:
            # Get center paper
            center_paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if not center_paper:
                return {"nodes": [], "links": [], "error": "Paper not found"}
            
            # Build graph
            nodes = []
            links = []
            visited = set()
            
            # Add center node
            center_node = self._create_node(center_paper, "center", (0, 0, 0))
            nodes.append(center_node)
            visited.add(str(paper_id))
            
            # Get related papers (simplified - using category similarity)
            # In production, use actual citation data from PaperRelationship table
            related_papers = self._get_related_papers(db, center_paper, max_nodes - 1)
            
            # Position nodes in 3D space using force-directed layout simulation
            positions = self._calculate_3d_positions(len(related_papers))
            
            for i, (paper, relation_type, strength) in enumerate(related_papers):
                if str(paper.id) in visited:
                    continue
                
                node = self._create_node(
                    paper, 
                    relation_type,
                    positions[i] if i < len(positions) else (0, 0, 0)
                )
                nodes.append(node)
                visited.add(str(paper.id))
                
                # Create link
                links.append({
                    "source": str(paper_id),
                    "target": str(paper.id),
                    "type": relation_type,
                    "strength": strength,
                })
            
            result = {
                "nodes": nodes,
                "links": links,
                "stats": {
                    "total_nodes": len(nodes),
                    "total_links": len(links),
                    "center_paper": center_paper.title,
                    "depth": depth,
                },
            }
            
            # Cache result
            intelligent_cache.set(cache_key, result, data_type=DataType.VISUALIZATIONS.value)
            
            return result
            
        finally:
            db.close()
    
    def _create_node(
        self, 
        paper: Paper, 
        node_type: str,
        position: Tuple[float, float, float]
    ) -> Dict[str, Any]:
        """Create a 3D node from a paper."""
        # Determine color based on type
        color_map = {
            "center": "#8B5CF6",      # Purple
            "cited": "#3B82F6",       # Blue (papers this cites)
            "citing": "#10B981",      # Green (papers citing this)
            "related": "#F59E0B",     # Orange (similar papers)
            "co_author": "#EC4899",   # Pink
        }
        
        # Size based on citations
        citation_count = paper.metrics.citation_count if paper.metrics else 0
        size = max(5, min(30, 5 + citation_count / 10))
        
        return {
            "id": str(paper.id),
            "label": paper.title[:60] + ("..." if len(paper.title) > 60 else ""),
            "fullTitle": paper.title,
            "type": node_type,
            "x": position[0],
            "y": position[1],
            "z": position[2],
            "size": size,
            "color": color_map.get(node_type, "#94A3B8"),
            "arxivId": paper.arxiv_id,
            "publishedDate": paper.published_date.isoformat(),
            "category": paper.primary_category,
            "metrics": {
                "citations": citation_count,
                "velocity": paper.metrics.citation_velocity_7d if paper.metrics else 0,
                "rank": paper.metrics.overall_rank_score if paper.metrics else 0,
            },
        }
    
    def _get_related_papers(
        self,
        db: Session,
        center_paper: Paper,
        limit: int
    ) -> List[Tuple[Paper, str, float]]:
        """
        Get related papers with relationship type and strength.
        Returns: [(paper, relation_type, strength), ...]
        """
        related = []
        
        # 1. Papers in same category (related)
        same_category = (
            db.query(Paper)
            .filter(
                Paper.primary_category == center_paper.primary_category,
                Paper.id != center_paper.id,
            )
            .join(PaperMetrics)
            .order_by(PaperMetrics.overall_rank_score.desc())
            .limit(limit // 2)
            .all()
        )
        
        for paper in same_category:
            # Calculate similarity strength (0-1)
            shared_categories = set(center_paper.categories) & set(paper.categories)
            strength = len(shared_categories) / max(len(center_paper.categories), 1)
            related.append((paper, "related", strength))
        
        # 2. Papers by same authors (co-author network)
        center_authors = {a["name"] for a in center_paper.authors}
        
        if center_authors:
            # Find papers with overlapping authors
            all_papers = db.query(Paper).filter(Paper.id != center_paper.id).limit(200).all()
            
            for paper in all_papers:
                paper_authors = {a["name"] for a in paper.authors}
                overlap = center_authors & paper_authors
                
                if overlap:
                    strength = len(overlap) / len(center_authors)
                    related.append((paper, "co_author", strength))
                    
                    if len(related) >= limit:
                        break
        
        # Sort by strength and limit
        related.sort(key=lambda x: x[2], reverse=True)
        return related[:limit]
    
    def _calculate_3d_positions(self, n: int) -> List[Tuple[float, float, float]]:
        """
        Calculate 3D positions for nodes using spherical distribution.
        Creates aesthetically pleasing layouts with good spacing.
        """
        positions = []
        
        # Use golden spiral for even distribution on sphere
        golden_ratio = (1 + 5 ** 0.5) / 2
        
        # MUCH larger radius for better spacing
        base_radius = 300
        
        for i in range(n):
            # Spherical coordinates
            theta = 2 * np.pi * i / golden_ratio
            phi = np.arccos(1 - 2 * (i + 0.5) / n)
            
            # Vary distance from center for 3D depth effect
            # Create shells at different radii
            shell = (i % 3)  # 0, 1, 2 alternating shells
            radius = base_radius + (shell * 100) + np.random.normal(0, 30)
            
            x = radius * np.sin(phi) * np.cos(theta)
            y = radius * np.sin(phi) * np.sin(theta)
            z = radius * np.cos(phi)
            
            positions.append((float(x), float(y), float(z)))
        
        return positions
    
    async def get_category_cluster_3d(
        self,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Generate 3D cluster visualization of papers by category.
        Papers are grouped and positioned based on their categories.
        """
        cache_key = f"3d_cluster:{category}:{limit}"
        cached = intelligent_cache.get(cache_key, DataType.VISUALIZATIONS.value)
        if cached:
            return cached
        
        db = SessionLocal()
        
        try:
            # Get papers
            query = db.query(Paper).join(PaperMetrics)
            
            if category:
                query = query.filter(Paper.primary_category == category)
            
            papers = (
                query
                .order_by(PaperMetrics.overall_rank_score.desc())
                .limit(limit)
                .all()
            )
            
            # Group by category
            category_groups = defaultdict(list)
            for paper in papers:
                category_groups[paper.primary_category].append(paper)
            
            # Create clusters in 3D space
            nodes = []
            cluster_centers = self._calculate_cluster_centers(len(category_groups))
            
            for idx, (cat, cat_papers) in enumerate(category_groups.items()):
                center = cluster_centers[idx] if idx < len(cluster_centers) else (0, 0, 0)
                
                # Position papers around cluster center
                for i, paper in enumerate(cat_papers):
                    # Add some spread around the center
                    angle = 2 * np.pi * i / len(cat_papers)
                    spread = 30
                    
                    x = center[0] + spread * np.cos(angle)
                    y = center[1] + spread * np.sin(angle)
                    z = center[2] + spread * np.sin(2 * angle)  # Add z variation
                    
                    nodes.append(self._create_node(paper, "cluster", (x, y, z)))
            
            result = {
                "nodes": nodes,
                "links": [],  # No links in cluster view
                "clusters": [
                    {
                        "category": cat,
                        "center": list(cluster_centers[idx]),
                        "count": len(cat_papers),
                        "color": self._get_category_color(cat),
                    }
                    for idx, (cat, cat_papers) in enumerate(category_groups.items())
                ],
                "stats": {
                    "total_papers": len(papers),
                    "total_clusters": len(category_groups),
                },
            }
            
            intelligent_cache.set(cache_key, result, data_type=DataType.VISUALIZATIONS.value)
            return result
            
        finally:
            db.close()
    
    def _calculate_cluster_centers(self, n: int) -> List[Tuple[float, float, float]]:
        """Calculate positions for cluster centers."""
        centers = []
        
        for i in range(n):
            angle = 2 * np.pi * i / n
            radius = 150
            
            x = radius * np.cos(angle)
            y = radius * np.sin(angle)
            z = 50 * np.sin(3 * angle)  # Vary height
            
            centers.append((float(x), float(y), float(z)))
        
        return centers
    
    def _get_category_color(self, category: str) -> str:
        """Get consistent color for a category."""
        color_map = {
            "cs.AI": "#8B5CF6",
            "cs.LG": "#3B82F6",
            "cs.CV": "#10B981",
            "cs.CL": "#F59E0B",
            "cs.NE": "#EC4899",
            "stat.ML": "#14B8A6",
        }
        return color_map.get(category, "#94A3B8")


# Singleton
paper_relationship_3d_service = PaperRelationship3DService()
