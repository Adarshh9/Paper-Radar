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
from app.core.database import engine, Base
from app.core.logging import setup_logging
from app.api import papers, users, interactions, recommendations

# Initialize logging
setup_logging()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info("Starting Paper Radar API", version="1.0.0", environment=settings.environment)
    
    # Create database tables (for development)
    # In production, use Alembic migrations
    if settings.environment == "development":
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    
    yield
    
    # Shutdown
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

# Middleware: GZip compression for responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Middleware: CORS
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
    
    # Add request ID to logger context
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


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Check if the API is running."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
        "environment": settings.environment,
    }


# Readiness check for Kubernetes/Docker
@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Check if the API is ready to accept traffic."""
    # TODO: Add database and redis connectivity checks
    return {"status": "ready"}


# Include API routers
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
