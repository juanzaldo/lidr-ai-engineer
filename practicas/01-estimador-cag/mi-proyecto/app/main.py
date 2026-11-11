from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.config import settings
from app.logging_config import configure_logging
from app.routers.estimations import router as estimations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.LOG_LEVEL)
    logger = logging.getLogger("estimator")
    logger.info("application_started", extra={"environment": settings.APP_ENV})
    try:
        yield
    finally:
        logger.info("application_stopped")


app = FastAPI(
    title="Estimador de Software CAG",
    description=(
        "API que genera estimaciones de software a partir de "
        "descripciones de proyectos con parámetros tipados, utilizando ejemplos estáticos "
        "como contexto y modelos de OpenAI o Anthropic."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(estimations_router)


@app.get("/health", tags=["Estado"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
