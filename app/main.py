import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.api_v1 import api_v1_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.rate_limit import RateLimitMiddleware, get_rate_limiter
from app.schemas.error import ErrorDetail, ErrorEnvelope
from app.services.model_service import get_model_service

logger = logging.getLogger("retailiq.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing startup and shutdown routines."""
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Configured CORS origins: {settings.CORS_ORIGINS}")

    # Inspect model weights presence non-intrusively (no inference or heavy loading)
    model_service = get_model_service()
    info = model_service.get_model_info()
    logger.info(
        f"YOLO11n weights path: {info['model_path']} "
        f"(exists={info['weights_exist']}, size={info['weights_size_bytes']} bytes)"
    )
    if not info["ml_dependencies_installed"]:
        logger.warning(
            "Computer vision ML dependencies ('ultralytics', 'torch') not installed. "
            "Backend foundation is operating in API/management mode."
        )

    # ------------------------------------------------------------------
    # Persistent RAG Knowledge Base Startup Reload
    # ------------------------------------------------------------------
    # Connect to PostgreSQL, load persisted document metadata, chunk text, and precomputed
    # 384-D embeddings into in-memory BM25 index without re-generating embeddings.
    try:
        from pathlib import Path
        from app.db.session import get_session_factory
        from app.services.rag.rag_service import get_rag_service

        rag_service = get_rag_service()
        session_factory = get_session_factory()
        async with session_factory() as session:
            import asyncio
            count = await asyncio.wait_for(rag_service.load_persisted_corpus(session), timeout=1.5)
            if count > 0:
                logger.info(
                    f"RAG Knowledge Base startup reload: {count} chunk(s) reloaded "
                    f"from database without re-embedding."
                )
            else:
                # First boot: database is empty, seed from default documents if present
                docs_dir = Path("data/documents")
                if docs_dir.exists():
                    logger.info("RAG database is empty on first startup; ingesting default documents...")
                    for doc_file in docs_dir.glob("*"):
                        if doc_file.suffix.lower() in {".txt", ".pdf", ".md"}:
                            await rag_service.aingest_document(doc_file, session=session)
                    logger.info(
                        f"Initial document persistence complete: {rag_service.get_corpus_size()} chunk(s) "
                        f"persisted to database."
                    )
    except Exception as err:
        logger.warning(f"RAG database startup reload was bypassed or unconfigured: {err}")

    yield

    limiter = get_rate_limiter()
    await limiter.close()
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


def create_application() -> FastAPI:
    """Factory creating and configuring the RetailIQ FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "RetailIQ Computer Vision & Retail Analytics Backend Service. "
            "Provides video analytics, store metrics, shelf status, and AI assistant APIs."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS for Next.js frontend communication
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized Redis Rate Limiting
    application.add_middleware(RateLimitMiddleware)

    # Register root health check strictly matching API_CONTRACT.md section 1
    application.include_router(health_router, prefix="", tags=["Health"])

    # Register API v1 prefixed router for future domain endpoints
    application.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # -------------------------------------------------------------
    # Standard Error Handlers (Conforming to API_CONTRACT.md)
    # -------------------------------------------------------------
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        error_code = "HTTP_ERROR"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            error_code = "RESOURCE_NOT_FOUND"
        elif exc.status_code == status.HTTP_400_BAD_REQUEST:
            error_code = "BAD_REQUEST"
        elif exc.status_code == status.HTTP_408_REQUEST_TIMEOUT:
            error_code = "REQUEST_TIMEOUT"

        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code=error_code,
                message=str(exc.detail),
                details={"status_code": exc.status_code},
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope.model_dump(),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request payload or parameters validation failed.",
                details={"errors": exc.errors()},
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=envelope.model_dump(),
        )

    @application.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(f"Unhandled server exception on {request.url.path}: {exc}")
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected server error occurred.",
                details={"type": exc.__class__.__name__},
            )
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=envelope.model_dump(),
        )

    return application


app = create_application()
