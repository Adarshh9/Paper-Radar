# Paper Radar Backend Intelligence

The brain of the platform. This service handles data ingestion, AI enrichment, ranking algorithms, and API delivery.

## System Architecture

```mermaid
graph TD
    subgraph "External Providers"
    ArXiv[arXiv API]
    S2[Semantic Scholar]
    GitHub[GitHub API]
    Groq[Groq LLM]
    end

    subgraph "Data Pipeline (Scripts)"
    Ingest[1. ingest_arxiv_daily]
    Enrich[2. enrich_semantic_scholar]
    Code[3. discover_implementations]
    Summary[4. generate_summaries]
    Rank[5. calculate_ranking_scores]
    end

    subgraph "Core Infrastructure"
    DB[(PostgreSQL)]
    Cache[(Redis)]
    API[FastAPI]
    end

    ArXiv --> Ingest --> DB
    S2 --> Enrich --> DB
    GitHub --> Code --> DB
    Groq --> Summary --> DB
    DB --> Rank --> Cache
    Cache --> API
    DB --> API
```

## How It Works (The Lifecycle)

The backend operates on a continuous enrichment cycle:

### 1. Ingestion (`scripts/ingest_arxiv_daily.py`)
- Fetches papers from arXiv categories: `cs.AI`, `cs.LG`, `cs.CV`, `cs.CL`.
- **Deduplication**: Checks database to avoid re-inserting existing papers.
- **Data**: Stores title, abstract, authors, and raw PDF link.

### 2. Enrichment (`scripts/enrich_...`)
- **Semantic Scholar**: We query S2 to get citation counts and "Influence" metrics.
- **GitHub**: We search GitHub for repositories matching the paper's title or arxiv ID to find official code implementations.

### 3. AI Insights (`scripts/generate_summaries.py`)
- **Engine**: Uses `Llama-3.3-70b` via Groq.
- **Prompting**: Structured prompting extracts JSON output containing:
    - **ELI5**: "Explain Like I'm 5"
    - **Methodology**: Technical approach.
    - **Use Cases**: Real-world application.
- **Performance**: Summaries are generated in background batches to process 500+ papers efficiently.

### 4. Smart Ranking V2 (`scripts/calculate_ranking_scores.py`)
We don't just list papers chronologically. We calculate a **Radar Score** (0.0 - 1.0) for every paper.

#### The Formula:
```python
Base_Score = (
    (Recency * 0.15) +          # Is it new?
    (Velocity * 0.25) +         # Are citations growing fast?
    (Implementation * 0.30) +   # Does it have code? (Heavy weight)
    (Social * 0.10) +           # Is it buzzing?
    (Impact * 0.15)             # Total citations (Log scale)
)

Final_Score = Base_Score * Freshness_Boost
```

- **Freshness Boost**: A **3.0x multiplier** is applied to papers < 7 days old to ensure the "Trending" tab is always fresh.
- **Code Bonus**: Providing code gives a paper a roughly 30% advantage in ranking.

## Internal Modules

### `app/services/`
- **`llm_service.py`**: Handles rate limiting (Groq tier limits) and structured JSON parsing.
- **`arxiv_service.py`**: XML parsing of arXiv responses.

### `app/core/cache.py`
- Implements a generic Redis caching wrapper.
- Strategy: **Cache-Aside**.
- **TTL**:
    - Paper Details: 1 hour.
    - Trending List: 15 minutes (to reflect velocity changes).
    - Summaries: Permanent (cached in DB), or 7 days in Redis.

## Setup & Init

### Environment Variables
Create `.env`:
```ini
DATABASE_URL=postgresql://user:pass@localhost:5432/radar
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=gsk_...        # Required for summaries
GITHUB_TOKEN=ghp_...        # Optional (avoids rate limits)
SECRET_KEY=...              # Generic string
```

### Running Locally
```bash
# 1. Install Dependencies
uv sync

# 2. Database
# Ensure Postgres/Redis are running (via Docker usually)
docker-compose up -d db redis

# 3. Migrations (First Run)
# The app creates tables automatically on startup via SQLAlchemy `create_all`.
# Just run the app once:
uv run uvicorn app.main:app

# 4. Populate Data
uv run python -m scripts.ingest_arxiv_daily
uv run python -m scripts.calculate_ranking_scores
```
