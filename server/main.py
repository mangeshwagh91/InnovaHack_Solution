import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles


from database.schema import init_db
from services.ingestion_queue import ingestion_queue
from dotenv import load_dotenv
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager for startup and shutdown events.
    Handles directory creation, database initialization, and vector store setup.
    """
    # ============ STARTUP ============
    logger.info("=" * 60)
    logger.info("🚀 DataForge AI API Starting Up")
    logger.info("=" * 60)
    
    # Create required directories
    uploads_path = os.getenv("UPLOADS_PATH", "./uploads")
    chroma_path = os.getenv("CHROMA_PATH", "./chroma_db")
    
    for path, name in [(uploads_path, "Uploads"), (chroma_path, "ChromaDB")]:
        try:
            os.makedirs(path, exist_ok=True)
            logger.info(f"✅ {name} directory ready: {os.path.abspath(path)}")
        except OSError as e:
            logger.error(f"❌ Failed to create {name} directory at {path}: {e}")
            raise

    # Initialize database
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.error("The application cannot start without a database.")
        raise RuntimeError(f"Database initialization failed: {e}") from e

    # Initialize vector store in the background (prevents Render port timeout)
    logger.info("Initializing vector store in the background...")
    import threading
    def init_vector_store_bg():
        try:
            from services.vector_store import initialize_collections
            collection_status = initialize_collections()
            if collection_status and all(collection_status.values()):
                logger.info("✅ Vector store collections initialized")
            else:
                failed = [name for name, ok in collection_status.items() if not ok]
                logger.warning(
                    f"⚠️  Vector store initialization partial failure: {', '.join(failed) or 'unknown collections'}"
                )
        except ImportError as e:
            logger.warning(f"⚠️  Vector store module not available: {e}")
            logger.warning("Semantic search features will be disabled.")
        except Exception as e:
            logger.warning(f"⚠️  Vector store initialization failed: {e}")
            logger.warning("Semantic search features may not work correctly.")
            
    threading.Thread(target=init_vector_store_bg, daemon=True).start()

    # Validate environment configuration
    _validate_environment()

    # Start ingestion queue worker
    ingestion_queue.start()

    logger.info("=" * 60)
    logger.info("✅ DataForge AI API ready — all systems nominal")
    logger.info("=" * 60)
    
    yield  # Application runs here
    
    # ============ SHUTDOWN ============
    logger.info("=" * 60)
    logger.info("🛑 DataForge AI API Shutting Down")
    logger.info("=" * 60)
    
    # Cleanup vector store connections
    try:
        from services.vector_store import cleanup_collections
        cleanup_collections()
        logger.info("✅ Vector store connections closed")
    except Exception as e:
        logger.warning(f"⚠️  Error during vector store cleanup: {e}")
    
    # Stop ingestion queue worker
    ingestion_queue.stop()

    logger.info("✅ DataForge AI API shutdown complete")


def _validate_environment() -> None:
    """Validate critical environment variables and log warnings for missing optional ones."""
    
    # Critical checks
    critical_vars = {
        "GROQ_API_KEYS": "No Groq API keys configured. LLM features will fail.",
        "GROQ_MODEL": "No Groq model specified. Using default.",
    }
    
    for var, warning in critical_vars.items():
        if not os.getenv(var):
            logger.warning(f"⚠️  {warning}")
    
    # Optional checks
    optional_vars = {
        "CHROMA_PATH": f"Using default ChromaDB path: {os.getenv('CHROMA_PATH', './chroma_db')}",
        "UPLOADS_PATH": f"Using default uploads path: {os.getenv('UPLOADS_PATH', './uploads')}",
    }
    
    for var, message in optional_vars.items():
        if not os.getenv(var):
            logger.info(f"ℹ️  {message}")
    
    # Log active configuration
    logger.info(f"📋 Active Configuration:")
    logger.info(f"   Groq Model: {os.getenv('GROQ_MODEL', 'Not set')}")
    logger.info(f"   API Keys: {len(os.getenv('GROQ_API_KEYS', '').split(','))} configured")
    logger.info(f"   Max Concurrent: {os.getenv('GROQ_MAX_CONCURRENT', 'Default')}")


# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="DataForge AI — Data Centre Project Intelligence API",
    version="1.0.0",
    description="""
    AI-powered EPC project intelligence for data centre construction.
    
    ## Features
    - **Specification Management**: Upload and parse construction specifications
    - **Compliance Checking**: Automated compliance verification
    - **Schedule Analysis**: Risk analysis for project schedules
    - **RFI Management**: Request for Information tracking
    - **Vendor Submittals**: Submittal document processing
    
    ## LLM Providers
    - Primary: Groq API (multi-key rotation)
    - Fallback: Ollama (local deployment)
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-Request-ID"],
    max_age=3600,
)


# ============================================================================
# Router Registration
# ============================================================================

def _register_router(
    module_name: str,
    prefix: str,
    tags: list[str],
    critical: bool = False
) -> None:
    """
    Safely register a router module.
    
    Args:
        module_name: Import path (e.g., 'routers.upload')
        prefix: URL prefix for the router
        tags: OpenAPI tags
        critical: If True, raise error on failure; if False, warn only
    """
    try:
        module = __import__(module_name, fromlist=["router"])
        router = getattr(module, "router")
        app.include_router(router, prefix=prefix, tags=tags)
        logger.info(f"✅ {tags[0]} router registered at {prefix}")
    except ImportError as e:
        message = f"❌ {tags[0]} router not available: {e}"
        if critical:
            logger.error(message)
            raise
        logger.warning(f"⚠️  {message}")
    except AttributeError as e:
        message = f"❌ {tags[0]} router missing 'router' attribute: {e}"
        if critical:
            logger.error(message)
            raise
        logger.warning(f"⚠️  {message}")
    except Exception as e:
        message = f"❌ Failed to register {tags[0]} router: {e}"
        if critical:
            logger.error(message)
            raise
        logger.warning(f"⚠️  {message}")


# Register all routers - Upload is critical, others are optional
logger.info("Registering API routers...")

_register_router("routers.upload", "/api/upload", ["Upload"], critical=True)
_register_router("routers.auth", "/api/auth", ["Auth"])
_register_router("routers.projects", "/api/projects", ["Projects"])
_register_router("routers.tenders", "/api/tenders", ["Tenders"])
_register_router("routers.compliance", "/api/compliance", ["Compliance"])
_register_router("routers.schedule", "/api/schedule", ["Schedule"])
_register_router("routers.rfi", "/api/rfi", ["RFI"])
_register_router("routers.dashboard", "/api/dashboard", ["Dashboard"])
_register_router("routers.commissioning", "/api/commissioning", ["Commissioning"])
_register_router("routers.supply_chain", "/api/supply-chain", ["Supply Chain"])
_register_router("routers.webhooks", "/api/webhooks", ["Webhooks"])
_register_router("routers.design", "/api/design", ["Design"])
_register_router("routers.integrations", "/api/integrations", ["Integrations"])
_register_router("routers.reports", "/api/reports", ["Reports"])


# ============================================================================
# Static Files
# ============================================================================

uploads_path = os.getenv("UPLOADS_PATH", "./uploads")
try:
    os.makedirs(uploads_path, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")
    logger.info(f"✅ Static files mounted at /uploads from {os.path.abspath(uploads_path)}")
except Exception as e:
    logger.error(f"❌ Failed to mount static files at {uploads_path}: {e}")


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 404 errors with helpful information."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Resource not found",
            "path": str(request.url),
            "method": request.method,
            "tip": "Check /api/status for available endpoints"
        }
    )


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 405 errors."""
    return JSONResponse(
        status_code=405,
        content={
            "error": "Method not allowed",
            "path": str(request.url),
            "method": request.method
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 500 errors with full logging."""
    logger.critical(
        f"Internal server error on {request.method} {request.url}: {str(exc)}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if os.getenv("DEBUG", "").lower() == "true" else "An unexpected error occurred",
            "path": str(request.url),
            "method": request.method,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url}: {str(exc)}",
        exc_info=True
    )
    
    # Determine appropriate status code
    status_code = 500
    if hasattr(exc, "status_code"):
        status_code = exc.status_code
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": type(exc).__name__,
            "message": str(exc),
            "path": str(request.url),
            "method": request.method,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )


# ============================================================================
# Request Middleware
# ============================================================================

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time and request ID to all responses."""
    import time
    import uuid
    
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    
    # Add request ID to request state for logging
    request.state.request_id = request_id
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    response.headers["X-Request-ID"] = request_id
    
    # Log request details
    logger.info(
        f"📨 {request.method} {request.url.path} "
        f"→ {response.status_code} "
        f"({process_time:.3f}s) "
        f"[{request_id}]"
    )
    
    return response


# ============================================================================
# Health Check & Status Endpoints
# ============================================================================

@app.get("/api/", tags=["Health"])
async def root() -> dict:
    """Root endpoint - basic health check."""
    return {
        "status": "running",
        "service": "DataForge AI API",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
        "status": "/api/status"
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Detailed health check endpoint."""
    health_status = {
        "status": "healthy",
        "version": app.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": "N/A"  # Could track with a startup timestamp
    }
    
    # Check database connectivity
    try:
        from database.connection import get_db
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check vector store
    try:
        from services.vector_store import check_health
        health_status["vector_store"] = check_health()
    except Exception as e:
        health_status["vector_store"] = f"error: {str(e)}"
    
    # Check Groq API
    groq_keys = os.getenv("GROQ_API_KEYS", "")
    health_status["groq_api"] = {
        "keys_configured": len(groq_keys.split(",")) if groq_keys else 0,
        "model": os.getenv("GROQ_MODEL", "Not set")
    }
    
    return health_status


@app.get("/api/status", tags=["Health"])
async def api_status() -> dict:
    """List all registered API routes."""
    routes = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            # Filter out internal/static routes from the list
            if not route.path.startswith("/uploads"):
                routes.append({
                    "path": route.path,
                    "name": route.name,
                    "methods": list(route.methods),
                    "tags": getattr(route, "tags", [])
                })
    
    return {
        "status": "running",
        "version": app.version,
        "routes": sorted(routes, key=lambda x: x["path"]),
        "total_endpoints": len(routes)
    }

# ============================================================================
# React SPA Serving
# ============================================================================

client_dist = Path(__file__).resolve().parent.parent / "client" / "dist"
if client_dist.exists():
    logger.info(f"✅ Found compiled frontend at {client_dist}")
    
    # Serve assets directory directly
    assets_dir = client_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Catch-all for React Router SPA
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Ignore API paths, let them hit the 404 handler
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"error": "Not found"})
        
        # Check if the requested file exists in dist (like favicon.ico, vite.svg)
        if full_path:
            file_path = client_dist / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
                
        # Otherwise serve index.html
        return FileResponse(str(client_dist / "index.html"))
else:
    logger.warning("⚠️ Compiled frontend not found. Run 'npm run build' in the client directory.")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "").lower() == "true"
    
    logger.info(f"Starting Uvicorn server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=not os.getenv("DISABLE_RELOAD", "").lower() == "true",
        log_level="debug" if debug else "info",
        access_log=True,
        timeout_keep_alive=30,
    )