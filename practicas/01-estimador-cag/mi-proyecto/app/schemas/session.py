from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.estimation import (
    DetailLevel, OutputFormat, ProjectType, StructuredEstimationResponse,
)
from app.sessions import ProjectMetadata


class SessionRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=80_000)
    project_type: ProjectType = ProjectType.WEB_SAAS
    detail_level: DetailLevel = DetailLevel.MEDIUM
    output_format: OutputFormat = OutputFormat.PHASES_TABLE

    @field_validator("transcript")
    @classmethod
    def useful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("La transcripción no puede estar vacía")
        return value


class CreateSessionResponse(BaseModel):
    session_id: UUID


class SessionInfoResponse(CreateSessionResponse):
    project_metadata: ProjectMetadata
    history_turns: int
    max_turns: int


class SessionEstimationResponse(StructuredEstimationResponse, SessionInfoResponse):
    pass
