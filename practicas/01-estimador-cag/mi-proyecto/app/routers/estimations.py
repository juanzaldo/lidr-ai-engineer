from fastapi import APIRouter, HTTPException

from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import (
    EstimationRequest, EstimationResponse, ErrorResponse,
    LegacyEstimationRequest, LegacyEstimationResponse,
)
from app.services.errors import LLMServiceError
from app.services.llm_service import generate_estimation


router = APIRouter(tags=["Estimaciones"])
PROMPT_VERSION = "v1"
ERROR_STATUS = {
    "invalid_input": 422,
    "provider_timeout": 504,
    "provider_unavailable": 503,
    "provider_rejected": 502,
    "invalid_response": 502,
    "configuration_error": 500,
    "internal_error": 500,
}


@router.post(
    "/estimate",
    response_model=EstimationResponse,
    responses={status: {"model": ErrorResponse} for status in (500, 502, 503, 504)},
)
async def estimate(request: EstimationRequest) -> EstimationResponse:
    system, user = render_estimation_prompt(request, version=PROMPT_VERSION)
    try:
        result = await generate_estimation(user, system_prompt=system)
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=ERROR_STATUS[exc.code],
            detail={"code": exc.code, "message": exc.public_message},
        ) from None
    return EstimationResponse(text=result["estimation"], prompt_version=PROMPT_VERSION)


@router.post(
    "/api/v1/estimate",
    response_model=LegacyEstimationResponse,
    deprecated=True,
    responses={status: {"model": ErrorResponse} for status in (500, 502, 503, 504)},
)
async def estimate_legacy(request: LegacyEstimationRequest) -> LegacyEstimationResponse:
    try:
        result = await generate_estimation(request.transcription)
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=ERROR_STATUS[exc.code],
            detail={"code": exc.code, "message": exc.public_message},
        ) from None
    return LegacyEstimationResponse(**result)
