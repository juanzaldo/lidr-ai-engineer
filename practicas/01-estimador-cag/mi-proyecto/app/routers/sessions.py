from functools import lru_cache

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.routers.estimations import ERROR_STATUS
from app.schemas.estimation import DetailLevel, OutputFormat, ProjectType
from app.schemas.session import (
    CreateSessionResponse, SessionEstimationResponse, SessionInfoResponse, SessionRequest,
)
from app.services.attachments import AttachmentError, enrich_transcript, extract_text
from app.services.conversation import estimate_in_session
from app.services.errors import LLMServiceError
from app.sessions import SessionNotFoundError, SessionStore


router = APIRouter(prefix="/sessions", tags=["Conversaciones"])


@lru_cache
def get_session_store() -> SessionStore:
    """Un store por proceso; se pierde al reiniciar y no se comparte entre workers."""
    return SessionStore(max_turns=settings.MAX_CONVERSATION_TURNS)


def find_session(store: SessionStore, session_id: str):
    try:
        return store.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(404, detail="La conversación no existe o el servicio se reinició.") from None


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(store: SessionStore = Depends(get_session_store)):
    return CreateSessionResponse(session_id=store.create().session_id)


@router.get("/{session_id}", response_model=SessionInfoResponse)
async def session_info(session_id: str, store: SessionStore = Depends(get_session_store)):
    session = find_session(store, session_id)
    return SessionInfoResponse(
        session_id=session.session_id, project_metadata=session.metadata,
        history_turns=session.history.turn_count, max_turns=session.history.max_turns,
    )


@router.post("/{session_id}/estimate", response_model=SessionEstimationResponse)
async def estimate(
    session_id: str,
    transcript: str = Form(..., min_length=1, max_length=80_000),
    project_type: ProjectType = Form(ProjectType.WEB_SAAS),
    detail_level: DetailLevel = Form(DetailLevel.MEDIUM),
    output_format: OutputFormat = Form(OutputFormat.PHASES_TABLE),
    attachments: list[UploadFile] = File(default=[]),
    store: SessionStore = Depends(get_session_store),
):
    session = find_session(store, session_id)
    try:
        request = SessionRequest(
            transcript=transcript, project_type=project_type,
            detail_level=detail_level, output_format=output_format,
        )
    except ValidationError:
        raise HTTPException(422, detail="Revisa la transcripción y las opciones.") from None

    try:
        if len(attachments) > settings.MAX_ATTACHMENTS:
            raise AttachmentError(413, "Demasiados adjuntos en la petición.")
        extracted, total_bytes = [], 0
        for upload in attachments:
            content = await upload.read(settings.MAX_ATTACHMENT_BYTES + 1)
            total_bytes += len(content)
            if len(content) > settings.MAX_ATTACHMENT_BYTES or total_bytes > settings.MAX_TOTAL_ATTACHMENT_BYTES:
                raise AttachmentError(413, "Los adjuntos superan el tamaño permitido.")
            text = await run_in_threadpool(
                extract_text, upload.filename or "", content, settings.MAX_ATTACHMENT_CHARS,
            )
            extracted.append((upload.filename or "adjunto", text))
        enriched = enrich_transcript(transcript, extracted)
        if len(enriched) > min(settings.MAX_CONTEXT_CHARS, 80_000):
            raise AttachmentError(413, "La transcripción y los adjuntos superan el límite de texto.")
        request = request.model_copy(update={"transcript": enriched})
        return await estimate_in_session(session, request)
    except AttachmentError as exc:
        raise HTTPException(exc.status_code, detail=exc.public_message) from None
    except LLMServiceError as exc:
        raise HTTPException(
            ERROR_STATUS[exc.code], detail={"code": exc.code, "message": exc.public_message},
        ) from None
    finally:
        for upload in attachments:
            await upload.close()
