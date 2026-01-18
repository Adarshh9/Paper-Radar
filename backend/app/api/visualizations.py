"""
3D Visualization API endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Paper
from app.services.paper_relationship_3d import paper_relationship_3d_service
from app.services.paper_topic_analysis_3d import paper_topic_analysis_3d_service

router = APIRouter()


@router.get("/papers/{paper_id}/network-3d")
async def get_paper_network_3d(
    paper_id: UUID,
    depth: int = Query(2, ge=1, le=3, description="Citation depth"),
    max_nodes: int = Query(50, ge=10, le=100, description="Maximum nodes"),
    db: Session = Depends(get_db),
):
    """
    Get 3D network graph of paper relationships.
    
    Returns nodes and links for interactive 3D visualization showing:
    - Papers this paper cites
    - Papers citing this paper
    - Related papers in same field
    - Co-author network
    """
    graph = await paper_relationship_3d_service.get_paper_network_3d(
        paper_id=str(paper_id),
        depth=depth,
        max_nodes=max_nodes,
    )
    
    if "error" in graph:
        raise HTTPException(status_code=404, detail=graph["error"])
    
    return graph


@router.get("/papers/{paper_id}/topics-3d")
async def get_paper_topics_3d(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get 3D visualization of topics and concepts within a paper.
    
    Returns hierarchical 3D graph showing:
    - Main concepts (center, large)
    - Building blocks (inner ring)
    - Techniques used (middle ring)
    - Applications (outer ring)
    - Relationships between concepts
    """
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    graph = await paper_topic_analysis_3d_service.analyze_paper_topics_3d(
        paper_id=str(paper_id),
        title=paper.title,
        abstract=paper.abstract,
    )
    
    return graph


@router.get("/papers/{paper_id}/learning-path-3d")
async def get_learning_path_3d(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get 3D learning path visualization.
    
    Shows what you need to know before reading (prerequisites below)
    and what you'll learn after reading (outcomes above).
    """
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    graph = await paper_topic_analysis_3d_service.get_learning_path_3d(
        paper_id=str(paper_id),
        title=paper.title,
        abstract=paper.abstract,
    )
    
    return graph


@router.get("/visualizations/category-cluster-3d")
async def get_category_cluster_3d(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(100, ge=20, le=200, description="Number of papers"),
    db: Session = Depends(get_db),
):
    """
    Get 3D cluster visualization of papers grouped by category.
    
    Shows papers as 3D clusters, great for exploring the research landscape.
    """
    graph = await paper_relationship_3d_service.get_category_cluster_3d(
        category=category,
        limit=limit,
    )
    
    return graph
