from app.services.errors import LLMServiceError
from app.config import settings
from app.services.llm_service import (
    build_system_prompt,
    stream_estimation_openai,
    stream_estimation_anthropic,
)
from app.context.examples import ESTIMATION_EXAMPLES

import re
import streamlit as st

def provider_error_detail(error, transcription=""):
    """Explica el fallo y muestra solo el mensaje del proveedor, con secretos ocultos."""
    cause = error.__cause__
    status = getattr(cause, "status_code", None)
    body = getattr(cause, "body", None)
    detail = body.get("error", body) if isinstance(body, dict) else {}
    message = detail.get("message", "") if isinstance(detail, dict) else ""
    original_message = message if isinstance(message, str) else ""
    message = original_message.lower()

    if status == 400 and any(term in message for term in (
        "credit balance", "insufficient credit", "insufficient balance",
    )):
        explanation = "El proveedor indica que no hay crédito suficiente en la cuenta API. Revisa la facturación de la cuenta asociada a esa clave."
    else:
        explanation = {
            400: "El proveedor rechazó algún parámetro de la solicitud.",
            401: "El proveedor rechazó la API key. Revisa la clave en .env y reinicia Streamlit.",
            403: "La cuenta o clave no tiene permiso para esta solicitud.",
            404: "El modelo o recurso solicitado no está disponible para esta cuenta.",
            429: "Se alcanzó un límite de uso del proveedor. Revisa sus límites e inténtalo más tarde.",
        }.get(status, "No hay un diagnóstico específico disponible todavía.")

    code = f"HTTP {status}" if isinstance(status, int) else error.code
    for key in (settings.OPENAI_API_KEY, settings.ANTHROPIC_API_KEY):
        if key is not None and key.get_secret_value():
            original_message = original_message.replace(key.get_secret_value(), "[CLAVE OCULTA]")
    if transcription:
        original_message = original_message.replace(transcription, "[TRANSCRIPCIÓN OCULTA]")
    original_message = re.sub(r"sk-[A-Za-z0-9_-]+", "[CLAVE OCULTA]", original_message)
    result = f"{code}: {explanation}"
    if original_message:
        result += f"\nDetalle del proveedor: {original_message[:1500]}"
    return result

def show_usage(usage):
    if "provider" in usage and "model" in usage:
        st.caption(f'{usage["provider"]} · {usage["model"]}')

    def money(value):
        return "No disponible" if value is None else f"${value:.8f}"

    st.table([
        {
            "Concepto": "Entrada",
            "Tokens": usage["input_tokens"],
            "Coste estimado USD": money(usage.get("input_cost_usd")),
        },
        {
            "Concepto": "Salida",
            "Tokens": usage["output_tokens"],
            "Coste estimado USD": money(usage.get("output_cost_usd")),
        },
        {
            "Concepto": "Total",
            "Tokens": usage["total_tokens"],
            "Coste estimado USD": money(usage.get("estimated_cost_usd")),
        },
    ])

async def stream_text(transcription, result, provider, model=None):
    if provider == "openai":
        events = stream_estimation_openai(transcription, requested_model=model)
    elif provider == "anthropic":
        events = stream_estimation_anthropic(transcription, requested_model=model)
    else:
        raise LLMServiceError("configuration_error")

    async for event in events:
        if event["type"] == "text":
            yield event["text"]

        elif event["type"] == "result":
            result.update(event["result"])

st.set_page_config(
    page_title="Estimador CAG",
    page_icon="📝",
)

st.title("📝 Estimador de software")
st.caption("Pega la transcripción de una reunión para generar una estimación.")
# Opciones explícitas: ampliar esta lista permite añadir modelos más adelante.
model_options = {
    "OpenAI · GPT-4o mini": ("openai", "gpt-4o-mini"),
    "Anthropic · Claude Haiku 4.5": ("anthropic", "claude-haiku-4-5"),
}
labels = list(model_options)
default_index = 1 if settings.LLM_PROVIDER == "anthropic" else 0

with st.sidebar:
    selected_label = st.selectbox(
        "Modelo para la próxima respuesta",
        options=labels,
        index=default_index,
        key="selected_model",
    )
    st.caption("Cambiar de modelo conserva el historial y el consumo acumulado.")

selected_provider, selected_model = model_options[selected_label]
selected_key = (
    settings.OPENAI_API_KEY
    if selected_provider == "openai"
    else settings.ANTHROPIC_API_KEY
)
key_available = (
    selected_key is not None
    and bool(selected_key.get_secret_value().strip())
)
if not key_available:
    st.warning(
        f"Configura la clave de {selected_provider} en .env y reinicia la aplicación."
    )

st.caption(f"Próxima respuesta: {selected_provider} · {selected_model}")
# Crear el historial solo si todavía no existe.
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hola. Comparte la transcripción de tu reunión.",
        }
    ]

# Dibujar los mensajes guardados en cada ejecución.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if "usage" in message:
            show_usage(message["usage"])

# Recibir un nuevo mensaje.
transcription = st.chat_input(
    "Escribe o pega la transcripción...",
    disabled=not key_available,
)

if transcription:
    transcription = transcription.strip()

    if not transcription:
        st.warning("Escribe una transcripción con contenido.")
    else:
        st.session_state.messages.append(
            {"role": "user", "content": transcription}
        )

        with st.chat_message("user"):
            st.markdown(transcription)

        with st.chat_message("assistant"):
            try:
                result = {}

                response = st.write_stream(
                    stream_text(transcription, result, selected_provider, selected_model)
                )

                if not result:
                    raise LLMServiceError("invalid_response")

                usage = {
                    "provider": result["provider"],
                    "model": result["model"],
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                    "total_tokens": result["total_tokens"],
                    "input_cost_usd": result.get("input_cost_usd"),
                    "output_cost_usd": result.get("output_cost_usd"),
                    "estimated_cost_usd": result.get("estimated_cost_usd"),
                }

                show_usage(usage)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response,
                        "usage": usage,
                    }
                )

                st.session_state.last_result = result

            except LLMServiceError as error:
                st.error(error.public_message)
                st.text(provider_error_detail(error, transcription))
                st.caption(
                    "Si apareció texto parcial, la generación no se completó. "
                    "Esta llamada no se añadió al acumulado y puede haber "
                    "generado consumo en el proveedor."
                )
# Obtener los consumos registrados en el historial.
usages = [
    message["usage"]
    for message in st.session_state.messages
    if "usage" in message
]

totals = {
    "input_tokens": sum(item["input_tokens"] for item in usages),
    "output_tokens": sum(item["output_tokens"] for item in usages),
    "total_tokens": sum(item["total_tokens"] for item in usages),
}

for field in (
    "input_cost_usd",
    "output_cost_usd",
    "estimated_cost_usd",
):
    values = [item.get(field) for item in usages]

    totals[field] = (
        sum(values)
        if all(value is not None for value in values)
        else None
    )

with st.sidebar:
    st.header("Contexto CAG")
    with st.expander("System prompt activo (solo lectura)"):
        st.code(build_system_prompt(), language=None)
    with st.expander("Ejemplos de referencia"):
        for index, example in enumerate(ESTIMATION_EXAMPLES, start=1):
            st.subheader(f"Ejemplo {index}")
            st.write(example["meeting_summary"])
            st.markdown(example["estimation"])

    last_result = st.session_state.get("last_result")
    if last_result:
        st.header("Última llamada completada")
        st.caption(f'{last_result["provider"]} · {last_result["model"]}')
        st.metric("Tokens de entrada", last_result["input_tokens"])
        st.metric("Tokens de salida", last_result["output_tokens"])
        st.metric("Tiempo de respuesta", f'{last_result["latency_ms"] / 1000:.2f} s')

    st.header("Consumo de esta sesión")
    st.caption(f"Llamadas con métricas registradas: {len(usages)}")
    show_usage(totals)

    st.caption(
        "Entrada: instrucciones, ejemplos CAG y transcripción. "
        "Salida: respuesta del modelo. "
        "Los costes son estimados en USD."
    )

    st.caption(
        "El acumulado incluye únicamente las respuestas con métricas "
        "guardadas en esta sesión. No representa el saldo de tu cuenta."
    )
