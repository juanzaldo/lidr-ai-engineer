"""Configuración pytest y datos ficticios: jamás usar claves reales en la suite."""
import os

import pytest

os.environ.update({
    "OPENAI_API_KEY": "test-not-real", "ANTHROPIC_API_KEY": "test-not-real",
    "LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-4o-mini", "LOG_LEVEL": "CRITICAL",
})


@pytest.fixture(autouse=True)
def block_external_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Acceso externo prohibido durante los tests")
    monkeypatch.setattr("httpx.HTTPTransport.handle_request", forbidden)
    monkeypatch.setattr("httpx.AsyncHTTPTransport.handle_async_request", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("app.services.llm_service.AsyncOpenAI", forbidden)
    monkeypatch.setattr("app.services.llm_service.AsyncAnthropic", forbidden)
