from datetime import datetime, timezone
import json
import logging
from time import perf_counter

import anthropic
import openai
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import settings
from app.context.examples import ESTIMATION_EXAMPLES
from app.prompts.loader import environment
from app.schemas.estimation import EstimationResult
from app.services.errors import LLMServiceError


log = logging.getLogger("estimator.llm")


def _anthropic_headers() -> dict[str, str]:
    """Selecciona workspace cuando la clave no está vinculada a uno."""
    workspace_id = (settings.ANTHROPIC_WORKSPACE_ID or "").strip()
    return {"anthropic-workspace-id": workspace_id} if workspace_id else {}


def build_system_prompt() -> str:
    """Prompt compatible con los clientes y el streaming de la sesión 3."""
    return environment.get_template("legacy/system.j2").render(
        examples=ESTIMATION_EXAMPLES
    ).strip()


async def generate_estimation(
    transcription: str, *, system_prompt: str | None = None
) -> dict:
    """Mantiene el contrato textual de las sesiones anteriores."""
    transcription = transcription.strip()
    if not transcription:
        raise LLMServiceError("invalid_input")
    return await _generate_estimation(transcription, system_prompt=system_prompt)


async def generate_structured_estimation(messages: list[dict[str, str]]) -> dict:
    """Genera un EstimationResult validado con historial, sin modificar la sesión.

    Una sola llamada, sin reintentos automáticos. El llamador confirmará el
    turno en memoria únicamente después de recibir un resultado válido.
    """
    if not isinstance(messages, list) or len(messages) < 2 or len(messages) % 2:
        raise LLMServiceError("invalid_input")
    copied = []
    for index, message in enumerate(messages):
        role = "system" if index == 0 else ("user" if index % 2 else "assistant")
        if (
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or message["role"] != role
            or not isinstance(message["content"], str)
            or not message["content"].strip()
        ):
            raise LLMServiceError("invalid_input")
        copied.append(dict(message))
    return await _generate_estimation(
        copied[-1]["content"], system_prompt=copied[0]["content"], messages=copied,
    )


async def _generate_estimation(
    transcription: str, *, system_prompt: str | None,
    messages: list[dict[str, str]] | None = None,
) -> dict:
    """Orquestación común: proveedores, validación, métricas y errores seguros."""

    started_at = perf_counter()
    context = {"provider": settings.LLM_PROVIDER, "model": settings.LLM_MODEL}
    log.info("estimation_started", extra=context)
    try:
        try:
            if system_prompt is None:
                system_prompt = build_system_prompt()
            options = {"messages": messages, "structured": True} if messages is not None else {}
            if settings.LLM_PROVIDER == "openai":
                result = await _call_openai(system_prompt, transcription, **options)
            elif settings.LLM_PROVIDER == "anthropic":
                result = await _call_anthropic(system_prompt, transcription, **options)
            else:
                raise LLMServiceError("configuration_error")
            if messages is not None:
                result["result"] = EstimationResult.model_validate_json(result.pop("estimation"))
        except ValidationError as exc:
            raise LLMServiceError("invalid_response") from exc
        except (openai.APITimeoutError, anthropic.APITimeoutError) as exc:
            raise LLMServiceError("provider_timeout") from exc
        except (openai.APIConnectionError, anthropic.APIConnectionError,
                openai.RateLimitError, anthropic.RateLimitError) as exc:
            raise LLMServiceError("provider_unavailable") from exc
        except (openai.APIStatusError, anthropic.APIStatusError) as exc:
            code = "provider_unavailable" if exc.status_code >= 500 else "provider_rejected"
            raise LLMServiceError(code) from exc
        except LLMServiceError:
            raise
        except (openai.APIError, anthropic.APIError) as exc:
            raise LLMServiceError("provider_rejected") from exc
        except Exception as exc:
            raise LLMServiceError("internal_error") from exc
    except LLMServiceError as exc:
        log.error("estimation_failed", extra={
            **context,
            "error_code": exc.code,
            "error_type": type(exc.__cause__ or exc).__name__,
            "latency_ms": round((perf_counter() - started_at) * 1000),
        })
        raise

    result["timestamp"] = datetime.now(timezone.utc)
    result["latency_ms"] = round((perf_counter() - started_at) * 1000)
    log.info("estimation_completed", extra={
        **context,
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "latency_ms": result["latency_ms"],
    })
    return result


async def _call_openai(
    system_prompt: str, transcription: str, *,
    messages: list[dict[str, str]] | None = None, structured: bool = False,
) -> dict:
    estimated_cost_usd = None
    input_cost_usd = None
    output_cost_usd = None
    key = settings.OPENAI_API_KEY
    if key is None:
        raise LLMServiceError("configuration_error")

    options = {}
    if structured:
        options["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "estimation_result", "strict": True,
                "schema": EstimationResult.model_json_schema(),
            },
        }

    async with AsyncOpenAI(
        api_key=key.get_secret_value(),
        timeout=60.0,
        max_retries=0,
    ) as client:
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages if messages is not None else [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcription},
            ],
            temperature=0.2,
            max_completion_tokens=3000,
            **options,
        )

    if not response.choices:
        raise LLMServiceError("invalid_response")
    choice = response.choices[0]
    if choice.finish_reason != "stop" or getattr(choice.message, "refusal", None):
        raise LLMServiceError("invalid_response")

    result = choice.message.content or ""
    usage = response.usage
    if usage is None:
        raise LLMServiceError("invalid_response")

    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    details = usage.prompt_tokens_details
    cached_tokens = (details.cached_tokens or 0) if details else 0

    # Tarifas USD por millón de tokens. Consulta: 2026-10-20.
    if settings.LLM_MODEL == "gpt-4o-mini":
        input_cost_usd = (
            (input_tokens - cached_tokens) * 0.15
            + cached_tokens * 0.075
        ) / 1_000_000

        output_cost_usd = output_tokens * 0.60 / 1_000_000

        estimated_cost_usd = input_cost_usd + output_cost_usd
    if not result.strip():
        raise LLMServiceError("invalid_response")
    return {
        "estimation": result.strip(),
        "model": response.model,
        "provider": "openai",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost_usd": input_cost_usd,
        "output_cost_usd": output_cost_usd,
        "estimated_cost_usd": (
            round(estimated_cost_usd, 8) if estimated_cost_usd is not None else None
        ),
    }


async def _call_anthropic(
    system_prompt: str, transcription: str, *,
    messages: list[dict[str, str]] | None = None, structured: bool = False,
) -> dict:
    estimated_cost_usd = None
    input_cost_usd = None
    output_cost_usd = None
    key = settings.ANTHROPIC_API_KEY
    if key is None:
        raise LLMServiceError("configuration_error")

    options = {}
    if structured:
        # Solo transporta el resultado tipado; no ejecuta una función externa.
        options = {
            "tools": [{
                "name": "estimation_result",
                "input_schema": EstimationResult.model_json_schema(),
            }],
            "tool_choice": {
                "type": "tool", "name": "estimation_result",
                "disable_parallel_tool_use": True,
            },
        }

    async with AsyncAnthropic(
        default_headers=_anthropic_headers(),
        api_key=key.get_secret_value(),
        timeout=60.0,
        max_retries=0,
    ) as client:
        response = await client.messages.create(
            model=settings.LLM_MODEL,
            system=system_prompt,
            messages=messages[1:] if messages is not None else [
                {"role": "user", "content": transcription},
            ],
            max_tokens=3000,
            **options,
        )

    expected_stop = "tool_use" if structured else "end_turn"
    if response.stop_reason != expected_stop:
        raise LLMServiceError("invalid_response")

    if structured:
        blocks = [block for block in response.content if block.type == "tool_use"]
        if len(blocks) != 1 or blocks[0].name != "estimation_result":
            raise LLMServiceError("invalid_response")
        result = json.dumps(blocks[0].input)
    else:
        result = "\n".join(
            block.text for block in response.content if block.type == "text"
        )

    usage = response.usage
    if usage is None:
        raise LLMServiceError("invalid_response")
    cached_tokens = usage.cache_read_input_tokens or 0
    cache_write_tokens = usage.cache_creation_input_tokens or 0
    input_tokens = (
        usage.input_tokens + cached_tokens + cache_write_tokens
    )
    output_tokens = usage.output_tokens

    # Esta implementación no solicita caché en Anthropic.
    # Si se añade después, hay que contemplar sus tarifas de escritura.
    if (
        settings.LLM_MODEL == "claude-haiku-4-5"
        and cached_tokens == 0
        and cache_write_tokens == 0
    ):
        input_cost_usd = input_tokens * 1.00 / 1_000_000
        output_cost_usd = output_tokens * 5.00 / 1_000_000
        estimated_cost_usd = input_cost_usd + output_cost_usd
    if not result.strip():
        raise LLMServiceError("invalid_response")
    return {
        "estimation": result.strip(),
        "model": response.model,
        "provider": "anthropic",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost_usd": input_cost_usd,
        "output_cost_usd": output_cost_usd,
        "estimated_cost_usd": (
            round(estimated_cost_usd, 8) if estimated_cost_usd is not None else None
        ),
    }

async def stream_estimation_openai(
    transcription: str, requested_model: str | None = None
):
    """Entrega fragmentos de texto y, al final, el resultado con métricas."""
    transcription = transcription.strip()

    if not transcription:
        raise LLMServiceError("invalid_input")

    requested_model = (requested_model or "").strip() or "gpt-4o-mini"

    key = settings.OPENAI_API_KEY
    if key is None or not key.get_secret_value().strip():
        raise LLMServiceError("configuration_error")

    started_at = perf_counter()
    pieces = []
    usage = None
    finish_reason = None
    model = requested_model

    try:
        async with AsyncOpenAI(
            api_key=key.get_secret_value(),
            timeout=60.0,
            max_retries=0,
        ) as client:
            stream = await client.chat.completions.create(
                model=requested_model,
                messages=[
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user", "content": transcription},
                ],
                temperature=0.2,
                max_completion_tokens=3000,
                stream=True,
                stream_options={"include_usage": True},
            )

            async with stream:
                async for chunk in stream:
                    model = chunk.model

                    if chunk.usage is not None:
                        usage = chunk.usage

                    if not chunk.choices:
                        continue

                    choice = chunk.choices[0]

                    if choice.finish_reason is not None:
                        finish_reason = choice.finish_reason

                    text = choice.delta.content
                    if text:
                        pieces.append(text)
                        yield {"type": "text", "text": text}

    except openai.APITimeoutError as exc:
        raise LLMServiceError("provider_timeout") from exc
    except (openai.APIConnectionError, openai.RateLimitError) as exc:
        raise LLMServiceError("provider_unavailable") from exc
    except openai.APIStatusError as exc:
        code = (
            "provider_unavailable"
            if exc.status_code >= 500
            else "provider_rejected"
        )
        raise LLMServiceError(code) from exc
    except openai.APIError as exc:
        raise LLMServiceError("provider_rejected") from exc

    estimation = "".join(pieces)

    if finish_reason != "stop" or not estimation.strip() or usage is None:
        raise LLMServiceError("invalid_response")

    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    details = usage.prompt_tokens_details
    cached_tokens = (details.cached_tokens or 0) if details else 0

    input_cost_usd = None
    output_cost_usd = None
    total_cost_usd = None

    if requested_model == "gpt-4o-mini":
        input_cost_usd = (
            (input_tokens - cached_tokens) * 0.15
            + cached_tokens * 0.075
        ) / 1_000_000

        output_cost_usd = output_tokens * 0.60 / 1_000_000
        total_cost_usd = input_cost_usd + output_cost_usd

    yield {
        "type": "result",
        "result": {
            "estimation": estimation,
            "model": model,
            "provider": "openai",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cached_input_tokens": cached_tokens,
            "input_cost_usd": input_cost_usd,
            "output_cost_usd": output_cost_usd,
            "estimated_cost_usd": total_cost_usd,
            "timestamp": datetime.now(timezone.utc),
            "latency_ms": round((perf_counter() - started_at) * 1000),
        },
    }

async def stream_estimation_anthropic(
    transcription: str, requested_model: str | None = None
):
    """Entrega texto progresivo y el resultado final con métricas."""
    transcription = transcription.strip()

    if not transcription:
        raise LLMServiceError("invalid_input")

    requested_model = (requested_model or "").strip() or "claude-haiku-4-5"

    key = settings.ANTHROPIC_API_KEY
    if key is None or not key.get_secret_value().strip():
        raise LLMServiceError("configuration_error")

    started_at = perf_counter()

    try:
        async with AsyncAnthropic(
            default_headers=_anthropic_headers(),
            api_key=key.get_secret_value(),
            timeout=60.0,
            max_retries=0,
        ) as client:
            async with client.messages.stream(
                model=requested_model,
                system=build_system_prompt(),
                messages=[
                    {"role": "user", "content": transcription},
                ],
                max_tokens=3000,
            ) as stream:
                async for text in stream.text_stream:
                    yield {"type": "text", "text": text}

                message = await stream.get_final_message()

    except anthropic.APITimeoutError as exc:
        raise LLMServiceError("provider_timeout") from exc
    except (anthropic.APIConnectionError, anthropic.RateLimitError) as exc:
        raise LLMServiceError("provider_unavailable") from exc
    except anthropic.APIStatusError as exc:
        code = (
            "provider_unavailable"
            if exc.status_code >= 500
            else "provider_rejected"
        )
        raise LLMServiceError(code) from exc
    except anthropic.APIError as exc:
        raise LLMServiceError("provider_rejected") from exc

    estimation = "".join(
        block.text
        for block in message.content
        if block.type == "text"
    )

    if message.stop_reason != "end_turn" or not estimation.strip():
        raise LLMServiceError("invalid_response")

    usage = message.usage
    cached_tokens = usage.cache_read_input_tokens or 0
    cache_write_tokens = usage.cache_creation_input_tokens or 0

    input_tokens = (
        usage.input_tokens + cached_tokens + cache_write_tokens
    )
    output_tokens = usage.output_tokens

    input_cost_usd = None
    output_cost_usd = None
    total_cost_usd = None

    # Conservamos las tarifas registradas en esta práctica.
    # Esta llamada no solicita caché a Anthropic.
    if (
        requested_model == "claude-haiku-4-5"
        and cached_tokens == 0
        and cache_write_tokens == 0
    ):
        input_cost_usd = input_tokens * 1.00 / 1_000_000
        output_cost_usd = output_tokens * 5.00 / 1_000_000
        total_cost_usd = input_cost_usd + output_cost_usd

    yield {
        "type": "result",
        "result": {
            "estimation": estimation,
            "model": message.model,
            "provider": "anthropic",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cached_input_tokens": cached_tokens,
            "input_cost_usd": input_cost_usd,
            "output_cost_usd": output_cost_usd,
            "estimated_cost_usd": total_cost_usd,
            "timestamp": datetime.now(timezone.utc),
            "latency_ms": round((perf_counter() - started_at) * 1000),
        },
    }
