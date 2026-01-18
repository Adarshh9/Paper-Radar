"""
Intra-Paper Topic Analysis Service.
Generates 3D visualizations of topics, concepts, and techniques within a single paper.
"""
import asyncio
import re
from typing import List, Dict, Any, Set, Tuple, Optional
from collections import Counter, defaultdict

import numpy as np
from loguru import logger

from app.core.intelligent_cache import intelligent_cache, DataType
from app.services.llm_service_enhanced import enhanced_llm_service


class PaperTopicAnalysis3DService:
    """Analyze and visualize topics within a paper in 3D."""
    
    def __init__(self):
        self.cache_ttl = 7200  # 2 hours cache
    
    async def analyze_paper_topics_3d(
        self,
        paper_id: str,
        title: str,
        abstract: str,
    ) -> Dict[str, Any]:
        """
        Extract and visualize topics, concepts, and techniques from a paper.
        
        Returns 3D graph structure with:
        - Main concepts as large central nodes
        - Techniques as medium nodes
        - Applications as smaller outer nodes
        - Relationships shown as links
        """
        cache_key = f"topics_3d:{paper_id}"
        cached = intelligent_cache.get(cache_key, DataType.VISUALIZATIONS.value)
        if cached:
            return cached
        
        # Extract topics using LLM
        topics_data = await self._extract_topics_with_llm(title, abstract)
        
        if not topics_data:
            # Fallback to keyword extraction
            topics_data = self._extract_topics_keyword_based(title, abstract)
        
        # Build 3D graph
        graph = self._build_3d_topic_graph(topics_data)
        
        # Cache result
        intelligent_cache.set(cache_key, graph, data_type=DataType.VISUALIZATIONS.value)
        
        return graph
    
    async def _extract_topics_with_llm(
        self,
        title: str,
        abstract: str,
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to extract structured topics from paper."""
        if not enhanced_llm_service.client:
            return None
        
        try:
            await enhanced_llm_service._rate_limit()
            
            prompt = f"""Analyze this research paper and extract key topics, concepts, and techniques.

Title: {title}
Abstract: {abstract}

Extract and categorize into:
1. Main Concepts (2-4): Core ideas or theories (e.g., "Attention Mechanism", "Neural Architecture")
2. Techniques (3-6): Specific methods or algorithms (e.g., "Multi-Head Attention", "Positional Encoding")
3. Applications (2-4): Use cases or domains (e.g., "Machine Translation", "Text Generation")
4. Building Blocks (3-5): Fundamental components (e.g., "Transformers", "Feed-Forward Networks")

Respond ONLY with valid JSON:
{{
  "main_concepts": ["concept1", "concept2"],
  "techniques": ["tech1", "tech2", "tech3"],
  "applications": ["app1", "app2"],
  "building_blocks": ["block1", "block2"],
  "relationships": [
    {{"from": "concept1", "to": "tech1", "type": "uses"}},
    {{"from": "tech1", "to": "app1", "type": "enables"}}
  ]
}}"""

            response = await asyncio.to_thread(
                lambda: enhanced_llm_service.client.chat.completions.create(
                    model=enhanced_llm_service.FAST_MODEL,
                    messages=[
                        {"role": "system", "content": "You are an expert at analyzing research papers and extracting structured information. Respond only with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000,
                )
            )
            
            if response and response.choices:
                import json
                content = response.choices[0].message.content
                # Clean response
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    cleaned = "\n".join(cleaned.split("\n")[1:-1])
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:].strip()
                
                data = json.loads(cleaned)
                return data
                
        except Exception as e:
            logger.warning(f"LLM topic extraction failed: {e}")
        
        return None
    
    def _extract_topics_keyword_based(
        self,
        title: str,
        abstract: str,
    ) -> Dict[str, Any]:
        """Fallback keyword-based topic extraction."""
        text = f"{title} {abstract}".lower()
        
        # Common ML/AI concepts
        concept_keywords = {
            "attention": "Attention Mechanism",
            "transformer": "Transformer Architecture",
            "neural network": "Neural Networks",
            "deep learning": "Deep Learning",
            "machine learning": "Machine Learning",
            "reinforcement": "Reinforcement Learning",
            "supervised": "Supervised Learning",
            "unsupervised": "Unsupervised Learning",
            "convolution": "Convolutional Networks",
            "recurrent": "Recurrent Networks",
        }
        
        technique_keywords = {
            "training": "Training Methods",
            "optimization": "Optimization",
            "backpropagation": "Backpropagation",
            "gradient": "Gradient Descent",
            "regularization": "Regularization",
            "dropout": "Dropout",
            "batch normalization": "Batch Normalization",
        }
        
        application_keywords = {
            "translation": "Machine Translation",
            "classification": "Classification",
            "detection": "Object Detection",
            "segmentation": "Image Segmentation",
            "generation": "Text Generation",
            "speech": "Speech Recognition",
        }
        
        # Find matches
        main_concepts = [v for k, v in concept_keywords.items() if k in text]
        techniques = [v for k, v in technique_keywords.items() if k in text]
        applications = [v for k, v in application_keywords.items() if k in text]
        
        # Create simple relationships
        relationships = []
        for concept in main_concepts[:2]:
            for tech in techniques[:2]:
                relationships.append({"from": concept, "to": tech, "type": "uses"})
            for app in applications[:2]:
                relationships.append({"from": concept, "to": app, "type": "enables"})
        
        return {
            "main_concepts": main_concepts[:4] or ["Core Concept"],
            "techniques": techniques[:6] or ["Method"],
            "applications": applications[:4] or ["Application"],
            "building_blocks": ["Neural Network", "Data Processing"],
            "relationships": relationships,
        }
    
    def _build_3d_topic_graph(self, topics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build 3D graph structure from topics with better spacing."""
        nodes = []
        links = []
        
        # Category configurations - LARGER radii for better spacing
        node_config = {
            "main_concepts": {
                "color": "#8B5CF6",  # Purple
                "size": 30,
                "layer": 0,  # Center
                "radius": 0,
                "z_offset": 0,
            },
            "building_blocks": {
                "color": "#3B82F6",  # Blue
                "size": 22,
                "layer": 1,  # Inner ring
                "radius": 150,
                "z_offset": -60,
            },
            "techniques": {
                "color": "#10B981",  # Green
                "size": 18,
                "layer": 2,  # Middle ring
                "radius": 280,
                "z_offset": 0,
            },
            "applications": {
                "color": "#F59E0B",  # Orange
                "size": 16,
                "layer": 3,  # Outer ring
                "radius": 400,
                "z_offset": 60,
            },
        }
        
        # Create nodes for each category
        node_id_map = {}  # Map labels to IDs
        
        for category, config in node_config.items():
            items = topics_data.get(category, [])
            
            for idx, label in enumerate(items):
                # Calculate position in 3D space (layered circular layout)
                # Add offset to avoid overlap at same angles
                angle_offset = (config["layer"] * 0.3)  # Rotate each layer slightly
                angle = 2 * np.pi * idx / max(len(items), 1) + angle_offset
                radius = config["radius"]
                
                # Add some randomness for organic feel
                jitter_x = np.random.normal(0, 15)
                jitter_y = np.random.normal(0, 15)
                
                x = radius * np.cos(angle) + jitter_x
                y = radius * np.sin(angle) + jitter_y
                z = config["z_offset"] + np.random.normal(0, 20)  # More Z variation
                
                node_id = f"{category}_{idx}"
                node_id_map[label] = node_id
                
                nodes.append({
                    "id": node_id,
                    "label": label,
                    "category": category.replace("_", " ").title(),
                    "x": float(x),
                    "y": float(y),
                    "z": float(z),
                    "size": config["size"],
                    "color": config["color"],
                    "layer": config["layer"],
                })
        
        # Create links from relationships
        relationships = topics_data.get("relationships", [])
        
        for rel in relationships:
            source_id = node_id_map.get(rel["from"])
            target_id = node_id_map.get(rel["to"])
            
            if source_id and target_id:
                links.append({
                    "source": source_id,
                    "target": target_id,
                    "type": rel.get("type", "related"),
                    "strength": 1.0,
                })
        
        # Add automatic links between same-layer nodes (weaker connections)
        for category, items in topics_data.items():
            if category == "relationships":
                continue
            
            for i, item1 in enumerate(items):
                for j, item2 in enumerate(items):
                    if i < j:  # Avoid duplicates
                        source_id = node_id_map.get(item1)
                        target_id = node_id_map.get(item2)
                        
                        if source_id and target_id:
                            links.append({
                                "source": source_id,
                                "target": target_id,
                                "type": "related",
                                "strength": 0.3,  # Weaker connection
                            })
        
        return {
            "nodes": nodes,
            "links": links,
            "layers": [
                {"name": "Core Concepts", "radius": 0, "color": "#8B5CF6"},
                {"name": "Building Blocks", "radius": 150, "color": "#3B82F6"},
                {"name": "Techniques", "radius": 280, "color": "#10B981"},
                {"name": "Applications", "radius": 400, "color": "#F59E0B"},
            ],
            "stats": {
                "total_nodes": len(nodes),
                "total_links": len(links),
                "main_concepts": len(topics_data.get("main_concepts", [])),
                "techniques": len(topics_data.get("techniques", [])),
                "applications": len(topics_data.get("applications", [])),
            },
        }
    
    async def get_learning_path_3d(
        self,
        paper_id: str,
        title: str,
        abstract: str,
    ) -> Dict[str, Any]:
        """
        Generate a 3D learning path visualization showing prerequisites and concepts.
        Visualizes "what you'll learn by reading this paper".
        """
        cache_key = f"learning_path_3d:{paper_id}"
        cached = intelligent_cache.get(cache_key, DataType.VISUALIZATIONS.value)
        if cached:
            return cached
        
        # Get prerequisites and key concepts
        learning_data = await self._extract_learning_path(title, abstract)
        
        # Build tree-like 3D structure
        graph = self._build_learning_path_graph(learning_data)
        
        intelligent_cache.set(cache_key, graph, data_type=DataType.VISUALIZATIONS.value)
        return graph
    
    async def _extract_learning_path(
        self,
        title: str,
        abstract: str,
    ) -> Dict[str, Any]:
        """Extract prerequisites and learning outcomes."""
        # Use summary generator's prerequisite method
        from app.services.summary_generator import adaptive_summary_generator
        
        prerequisites = await adaptive_summary_generator.identify_prerequisites(title, abstract)
        
        # For learning outcomes, use simplified extraction
        outcomes = [
            "Understanding of core methodology",
            "Practical implementation knowledge",
            "Research context and motivation",
            "Experimental validation approaches",
        ]
        
        return {
            "prerequisites": prerequisites or ["Basic ML knowledge", "Mathematics"],
            "core_concepts": ["Main contribution", "Novel approach"],
            "learning_outcomes": outcomes,
            "applications": ["Real-world use case"],
        }
    
    def _build_learning_path_graph(self, learning_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build tree structure for learning path."""
        nodes = []
        links = []
        
        # Root node (the paper itself)
        nodes.append({
            "id": "paper",
            "label": "This Paper",
            "x": 0,
            "y": 0,
            "z": 0,
            "size": 30,
            "color": "#8B5CF6",
            "category": "Main Topic",
        })
        
        # Prerequisites (below)
        prereqs = learning_data.get("prerequisites", [])
        for i, prereq in enumerate(prereqs[:5]):
            angle = 2 * np.pi * i / len(prereqs)
            nodes.append({
                "id": f"prereq_{i}",
                "label": prereq,
                "x": 100 * np.cos(angle),
                "y": 100 * np.sin(angle),
                "z": -60,
                "size": 15,
                "color": "#EF4444",  # Red - must learn first
                "category": "Prerequisites",
            })
            links.append({
                "source": f"prereq_{i}",
                "target": "paper",
                "type": "prerequisite",
            })
        
        # Learning outcomes (above)
        outcomes = learning_data.get("learning_outcomes", [])
        for i, outcome in enumerate(outcomes[:4]):
            angle = 2 * np.pi * i / len(outcomes)
            nodes.append({
                "id": f"outcome_{i}",
                "label": outcome,
                "x": 120 * np.cos(angle + np.pi/4),
                "y": 120 * np.sin(angle + np.pi/4),
                "z": 60,
                "size": 18,
                "color": "#10B981",  # Green - will learn
                "category": "Learning Outcomes",
            })
            links.append({
                "source": "paper",
                "target": f"outcome_{i}",
                "type": "outcome",
            })
        
        return {
            "nodes": nodes,
            "links": links,
            "stats": {
                "prerequisites": len(prereqs),
                "outcomes": len(outcomes),
            },
        }


# Singleton
paper_topic_analysis_3d_service = PaperTopicAnalysis3DService()
