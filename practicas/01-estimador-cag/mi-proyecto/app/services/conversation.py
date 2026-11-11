from app.prompts.loader import render_conversational_prompt
from app.schemas.estimation import EstimationResult
from app.schemas.session import SessionEstimationResponse, SessionRequest
from app.services.llm_service import generate_structured_estimation
from app.services.metadata import update_metadata
from app.sessions import Session


PROMPT_VERSION = "v2"


async def estimate_in_session(session: Session, request: SessionRequest) -> SessionEstimationResponse:
    # Dos peticiones simultáneas de la misma sesión se procesan en orden.
    async with session.lock:
        system, user = render_conversational_prompt(request, session.metadata, PROMPT_VERSION)
        messages = session.history.to_messages_list(system_prompt=system, current_user=user)
        generated = await generate_structured_estimation(messages)
        result = EstimationResult.model_validate(generated["result"])
        metadata = update_metadata(session.metadata, request.transcript, result)
        response = SessionEstimationResponse(
            session_id=session.session_id, result=result, prompt_version=PROMPT_VERSION,
            project_metadata=metadata,
            history_turns=min(session.history.turn_count + 1, session.history.max_turns),
            max_turns=session.history.max_turns,
        )
        # Confirmar solo después de validar todo; un fallo no deja medio turno.
        session.history.append(user=user, assistant=result.model_dump_json())
        session.metadata = metadata
        return response
