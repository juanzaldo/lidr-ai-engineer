from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ProjectType(str, Enum):
    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"


class EstimationRequest(BaseModel):
    description: str = Field(min_length=20, max_length=2000)
    project_type: ProjectType
    detail_level: DetailLevel
    output_format: OutputFormat

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        if len(value.strip()) < 20:
            raise ValueError("Describe el proyecto con al menos 20 caracteres útiles.")
        return value


class EstimationResponse(BaseModel):
    text: str
    prompt_version: str


class LegacyEstimationRequest(BaseModel):
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


class LegacyEstimationResponse(BaseModel):
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
