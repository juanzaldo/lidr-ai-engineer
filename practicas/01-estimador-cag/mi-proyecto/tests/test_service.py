"""Pruebas de los adaptadores con respuestas SDK simuladas, sin red."""

import io
import json
import logging
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

import anthropic
import httpx
import openai
from pydantic import SecretStr

with patch.dict(os.environ, {
    "OPENAI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key",
    "LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-4o-mini",
    "LOG_LEVEL": "CRITICAL",
}):
    from app.services import llm_service as service
    from app.services.errors import LLMServiceError
    from app.logging_config import configure_logging, EventFormatter


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = NS(
            LLM_PROVIDER="openai", LLM_MODEL="gpt-4o-mini",
            OPENAI_API_KEY=SecretStr("test-key"),
            ANTHROPIC_API_KEY=SecretStr("test-key"),
            ANTHROPIC_WORKSPACE_ID=None,
        )
        self.enterContext(patch.object(service, "settings", self.config))
        # Prohibir crear clientes reales incluso si un test olvida simularlos.
        self.openai_factory = self.enterContext(patch.object(
            service, "AsyncOpenAI", side_effect=AssertionError("Cliente real prohibido")
        ))
        self.anthropic_factory = self.enterContext(patch.object(
            service, "AsyncAnthropic", side_effect=AssertionError("Cliente real prohibido")
        ))

    def openai_response(self):
        return NS(
            choices=[NS(finish_reason="stop", message=NS(content="Estimación"))],
            usage=NS(prompt_tokens=100, completion_tokens=50,
                     prompt_tokens_details=NS(cached_tokens=40)),
            model="gpt-4o-mini-test",
        )

    def mock_openai(self, response):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.chat.completions.create.return_value = response
        self.openai_factory.side_effect = None
        self.openai_factory.return_value = client
        return client

    async def test_openai_context_usage_and_cached_cost(self):
        client = self.mock_openai(self.openai_response())
        result = await service.generate_estimation(" Nueva reunión ")
        self.assertEqual(result["total_tokens"], 150)
        self.assertAlmostEqual(result["estimated_cost_usd"], 0.000042)
        self.assertIsNotNone(result["timestamp"].tzinfo)
        self.assertGreaterEqual(result["latency_ms"], 0)
        args = client.chat.completions.create.call_args.kwargs
        self.assertEqual(args["messages"], [
            {"role": "system", "content": service.build_system_prompt()},
            {"role": "user", "content": "Nueva reunión"},
        ])
        client.__aexit__.assert_awaited_once()
        self.anthropic_factory.assert_not_called()

    async def test_anthropic_context_blocks_and_cost(self):
        self.config.LLM_PROVIDER = "anthropic"
        self.config.LLM_MODEL = "claude-haiku-4-5"
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.messages.create.return_value = NS(
            stop_reason="end_turn", model="claude-haiku-test",
            content=[NS(type="text", text="Parte 1"), NS(type="thinking"),
                     NS(type="text", text="Parte 2")],
            usage=NS(input_tokens=100, output_tokens=50,
                     cache_read_input_tokens=0, cache_creation_input_tokens=0),
        )
        self.anthropic_factory.side_effect = None
        self.anthropic_factory.return_value = client
        result = await service.generate_estimation("Nueva reunión")
        self.assertEqual(result["estimation"], "Parte 1\nParte 2")
        self.assertAlmostEqual(result["estimated_cost_usd"], 0.00035)
        self.assertEqual(client.messages.create.call_args.kwargs["system"],
                         service.build_system_prompt())
        self.assertEqual(client.messages.create.call_args.kwargs["messages"],
                         [{"role": "user", "content": "Nueva reunión"}])
        client.__aexit__.assert_awaited_once()
        self.openai_factory.assert_not_called()

    async def test_rejects_empty_and_truncated_responses(self):
        for text, reason in (("  ", "stop"), ("Parcial", "length")):
            with self.subTest(reason=reason):
                response = self.openai_response()
                response.choices[0].message.content = text
                response.choices[0].finish_reason = reason
                self.mock_openai(response)
                with self.assertRaises(LLMServiceError) as caught:
                    await service.generate_estimation("Reunión")
                self.assertEqual(caught.exception.code, "invalid_response")

    async def test_invalid_input_does_not_create_client(self):
        with self.assertRaises(LLMServiceError) as caught:
            await service.generate_estimation("   ")
        self.assertEqual(caught.exception.code, "invalid_input")
        self.openai_factory.assert_not_called()
        self.anthropic_factory.assert_not_called()

    async def test_rendered_prompt_pair_reaches_each_provider_separately(self):
        from app.prompts.loader import render_estimation_prompt
        from app.schemas.estimation import EstimationRequest

        system, user = render_estimation_prompt(EstimationRequest(
            description="Un portal para reservar equipos audiovisuales.",
            project_type="web_saas", detail_level="detailed", output_format="narrative",
        ))
        for provider in ("openai", "anthropic"):
            self.config.LLM_PROVIDER = provider
            with patch.object(service, f"_call_{provider}", AsyncMock(return_value={
                "estimation": "Respuesta", "input_tokens": 100, "output_tokens": 50,
            })) as call:
                await service.generate_estimation(user, system_prompt=system)
                call.assert_awaited_once_with(system, user)

    async def test_sdk_errors_are_sanitized_for_both_providers(self):
        request = httpx.Request("POST", "https://example.invalid")
        for sdk, provider in ((openai, "openai"), (anthropic, "anthropic")):
            self.config.LLM_PROVIDER = provider
            cases = [
                (sdk.APITimeoutError(request=request), "provider_timeout"),
                (sdk.APIConnectionError(request=request), "provider_unavailable"),
                (RuntimeError("private-secret-and-transcription"), "internal_error"),
            ]
            for status, error_type, code in (
                (429, sdk.RateLimitError, "provider_unavailable"),
                (401, sdk.AuthenticationError, "provider_rejected"),
                (500, sdk.InternalServerError, "provider_unavailable"),
            ):
                cases.append((error_type(
                    "private-secret-and-transcription",
                    response=httpx.Response(status, request=request), body=None,
                ), code))
            for error, code in cases:
                with self.subTest(provider=provider, error=type(error).__name__):
                    with patch.object(service, f"_call_{provider}",
                                      AsyncMock(side_effect=error)):
                        with self.assertLogs("estimator.llm", level="INFO") as logs:
                            with self.assertRaises(LLMServiceError) as caught:
                                await service.generate_estimation("private-transcription")
                    self.assertEqual(caught.exception.code, code)
                    self.assertNotIn("private-", str(caught.exception))
                    rendered = "\n".join(EventFormatter().format(r) for r in logs.records)
                    self.assertNotIn("private-", rendered)
                    self.assertIn(code, rendered)


class LoggingTests(unittest.TestCase):
    def test_level_json_and_no_duplicate_handlers(self):
        logger = logging.getLogger("estimator")
        old = (logger.handlers[:], logger.level, logger.propagate)
        logger.handlers = []
        stream = io.StringIO()
        try:
            with patch("sys.stderr", stream):
                configure_logging("WARNING")
                configure_logging("WARNING")
                self.assertEqual(len(logger.handlers), 1)
                logger.info("hidden")
                logger.warning("visible", extra={"provider": "openai", "secret": "private"})
            records = [json.loads(line) for line in stream.getvalue().splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["event"], "visible")
            self.assertNotIn("secret", records[0])
        finally:
            for handler in logger.handlers:
                handler.close()
            logger.handlers, logger.level, logger.propagate = old
