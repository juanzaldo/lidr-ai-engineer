"""Memoria conversacional volátil para un único proceso de FastAPI.

El ejercicio acepta perder las sesiones al reiniciar: todavía no necesita
persistencia ni compartir estado entre workers. Los endpoints comparten un store
en este proceso y serializan las peticiones de cada sesión con su propio lock.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


MAX_TURNS = 6


class ConversationHistory:
    """Conserva como máximo N turnos completos, cada uno user + assistant.

    El system prompt se recibe de nuevo en cada llamada, renderizado con los
    metadatos actuales. Nunca ocupa un turno ni se pierde al recortar la ventana.
    Solo se añade un par después de obtener una respuesta válida del proveedor.
    """

    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        if type(max_turns) is not int or max_turns < 1:
            raise ValueError("max_turns debe ser un entero positivo")
        self._turns: deque[tuple[str, str]] = deque(maxlen=max_turns)

    @property
    def max_turns(self) -> int:
        limit = self._turns.maxlen
        assert limit is not None
        return limit

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    def append(self, *, user: str, assistant: str) -> None:
        """Añade un par completo; descarta el más antiguo si excede el límite."""
        for content in (user, assistant):
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Los mensajes del turno deben ser texto no vacío")
        self._turns.append((user, assistant))

    def to_messages_list(
        self, *, system_prompt: str, current_user: str | None = None
    ) -> list[dict[str, str]]:
        """Devuelve system + N pares previos + user actual, sin mutar memoria.

        El llamador regenera system_prompt desde ProjectMetadata cada turno.
        El mensaje actual es opcional para inspeccionar el historial; cuando
        se incluye, el máximo es 2 * max_turns + 2 mensajes. Anthropic recibe
        el primer mensaje como parámetro system separado en su adaptador.
        """
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("El system prompt no puede estar vacío")
        if current_user is not None and (
            not isinstance(current_user, str) or not current_user.strip()
        ):
            raise ValueError("El mensaje actual no puede estar vacío")
        messages = [{"role": "system", "content": system_prompt}]
        for user, assistant in self._turns:
            messages.extend([
                {"role": "user", "content": user},
                {"role": "assistant", "content": assistant},
            ])
        if current_user is not None:
            messages.append({"role": "user", "content": current_user})
        return messages


class ProjectMetadata(BaseModel):
    """Hechos del proyecto separados del historial que puede ser descartado."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    project_name: str | None = Field(default=None, min_length=1, max_length=120)
    assumed_team_size: int | None = Field(default=None, strict=True, ge=1, le=50)
    mentioned_technologies: list[str] = Field(default_factory=list)
    agreed_scope: str | None = Field(default=None, min_length=1, max_length=2000)

    def is_empty(self) -> bool:
        return (
            self.project_name is None
            and self.assumed_team_size is None
            and not self.mentioned_technologies
            and self.agreed_scope is None
        )


@dataclass
class Session:
    """Estado de un proyecto; se pierde al reiniciar por diseño de esta fase."""

    session_id: str = field(default_factory=lambda: str(uuid4()))
    history: ConversationHistory = field(default_factory=ConversationHistory)
    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class SessionNotFoundError(KeyError):
    """Identificador desconocido, por ejemplo tras reiniciar el proceso."""


class SessionStore:
    """Diccionario por proceso: sin BBDD y sin sincronización entre workers.

    Un store compartido por la aplicación conservará las sesiones entre
    peticiones. Cada instancia nueva empieza vacía, también en los tests.
    """

    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        self.max_turns = ConversationHistory(max_turns).max_turns
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        session = Session(history=ConversationHistory(self.max_turns))
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(session_id) from None
