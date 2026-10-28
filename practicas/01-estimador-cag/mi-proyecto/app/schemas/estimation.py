from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class EstimationRequest(BaseModel):
    transcription: str = Field(
        min_length=1,
        description="Transcripción de la reunión que se desea estimar.",
    )

    @field_validator("transcription")
    @classmethod
    def validate_transcription(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("La transcripción no puede estar vacía.")
        return value


class EstimationResponse(BaseModel):
    estimation: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None = Field(
        description="Coste aproximado de la llamada al LLM en USD."
    )
    timestamp: datetime = Field(
        description="Fecha y hora UTC de generación de la respuesta."
    )
    latency_ms: int = Field(
        description="Tiempo transcurrido de la llamada en milisegundos."
    )


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail
