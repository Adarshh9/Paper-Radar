"""
Optimized Database Queries and Repository Layer.
Implements efficient querying patterns to avoid N+1 problems and optimize performance.
"""
from datetime import date, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import func, desc, case, literal_column, text, Index
from sqlalchemy.orm import Session, joinedload, selectinload, contains_eager
from loguru import logger

from app.models import Paper, PaperMetrics, PaperImplementation, PaperSummary
from app.core.intelligent_cache import intelligent_cache, DataType


# ==============================================================================
# Composite Indexes (to be added via migration)
# ==============================================================================

# These indexes should be created via Alembic migration:
#
# CREATE INDEX ix_papers_category_date_score ON papers (primary_category, published_date DESC);
# CREATE INDEX ix_paper_metrics_score_citations ON paper_metrics (overall_rank_score DESC, citation_count DESC);
# CREATE INDEX ix_papers_search ON papers USING gin (to_tsvector('english', title || ' ' || abstract));
# CREATE INDEX ix_paper_implementations_paper_stars ON paper_implementations (paper_id, stars DESC);

RECOMMENDED_INDEXES = [
    # Category + date + score for filtered trending queries
    Index('ix_papers_category_date_score', 
          Paper.primary_category, Paper.published_date.desc()),
    
    # Score + citations for ranking queries
    Index('ix_paper_metrics_rank',
          PaperMetrics.overall_rank_score.desc(), 
          PaperMetrics.citation_count.desc()),
    
    # Paper implementations by paper and stars
    Index('ix_implementations_paper_stars',
          PaperImplementation.paper_id, 
          PaperImplementation.stars.desc()),
]


# ==============================================================================
# Optimized Repository Methods
# ==============================================================================

class OptimizedPaperRepository:
    """
    Optimized paper repository with efficient query patterns.
    
    Fixes:
    - N+1 query problems using eager loading
    - Single optimized query instead of multiple queries
    - Database-level caching strategy
    - Composite indexes for common query patterns
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_paper_with_relations(self, paper_id: UUID) -> Optional[Paper]:
        """
        Get a single paper with all relations loaded in one query.
        
        Avoids N+1 by using joinedload for one-to-one and selectinload for one-to-many.
        """
        return (
            self.db.query(Paper)
            .options(
                joinedload(Paper.metrics),
                joinedload(Paper.summary),
                selectinload(Paper.implementations),
            )
            .filter(Paper.id == paper_id)
            .first()
        )
    
    def get_papers_by_ids(
        self,
        paper_ids: List[UUID],
        maintain_order: bool = True,
    ) -> List[Paper]:
        """
        Get multiple papers by IDs in a single optimized query.
        
        Uses a single query with ORDER BY FIELD() equivalent to maintain order.
        """
        if not paper_ids:
            return []
        
        # Single query with eager loading
        papers = (
            self.db.query(Paper)
            .options(
                joinedload(Paper.metrics),
                joinedload(Paper.summary),
                selectinload(Paper.implementations),
            )
            .filter(Paper.id.in_(paper_ids))
            .all()
        )
        
        if maintain_order:
            # Maintain original order
            paper_map = {p.id: p for p in papers}
            return [paper_map[pid] for pid in paper_ids if pid in paper_map]
        
        return papers
    
    def get_trending_papers_optimized(
        self,
        timeframe_days: int = 7,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> List[Paper]:
        """
        Optimized trending papers query.
        
        Uses a single query with proper indexing hints.
        """
        cache_key = f"trending:{timeframe_days}:{limit}:{category or 'all'}"
        cached = intelligent_cache.get(cache_key, DataType.TRENDING_PAPERS.value)
        if cached:
            # Return cached paper IDs and fetch full data
            return self.get_papers_by_ids([UUID(pid) for pid in cached])
        
        threshold_date = date.today() - timedelta(days=timeframe_days)
        
        # Build optimized query
        query = (
            self.db.query(Paper)
            .options(
                joinedload(Paper.metrics),
                joinedload(Paper.summary),
                selectinload(Paper.implementations),
            )
            .outerjoin(PaperMetrics)
            .filter(Paper.published_date >= threshold_date)
        )
        
        if category:
            query = query.filter(Paper.primary_category == category)
        
        # Order by rank score with fallback
        papers = (
            query
            .order_by(
                desc(func.coalesce(PaperMetrics.overall_rank_score, 0)),
                desc(Paper.published_date),
            )
            .limit(limit)
            .all()
        )
        
        # Cache paper IDs (not full objects)
        intelligent_cache.set(
            cache_key,
            [str(p.id) for p in papers],
            data_type=DataType.TRENDING_PAPERS.value,
        )
        
        return papers
    
    def get_recommendations_optimized(
        self,
        user_id: UUID,
        interested_categories: List[str],
        interacted_paper_ids: List[UUID],
        limit: int = 20,
    ) -> List[Paper]:
        """
        Optimized recommendations query.
        
        Fixes N+1 by:
        1. Using a single query with proper joins
        2. Avoiding multiple subqueries
        3. Using selectinload for collections
        """
        # Build base query with all needed relations
        query = (
            self.db.query(Paper)
            .options(
                joinedload(Paper.metrics),
                joinedload(Paper.summary),
                selectinload(Paper.implementations),
            )
            .outerjoin(PaperMetrics)
        )
        
        # Filter by categories
        if interested_categories:
            query = query.filter(Paper.primary_category.in_(interested_categories))
        
        # Exclude interacted papers
        if interacted_paper_ids:
            query = query.filter(~Paper.id.in_(interacted_paper_ids))
        
        # Order by rank score
        papers = (
            query
            .order_by(desc(func.coalesce(PaperMetrics.overall_rank_score, 0)))
            .limit(limit)
            .all()
        )
        
        return papers
    
    def get_similar_papers_optimized(
        self,
        paper: Paper,
        limit: int = 10,
    ) -> List[Paper]:
        """
        Get similar papers with optimized query.
        
        Uses category and implements efficient filtering.
        """
        cache_key = f"similar:{paper.id}:{limit}"
        cached = intelligent_cache.get(cache_key, DataType.SEARCH_RESULTS.value)
        if cached:
            return self.get_papers_by_ids([UUID(pid) for pid in cached])
        
        # Single optimized query
        similar = (
            self.db.query(Paper)
            .options(
                joinedload(Paper.metrics),
                joinedload(Paper.summary),
                selectinload(Paper.implementations),
            )
            .outerjoin(PaperMetrics)
            .filter(
                Paper.id != paper.id,
                Paper.primary_category == paper.primary_category,
            )
            .order_by(desc(func.coalesce(PaperMetrics.overall_rank_score, 0)))
            .limit(limit)
            .all()
        )
        
        # Cache result
        intelligent_cache.set(
            cache_key,
            [str(p.id) for p in similar],
            data_type=DataType.SEARCH_RESULTS.value,
        )
        
        return similar
    
    def search_papers_optimized(
        self,
        query_text: str,
        categories: Optional[List[str]] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        has_implementation: bool = False,
        min_citations: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Paper], int]:
        """
        Optimized search with full-text matching.
        
        Returns (papers, total_count) tuple.
        """
        # Build search query
        search_term = f"%{query_text}%"
        
        # Count query (separate for efficiency)
        count_query = self.db.query(func.count(Paper.id)).filter(
            Paper.title.ilike(search_term) | Paper.abstract.ilike(search_term)
        )
        
        # Main query with eager loading
        main_query = (
            self.db.query(Paper)
            .options(
                joinedload(Paper.metrics),
                joinedload(Paper.summary),
                selectinload(Paper.implementations),
            )
            .filter(
                Paper.title.ilike(search_term) | Paper.abstract.ilike(search_term)
            )
        )
        
        # Apply filters to both queries
        if categories:
            count_query = count_query.filter(Paper.primary_category.in_(categories))
            main_query = main_query.filter(Paper.primary_category.in_(categories))
        
        if date_from:
            count_query = count_query.filter(Paper.published_date >= date_from)
            main_query = main_query.filter(Paper.published_date >= date_from)
        
        if date_to:
            count_query = count_query.filter(Paper.published_date <= date_to)
            main_query = main_query.filter(Paper.published_date <= date_to)
        
        if has_implementation:
            # Subquery for papers with implementations
            impl_subquery = (
                self.db.query(PaperImplementation.paper_id)
                .distinct()
                .subquery()
            )
            count_query = count_query.filter(Paper.id.in_(impl_subquery))
            main_query = main_query.filter(Paper.id.in_(impl_subquery))
        
        if min_citations:
            count_query = count_query.join(PaperMetrics).filter(
                PaperMetrics.citation_count >= min_citations
            )
            main_query = main_query.join(PaperMetrics, isouter=True).filter(
                func.coalesce(PaperMetrics.citation_count, 0) >= min_citations
            )
        
        # Get total count
        total = count_query.scalar()
        
        # Apply pagination and ordering
        offset = (page - 1) * page_size
        papers = (
            main_query
            .outerjoin(PaperMetrics)
            .order_by(
                desc(func.coalesce(PaperMetrics.overall_rank_score, 0)),
                desc(Paper.published_date),
            )
            .offset(offset)
            .limit(page_size)
            .all()
        )
        
        return papers, total
    
    def get_papers_needing_update(
        self,
        hours_since_update: int = 24,
        limit: int = 100,
    ) -> List[Paper]:
        """
        Get papers that need metrics update.
        
        Prioritizes:
        1. Papers with no metrics
        2. Papers with high velocity (need frequent updates)
        3. Papers with stale data
        """
        cutoff_time = date.today() - timedelta(hours=hours_since_update)
        
        # Papers without metrics (highest priority)
        no_metrics = (
            self.db.query(Paper)
            .outerjoin(PaperMetrics)
            .filter(PaperMetrics.id.is_(None))
            .limit(limit // 3)
            .all()
        )
        
        # High velocity papers (need frequent updates)
        remaining_limit = limit - len(no_metrics)
        high_velocity = (
            self.db.query(Paper)
            .join(PaperMetrics)
            .filter(
                PaperMetrics.citation_velocity_7d > 10,
                PaperMetrics.last_metrics_update < cutoff_time,
            )
            .order_by(desc(PaperMetrics.citation_velocity_7d))
            .limit(remaining_limit // 2)
            .all()
        )
        
        # Stale papers
        remaining_limit = limit - len(no_metrics) - len(high_velocity)
        stale = (
            self.db.query(Paper)
            .join(PaperMetrics)
            .filter(PaperMetrics.last_metrics_update < cutoff_time)
            .order_by(PaperMetrics.last_metrics_update.asc())
            .limit(remaining_limit)
            .all()
        )
        
        return no_metrics + high_velocity + stale
    
    def bulk_update_metrics(
        self,
        updates: List[Dict[str, Any]],
    ) -> int:
        """
        Bulk update paper metrics efficiently.
        
        Uses bulk update instead of individual updates.
        """
        if not updates:
            return 0
        
        updated = 0
        for batch_start in range(0, len(updates), 100):
            batch = updates[batch_start:batch_start + 100]
            
            for update in batch:
                paper_id = update.pop('paper_id')
                self.db.query(PaperMetrics).filter(
                    PaperMetrics.paper_id == paper_id
                ).update(update, synchronize_session=False)
                updated += 1
            
            self.db.commit()
        
        return updated
    
    def get_category_stats_optimized(self) -> List[Dict[str, Any]]:
        """
        Get category statistics in a single efficient query.
        """
        cache_key = "category_stats"
        cached = intelligent_cache.get(cache_key)
        if cached:
            return cached
        
        # Single aggregation query
        result = (
            self.db.query(
                Paper.primary_category,
                func.count(Paper.id).label("paper_count"),
                func.avg(PaperMetrics.citation_count).label("avg_citations"),
                func.avg(PaperMetrics.overall_rank_score).label("avg_score"),
            )
            .outerjoin(PaperMetrics)
            .group_by(Paper.primary_category)
            .order_by(desc("paper_count"))
            .all()
        )
        
        stats = [
            {
                "category": row[0],
                "paper_count": row[1],
                "avg_citations": float(row[2]) if row[2] else 0,
                "avg_score": float(row[3]) if row[3] else 0,
            }
            for row in result
        ]
        
        # Cache for 6 hours
        intelligent_cache.set(cache_key, stats, ttl_seconds=21600)
        
        return stats


# ==============================================================================
# Database Caching Strategy
# ==============================================================================

class DatabaseCacheStrategy:
    """
    Implements database-level caching strategy.
    
    - Query result caching with intelligent TTL
    - Materialized view patterns for expensive queries
    - Cache invalidation on writes
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.repo = OptimizedPaperRepository(db)
    
    def get_trending_with_caching(
        self,
        timeframe: str = "week",
        limit: int = 20,
        category: Optional[str] = None,
    ) -> List[Paper]:
        """
        Get trending papers with intelligent caching.
        
        TTL is shorter for recent timeframes, longer for historical.
        """
        days_map = {"day": 1, "week": 7, "month": 30}
        days = days_map.get(timeframe, 7)
        
        # TTL varies by timeframe volatility
        ttl_map = {"day": 300, "week": 600, "month": 3600}
        ttl = ttl_map.get(timeframe, 600)
        
        cache_key = f"trending_cached:{timeframe}:{limit}:{category or 'all'}"
        cached = intelligent_cache.get(cache_key, DataType.TRENDING_PAPERS.value)
        
        if cached:
            paper_ids = [UUID(pid) for pid in cached]
            return self.repo.get_papers_by_ids(paper_ids)
        
        papers = self.repo.get_trending_papers_optimized(days, limit, category)
        
        # Cache paper IDs with appropriate TTL
        intelligent_cache.set(
            cache_key,
            [str(p.id) for p in papers],
            data_type=DataType.TRENDING_PAPERS.value,
            ttl_seconds=ttl,
        )
        
        return papers
    
    def invalidate_paper_cache(self, paper_id: UUID):
        """Invalidate all caches related to a specific paper."""
        patterns = [
            f"paper:{paper_id}",
            f"similar:{paper_id}",
            f"trending:",  # Partial match
            "recommendations:",  # Partial match
        ]
        
        for pattern in patterns:
            intelligent_cache.invalidate_pattern(pattern)
    
    def invalidate_category_cache(self, category: str):
        """Invalidate caches related to a category."""
        intelligent_cache.invalidate_pattern(f"trending:*:{category}")
        intelligent_cache.invalidate_pattern("category_stats")
