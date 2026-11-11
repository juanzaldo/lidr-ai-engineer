from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class Phase(BaseModel):
    """Desglose de una fase; los costes del proyecto se expresan en EUR."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=64)
    duration_weeks: int = Field(ge=1, le=52)
    cost_eur: int = Field(ge=0, le=1_000_000)
    summary: str = Field(min_length=10, max_length=600)


class EstimationResult(BaseModel):
    """Resultado conversacional validado, independiente del formato visual.

    Las fases pueden solaparse: la duración total no tiene que ser su suma.
    Los costes sí deben sumar exactamente. La baja confianza se declara
    explícitamente, siguiendo el contrato de la referencia del maestro.
    """

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    summary: str = Field(min_length=10, max_length=1200)
    confidence_pct: int = Field(
        ge=0, le=100,
        description="Si es menor de 30, summary debe comenzar con 'Out of scope:'.",
    )
    phases: list[Phase] = Field(min_length=1, max_length=8)
    total_duration_weeks: int = Field(ge=1, le=104)
    total_cost_eur: int = Field(
        ge=0, le=2_000_000,
        description="Suma exacta de cost_eur de todas las fases.",
    )

    @model_validator(mode="after")
    def validate_business_rules(self) -> "EstimationResult":
        if sum(phase.cost_eur for phase in self.phases) != self.total_cost_eur:
            raise ValueError("El coste total debe coincidir con la suma de las fases")
        if self.confidence_pct < 30 and not self.summary.startswith("Out of scope:"):
            raise ValueError("Confianza menor de 30 requiere el prefijo 'Out of scope:'")
        return self


class StructuredEstimationResponse(BaseModel):
    """Contrato nuevo; los endpoints anteriores conservan su respuesta textual."""

    result: EstimationResult
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
