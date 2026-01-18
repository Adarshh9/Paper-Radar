"""
FastAPI application entry point.
"""
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger

from app.core.config import get_settings
from app.core.database import engine, Base, init_db
from app.core.logging import setup_logging
from app.api import papers, users, interactions, recommendations, visualizations

# Initialize logging
setup_logging()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs on startup and shutdown.
    """
    # Initialize database (creates tables if they don't exist)
    # This is especially important for local SQLite development
    init_db()
    logger.info("Database initialized", 
                local_storage=settings.use_local_storage,
                data_dir=str(settings.data_directory) if settings.use_local_storage else "N/A")
    
    # Start background scheduler for automated ingestion
    if settings.environment != "development":  # Only in production
        from app.services.background_scheduler import scheduler
        scheduler.start()
        logger.info("Background scheduler started")
    else:
        logger.info("Background scheduler disabled in development mode")
        logger.info("To enable scheduler, run: uv run python -m app.services.background_scheduler")
    
    yield
    
    # Shutdown
    if settings.environment != "development":
        from app.services.background_scheduler import scheduler
        scheduler.shutdown()
        logger.info("Background scheduler stopped")
    
    logger.info("Shutting down Paper Radar API")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Academic paper discovery platform that aggregates, ranks, and personalizes research papers.",
    version="1.0.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware for request/response logging and correlation IDs.
    """
    request_id = str(uuid4())[:8]
    start_time = time.time()
    
    with logger.contextualize(request_id=request_id):
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )
        
        response: Response = await call_next(request)
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        
        # Add correlation ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


@app.get("/health", tags=["Health"])
async def health_check():
    """Check if the API is running."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
        "environment": settings.environment,
    }


@app.get("/ready", tags=["Health"])
async def readiness_check():
    return {"status": "ready"}


app.include_router(
    papers.router,
    prefix="/api/papers",
    tags=["Papers"],
)

app.include_router(
    users.router,
    prefix="/api",
    tags=["Users"],
)

app.include_router(
    interactions.router,
    prefix="/api/interactions",
    tags=["Interactions"],
)

app.include_router(
    recommendations.router,
    prefix="/api/recommendations",
    tags=["Recommendations"],
)

app.include_router(
    visualizations.router,
    prefix="/api/visualizations",
    tags=["3D Visualizations"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level="warning",  # Suppress uvicorn access logs, we use our middleware
        access_log=False,
    )
