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

### Prerequisites

- **Python 3.11+** (required)
- **uv** (recommended) or pip
- **Docker & Docker Compose** (for PostgreSQL/Redis) OR local installations
- **Git**

### Step 1: Clone and Navigate

```powershell
# Clone the repository
git clone https://github.com/your-org/paper-radar.git
cd paper-radar/backend
```

### Step 2: Environment Variables

Create a `.env` file in the `backend/` directory:

```ini
# === Required ===
SECRET_KEY=your-super-secret-key-at-least-32-chars

# === API Keys (Get these first) ===
GROQ_API_KEY=gsk_...                    # Required for AI summaries (https://console.groq.com)
GITHUB_TOKEN=ghp_...                    # Optional but recommended (https://github.com/settings/tokens)
SEMANTIC_SCHOLAR_API_KEY=               # Optional (https://www.semanticscholar.org/product/api)

# === Local Development Mode (Recommended for first setup) ===
USE_LOCAL_STORAGE=true                  # Uses SQLite + file cache (no Docker needed)
LOCAL_DATA_DIR=./data

# === Production Mode (requires Docker) ===
# USE_LOCAL_STORAGE=false
# DATABASE_URL=postgresql://radar:radar@localhost:5432/paperradar
# REDIS_URL=redis://localhost:6379/0

# === Optional Tuning ===
ENVIRONMENT=development
DEBUG=true
ARXIV_REQUESTS_PER_SECOND=2.0
SEMANTIC_SCHOLAR_REQUESTS_PER_5MIN=80
GROQ_REQUESTS_PER_MINUTE=30
```

### Step 3: Install Dependencies

```powershell
# Using uv (recommended - faster)
uv sync

# OR using pip
pip install -e ".[dev]"
```

### Step 4: Start Infrastructure (Production Mode Only)

Skip this if using `USE_LOCAL_STORAGE=true`.

```powershell
# Start PostgreSQL and Redis
docker-compose up -d db redis

# Verify containers are running
docker-compose ps
```

### Step 5: Initialize Database

```powershell
# The app auto-creates tables on first run
# Just start the server once:
uv run uvicorn app.main:app --reload

# Or run the quickstart script:
uv run python -m scripts.quickstart
```

### Step 6: Populate Data

```powershell
# Option A: Run full pipeline (recommended)
uv run python -m scripts.run_pipeline

# Option B: Run steps individually
# 1. Fetch papers from arXiv
uv run python -m scripts.ingest_arxiv_daily

# 2. Enrich with citation data
uv run python -m scripts.enrich_semantic_scholar

# 3. Find GitHub implementations
uv run python -m scripts.discover_implementations

# 4. Generate AI summaries (requires GROQ_API_KEY)
uv run python -m scripts.generate_summaries

# 5. Calculate ranking scores
uv run python -m scripts.calculate_ranking_scores
```

---

## Running the Server

### Development Mode

```powershell
# With auto-reload
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using the shorthand
uv run python -m uvicorn app.main:app --reload
```

### Production Mode

```powershell
# With multiple workers
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Verify Server is Running

```powershell
# Health check
curl http://localhost:8000/health

# API docs (interactive)
# Open in browser: http://localhost:8000/docs

# Get trending papers
curl http://localhost:8000/api/papers/trending
```

---

## Testing

### Run All Tests

```powershell
# Run test suite
uv run pytest

# With coverage report
uv run pytest --cov=app --cov-report=html

# Verbose output
uv run pytest -v
```

### Run Specific Tests

```powershell
# Test a specific file
uv run pytest tests/test_papers.py

# Test a specific function
uv run pytest tests/test_papers.py::test_get_trending

# Run only fast tests (skip slow integration tests)
uv run pytest -m "not slow"
```

### Quick Service Tests

```powershell
# Test external service connections
uv run python -m scripts.test_services

# Test the ranking algorithm
uv run python -m scripts.quick_test
```

---

## API Quick Reference

Once running, the API is available at `http://localhost:8000`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/docs` | GET | Interactive API documentation |
| `/api/papers` | GET | List papers (paginated) |
| `/api/papers/trending` | GET | Get trending papers |
| `/api/papers/{id}` | GET | Get paper details |
| `/api/papers/search` | POST | Search papers |
| `/api/papers/categories` | GET | List categories |
| `/api/recommendations` | GET | Get personalized recommendations |

### Example API Calls

```powershell
# Get trending papers (last week)
curl "http://localhost:8000/api/papers/trending?timeframe=week&limit=10"

# Search papers
curl -X POST "http://localhost:8000/api/papers/search" `
  -H "Content-Type: application/json" `
  -d '{"query": "transformer attention mechanism"}'

# Get paper by ID
curl "http://localhost:8000/api/papers/{paper-uuid}"

# Filter by category
curl "http://localhost:8000/api/papers?category=cs.LG&page=1&page_size=20"
```

---

## Troubleshooting

### Common Issues

**"Database connection failed"**
```powershell
# If using local storage, ensure USE_LOCAL_STORAGE=true in .env
# If using Docker, check containers:
docker-compose ps
docker-compose logs db
```

**"GROQ_API_KEY not set"**
```powershell
# Get a free API key from https://console.groq.com
# Add to .env: GROQ_API_KEY=gsk_your_key_here
```

**"Rate limit exceeded"**
```powershell
# Reduce request rates in .env:
ARXIV_REQUESTS_PER_SECOND=1.0
SEMANTIC_SCHOLAR_REQUESTS_PER_5MIN=50
```

**"Module not found"**
```powershell
# Ensure you're in the backend directory
cd backend

# Reinstall dependencies
uv sync --reinstall
```

### Reset Everything

```powershell
# Delete local data and start fresh
Remove-Item -Recurse -Force ./data
uv run python -m scripts.quickstart
```

---

## Development Workflow

### Code Quality

```powershell
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type checking
uv run mypy app/

# Run all checks
uv run pre-commit run --all-files
```

### Adding New Dependencies

```powershell
# Add a dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Update lock file
uv lock
```

### Database Migrations (Production)

```powershell
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1
```
