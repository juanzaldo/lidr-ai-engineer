from fastapi import FastAPI

from app.routers.estimations import router as estimations_router


app = FastAPI(
    title="Estimador de Software CAG",
    description=(
        "API que genera estimaciones de software a partir de "
        "transcripciones de reuniones, utilizando ejemplos estáticos "
        "como contexto y modelos de OpenAI o Anthropic."
    ),
    version="0.1.0",
)

app.include_router(estimations_router)


@app.get("/health", tags=["Estado"])
async def health() -> dict[str, str]:
    return {"status": "ok"}