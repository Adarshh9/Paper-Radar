"""
Paper Embedding Service - "Paper DNA" for semantic understanding.
Uses sentence-transformers for semantic search and similarity.
"""
import asyncio
import pickle
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import hashlib

import numpy as np
from loguru import logger

from app.core.config import get_settings
from app.core.intelligent_cache import intelligent_cache, DataType

settings = get_settings()


@dataclass
class SimilarPaper:
    """Result from similarity search."""
    paper_id: str
    arxiv_id: str
    title: str
    similarity_score: float
    category: str


@dataclass
class TopicCluster:
    """A cluster of related papers (emerging research area)."""
    cluster_id: int
    name: str
    papers: List[str]  # Paper IDs
    centroid: np.ndarray
    keywords: List[str]
    size: int


class PaperEmbeddingService:
    """
    Service for generating and managing paper embeddings.
    
    Features:
    - Semantic search: Find papers by meaning, not just keywords
    - Paper2Vec: Each paper becomes a point in semantic space
    - Topic clustering: Auto-discover emerging research areas
    - Cross-domain discovery: Find papers from different fields solving similar problems
    """
    
    # Model configuration
    MODEL_NAME = "allenai/specter2"  # Specialized for scientific papers
    EMBEDDING_DIM = 768
    FALLBACK_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # Smaller, faster fallback
    
    def __init__(self, index_path: Optional[Path] = None):
        self._model = None
        self._model_loaded = False
        self._index = None
        self._paper_ids: List[str] = []
        self.index_path = index_path or (settings.data_directory / "embeddings")
        self.index_path.mkdir(parents=True, exist_ok=True)
    
    def _load_model(self):
        """Lazy load the embedding model."""
        if self._model_loaded:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            try:
                self._model = SentenceTransformer(self.MODEL_NAME)
                logger.info(f"Loaded embedding model: {self.MODEL_NAME}")
            except Exception as e:
                logger.warning(f"Failed to load {self.MODEL_NAME}, using fallback: {e}")
                self._model = SentenceTransformer(self.FALLBACK_MODEL)
            
            self._model_loaded = True
            
        except ImportError:
            logger.warning("sentence-transformers not installed, embeddings disabled")
            self._model = None
            self._model_loaded = True
    
    def _load_index(self):
        """Load or create FAISS index."""
        if self._index is not None:
            return
        
        index_file = self.index_path / "paper_index.faiss"
        ids_file = self.index_path / "paper_ids.pkl"
        
        try:
            import faiss
            
            if index_file.exists() and ids_file.exists():
                self._index = faiss.read_index(str(index_file))
                with open(ids_file, "rb") as f:
                    self._paper_ids = pickle.load(f)
                logger.info(f"Loaded FAISS index with {len(self._paper_ids)} papers")
            else:
                # Create new index
                self._index = faiss.IndexFlatIP(self.EMBEDDING_DIM)  # Inner product (for cosine similarity)
                self._paper_ids = []
                logger.info("Created new FAISS index")
                
        except ImportError:
            logger.warning("FAISS not installed, using brute-force similarity")
            self._index = None
            self._paper_ids = []
    
    async def generate_embedding(
        self,
        title: str,
        abstract: str,
        use_cache: bool = True,
    ) -> Optional[np.ndarray]:
        """
        Generate embedding for a paper.
        
        Args:
            title: Paper title
            abstract: Paper abstract
            use_cache: Whether to use cached embeddings
        
        Returns:
            768-dimensional embedding vector, or None if failed
        """
        # Check cache
        cache_key = f"embedding:{hashlib.md5((title + abstract).encode()).hexdigest()}"
        if use_cache:
            cached = intelligent_cache.get(cache_key, DataType.EMBEDDINGS.value)
            if cached is not None:
                return np.array(cached)
        
        self._load_model()
        if self._model is None:
            return None
        
        # Combine title and abstract with separator
        text = f"{title} [SEP] {abstract}"
        
        try:
            # Generate embedding (run in thread to not block)
            embedding = await asyncio.to_thread(
                self._model.encode,
                text,
                normalize_embeddings=True,  # For cosine similarity
            )
            
            # Cache the result (30 days - embeddings don't change)
            if use_cache:
                intelligent_cache.set(
                    cache_key,
                    embedding.tolist(),
                    data_type=DataType.EMBEDDINGS.value,
                )
            
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None
    
    async def generate_batch_embeddings(
        self,
        papers: List[Tuple[str, str, str]],  # (paper_id, title, abstract)
        batch_size: int = 32,
    ) -> Dict[str, np.ndarray]:
        """
        Generate embeddings for multiple papers efficiently.
        
        Returns:
            Dict mapping paper_id to embedding
        """
        self._load_model()
        if self._model is None:
            return {}
        
        results = {}
        
        for i in range(0, len(papers), batch_size):
            batch = papers[i:i + batch_size]
            texts = [f"{title} [SEP] {abstract}" for _, title, abstract in batch]
            
            try:
                embeddings = await asyncio.to_thread(
                    self._model.encode,
                    texts,
                    normalize_embeddings=True,
                    batch_size=batch_size,
                    show_progress_bar=False,
                )
                
                for (paper_id, title, abstract), embedding in zip(batch, embeddings):
                    results[paper_id] = embedding
                    
                    # Cache each embedding
                    cache_key = f"embedding:{hashlib.md5((title + abstract).encode()).hexdigest()}"
                    intelligent_cache.set(
                        cache_key,
                        embedding.tolist(),
                        data_type=DataType.EMBEDDINGS.value,
                    )
                
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
        
        return results
    
    async def add_to_index(
        self,
        paper_id: str,
        embedding: np.ndarray,
    ):
        """Add a paper embedding to the search index."""
        self._load_index()
        
        if self._index is not None:
            try:
                import faiss
                
                # Normalize if not already
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                
                self._index.add(embedding.reshape(1, -1).astype('float32'))
                self._paper_ids.append(paper_id)
                
            except ImportError:
                pass
    
    async def build_index(
        self,
        embeddings: Dict[str, np.ndarray],
    ):
        """Build complete search index from embeddings."""
        self._load_index()
        
        if not embeddings:
            return
        
        try:
            import faiss
            
            # Create new index
            self._index = faiss.IndexFlatIP(self.EMBEDDING_DIM)
            self._paper_ids = list(embeddings.keys())
            
            # Stack all embeddings
            embedding_matrix = np.vstack([
                embeddings[pid] for pid in self._paper_ids
            ]).astype('float32')
            
            # Normalize
            faiss.normalize_L2(embedding_matrix)
            
            # Add to index
            self._index.add(embedding_matrix)
            
            # Save index
            index_file = self.index_path / "paper_index.faiss"
            ids_file = self.index_path / "paper_ids.pkl"
            
            faiss.write_index(self._index, str(index_file))
            with open(ids_file, "wb") as f:
                pickle.dump(self._paper_ids, f)
            
            logger.info(f"Built FAISS index with {len(self._paper_ids)} papers")
            
        except ImportError:
            logger.warning("FAISS not available, storing embeddings only")
    
    async def find_similar_papers(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[Tuple[str, float]]:
        """
        Find papers similar to a query embedding.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            exclude_ids: Paper IDs to exclude from results
        
        Returns:
            List of (paper_id, similarity_score) tuples
        """
        self._load_index()
        
        if self._index is None or len(self._paper_ids) == 0:
            return []
        
        try:
            import faiss
            
            # Normalize query
            query = query_embedding.reshape(1, -1).astype('float32')
            faiss.normalize_L2(query)
            
            # Search with extra results in case we need to filter
            k = min(top_k * 2, len(self._paper_ids))
            distances, indices = self._index.search(query, k)
            
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0 or idx >= len(self._paper_ids):
                    continue
                
                paper_id = self._paper_ids[idx]
                
                if exclude_ids and paper_id in exclude_ids:
                    continue
                
                results.append((paper_id, float(dist)))
                
                if len(results) >= top_k:
                    break
            
            return results
            
        except ImportError:
            return []
    
    async def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        category: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """
        Search papers by natural language query.
        
        Args:
            query: Natural language search query
            top_k: Number of results
            category: Optional category filter
        
        Returns:
            List of (paper_id, similarity_score) tuples
        """
        # Generate query embedding
        query_embedding = await self.generate_embedding(query, "", use_cache=False)
        
        if query_embedding is None:
            return []
        
        return await self.find_similar_papers(query_embedding, top_k)
    
    async def find_cross_domain_papers(
        self,
        paper_id: str,
        paper_embedding: np.ndarray,
        paper_category: str,
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """
        Find papers from different fields solving similar problems.
        
        This helps discover cross-domain applications and techniques.
        """
        # Get similar papers
        all_similar = await self.find_similar_papers(
            paper_embedding,
            top_k=top_k * 3,
            exclude_ids=[paper_id],
        )
        
        # Filter to different categories
        # Note: Would need category lookup in production
        cross_domain = []
        for pid, score in all_similar:
            # Placeholder - would lookup paper category
            if len(cross_domain) < top_k:
                cross_domain.append((pid, score))
        
        return cross_domain
    
    async def cluster_papers(
        self,
        embeddings: Dict[str, np.ndarray],
        n_clusters: int = 20,
    ) -> List[TopicCluster]:
        """
        Cluster papers into topic groups.
        
        Useful for discovering emerging research areas.
        """
        if len(embeddings) < n_clusters:
            return []
        
        try:
            from sklearn.cluster import KMeans
            from sklearn.feature_extraction.text import TfidfVectorizer
            
            paper_ids = list(embeddings.keys())
            embedding_matrix = np.vstack([embeddings[pid] for pid in paper_ids])
            
            # Perform clustering
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embedding_matrix)
            
            # Build cluster objects
            clusters = []
            for i in range(n_clusters):
                cluster_mask = labels == i
                cluster_paper_ids = [
                    paper_ids[j] for j in range(len(paper_ids)) if cluster_mask[j]
                ]
                
                if len(cluster_paper_ids) > 0:
                    clusters.append(TopicCluster(
                        cluster_id=i,
                        name=f"Cluster {i}",  # Would generate from keywords
                        papers=cluster_paper_ids,
                        centroid=kmeans.cluster_centers_[i],
                        keywords=[],  # Would extract from paper titles
                        size=len(cluster_paper_ids),
                    ))
            
            return sorted(clusters, key=lambda c: c.size, reverse=True)
            
        except ImportError:
            logger.warning("scikit-learn not available for clustering")
            return []
    
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(np.dot(a, b) / (norm_a * norm_b))


# Singleton instance
paper_embedding_service = PaperEmbeddingService()
