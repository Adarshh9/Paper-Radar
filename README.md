# 📡 Paper Radar

**Academic paper discovery platform** that aggregates, ranks, and provides deep insights for research papers. Built for researchers who want to cut through the noise.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![License](https://img.shields.io/badge/license-MIT-blue)

## 🏗 Architecture

```mermaid
graph TD
    Sources[Sources: arXiv, Semantic Scholar, GitHub] -->|Ingest| Pipeline
    
    subgraph Backend
    Pipeline[Ingestion Pipeline] -->|Store| DB[(PostgreSQL)]
    Pipeline -->|Cache| Redis[(Redis)]
    LLM[Groq LLM] -->|Generate Insights| DB
    Ranking[Ranking Engine] -->|Score| Redis
    API[FastAPI Service] -->|Read| DB & Redis
    end
    
    subgraph Frontend
    Web[Next.js App] -->|REST API| API
    end
```

## ✨ Key Features

- **🔍 Smart Ranking V2**: Papers are ranked by a weighted score of meaningful signals, not just citation counts.
    - **Freshness Boost**: New papers (<7 days) get a 3.0x score multiplier.
    - **Velocity**: We track daily citation rates to find rising stars.
    - **Code Availability**: Papers with implementation code are prioritized.
- **🧠 Deep Dive Insights**: AI-generated structured summaries that explain papers without needing to open the PDF.
    - **ELI5**: "Explain Like I'm 5" simplifications.
    - **Methodology & Use Cases**: Technical deep dives extracted automatically.
- **💻 Implementation Finder**: Automatically links GitHub repositories and HuggingFace models to papers.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ & [uv](https://github.com/astral-sh/uv)
- Node.js 18+
- Docker & Docker Compose

### ⚡ Fast Setup (Docker)

```bash
# 1. Clone & Setup Utils
git clone https://github.com/Adarshh9/paper-radar.git
cd paper-radar

# 2. Configure Environment
cp backend/.env.example backend/.env
# Edit backend/.env: Add GROQ_API_KEY (required) and GITHUB_TOKEN (optional)

# 3. Start Infrastructure (DB + Redis + API)
docker-compose up -d

# 4. Start Frontend
cd frontend
npm install && npm run dev
```

Visit **http://localhost:3000** to browse.

## 🛠 Backend Workflow

The backend is organized into modular services and data pipelines.

### Data Pipelines
Run these scripts to populate your local database:

1.  **Ingestion**: Fetches latest papers from arXiv (CS.AI, CS.LG, etc.).
    ```bash
    uv run python -m scripts.ingest_arxiv_daily
    ```
2.  **Enrichment**: Adds citation counts from Semantic Scholar and code links from GitHub.
    ```bash
    uv run python -m scripts.enrich_semantic_scholar
    uv run python -m scripts.discover_implementations
    ```
3.  **Insight Generation**: Uses Groq (Llama 3) to generate ELI5/Methodology summaries.
    ```bash
    uv run python -m scripts.generate_summaries
    ```
4.  **Ranking**: Calculates scores and caches trending lists in Redis.
    ```bash
    uv run python -m scripts.calculate_ranking_scores
    ```

## ⚙️ Configuration

### Backend variables (`backend/.env`)
| Variable | Descrption |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `GROQ_API_KEY` | **Required** for AI summaries |
| `GITHUB_TOKEN` | Recommended to avoid rate limits |
| `Paper Radar Secret` | JWT signing key |

### Frontend variables (`frontend/.env.local`)
| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api` | Backend API URL |

## 🤝 Contributing
1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License
MIT License. See [LICENSE](LICENSE).
