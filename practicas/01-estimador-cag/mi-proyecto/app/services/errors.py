"""Errores de dominio con mensajes públicos controlados."""

from typing import Literal


ErrorCode = Literal[
    "invalid_input", "provider_timeout", "provider_unavailable",
    "provider_rejected", "invalid_response", "configuration_error", "internal_error",
]

MESSAGES = {
    "invalid_input": "La transcripción o el historial de mensajes no es válido.",
    "provider_timeout": "El proveedor tardó demasiado en responder.",
    "provider_unavailable": "El proveedor no está disponible. Inténtalo más tarde.",
    "provider_rejected": "No se pudo completar la solicitud con el proveedor.",
    "invalid_response": "El proveedor devolvió una respuesta vacía, incompleta o inválida.",
    "configuration_error": "La configuración del servicio requiere revisión.",
    "internal_error": "Ocurrió un error interno al generar la estimación.",
}


class LLMServiceError(Exception):
    def __init__(self, code: ErrorCode):
        self.code = code
        self.public_message = MESSAGES[code]
        super().__init__(self.public_message)
