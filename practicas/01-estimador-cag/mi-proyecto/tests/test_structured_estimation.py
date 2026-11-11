"""Contrato y adaptadores estructurados con SDK simulado, sin consumo de tokens."""

from copy import deepcopy
import json
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

import anthropic
import httpx
import openai
from pydantic import SecretStr, ValidationError

from app.schemas.estimation import EstimationResult, StructuredEstimationResponse
from app.sessions import ConversationHistory

with patch.dict(os.environ, {
    "OPENAI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key",
    "LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-4o-mini",
    "LOG_LEVEL": "CRITICAL",
}):
    from app.services import llm_service as service
    from app.services.errors import LLMServiceError
    from app.logging_config import EventFormatter


def valid_estimation():
    return {
        "summary": "Portal Nimbus para reservar salas de reuniones.",
        "confidence_pct": 80,
        "phases": [
            {"name": "Diseño", "duration_weeks": 2, "cost_eur": 1000,
             "summary": "Definir los flujos principales y sus pantallas."},
            {"name": "Desarrollo", "duration_weeks": 3, "cost_eur": 2000,
             "summary": "Construir el calendario y gestionar reservas."},
        ],
        "total_duration_weeks": 4,
        "total_cost_eur": 3000,
    }


class StructuredContractTests(unittest.TestCase):
    def test_valid_result_can_have_overlapping_phases(self):
        result = EstimationResult.model_validate(valid_estimation())
        response = StructuredEstimationResponse(result=result, prompt_version="v2")
        self.assertEqual(response.model_dump()["result"], valid_estimation())

    def test_cost_and_low_confidence_rules(self):
        data = valid_estimation()
        data["total_cost_eur"] = 4000
        with self.assertRaises(ValidationError):
            EstimationResult.model_validate(data)
        data = valid_estimation()
        data["confidence_pct"] = 29
        with self.assertRaises(ValidationError):
            EstimationResult.model_validate(data)
        data["summary"] = "Out of scope: faltan detalles para una estimación fiable."
        self.assertEqual(EstimationResult.model_validate(data).confidence_pct, 29)
        data["confidence_pct"] = 30
        data["summary"] = "Alcance preliminar con información limitada."
        EstimationResult.model_validate(data)

    def test_rejects_wrong_types_bounds_extra_fields_and_empty_phases(self):
        for changes in (
            {"total_cost_eur": "3000"}, {"confidence_pct": True},
            {"confidence_pct": 101}, {"confidence_pct": -1},
            {"phases": []}, {"phases": valid_estimation()["phases"] * 5},
            {"summary": " " * 20}, {"total_duration_weeks": 0},
            {"total_duration_weeks": 105}, {"unexpected": "data"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                EstimationResult.model_validate({**valid_estimation(), **changes})
        for changes in (
            {"name": " "}, {"cost_eur": -1}, {"duration_weeks": 53},
            {"duration_weeks": 1.5}, {"unexpected": "data"},
        ):
            data = valid_estimation()
            data["phases"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                EstimationResult.model_validate(data)


class StructuredAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = NS(
            LLM_PROVIDER="openai", LLM_MODEL="gpt-4o-mini",
            OPENAI_API_KEY=SecretStr("test-key"),
            ANTHROPIC_API_KEY=SecretStr("test-key"), ANTHROPIC_WORKSPACE_ID=None,
        )
        self.enterContext(patch.object(service, "settings", self.config))
        self.factories = {
            provider: self.enterContext(patch.object(
                service, name, side_effect=AssertionError("Cliente real prohibido"),
            ))
            for provider, name in (("openai", "AsyncOpenAI"), ("anthropic", "AsyncAnthropic"))
        }
        for target in ("httpx.AsyncHTTPTransport.handle_async_request", "socket.create_connection"):
            self.enterContext(patch(target, side_effect=AssertionError("Red prohibida")))
        history = ConversationHistory()
        history.append(user="Proyecto Nimbus", assistant="Estimación anterior")
        self.messages = history.to_messages_list(
            system_prompt="Nombre: Nimbus; equipo: 3", current_user="Añade calendario",
        )

    def response(self, provider, data=None):
        data = valid_estimation() if data is None else data
        if provider == "openai":
            return NS(
                choices=[NS(finish_reason="stop", message=NS(content=json.dumps(data), refusal=None))],
                usage=NS(prompt_tokens=100, completion_tokens=50,
                         prompt_tokens_details=NS(cached_tokens=0)),
                model="gpt-4o-mini-test",
            )
        return NS(
            stop_reason="tool_use", model="claude-haiku-test",
            content=[NS(type="tool_use", name="estimation_result", input=data)],
            usage=NS(input_tokens=100, output_tokens=50,
                     cache_read_input_tokens=0, cache_creation_input_tokens=0),
        )

    def mock_provider(self, provider, response):
        self.config.LLM_PROVIDER = provider
        self.config.LLM_MODEL = "gpt-4o-mini" if provider == "openai" else "claude-haiku-4-5"
        client = AsyncMock()
        client.__aenter__.return_value = client
        call = client.chat.completions.create if provider == "openai" else client.messages.create
        call.return_value = response
        self.factories[provider].side_effect = None
        self.factories[provider].return_value = client
        return client, call

    async def test_both_providers_receive_full_history_and_return_validated_result(self):
        original = deepcopy(self.messages)
        for provider in ("openai", "anthropic"):
            with self.subTest(provider=provider):
                client, call = self.mock_provider(provider, self.response(provider))
                result = await service.generate_structured_estimation(self.messages)
                self.assertIsInstance(result["result"], EstimationResult)
                self.assertEqual(result["result"].total_cost_eur, 3000)
                self.assertNotIn("estimation", result)
                self.assertEqual(result["total_tokens"], 150)
                self.assertIsNotNone(result["timestamp"].tzinfo)
                self.assertGreaterEqual(result["latency_ms"], 0)
                args = call.call_args.kwargs
                if provider == "openai":
                    self.assertEqual(args["messages"], original)
                    schema = args["response_format"]["json_schema"]
                    self.assertTrue(schema["strict"])
                    self.assertEqual(schema["schema"], EstimationResult.model_json_schema())
                else:
                    self.assertEqual(args["system"], original[0]["content"])
                    self.assertEqual(args["messages"], original[1:])
                    self.assertEqual(args["tools"][0]["input_schema"], EstimationResult.model_json_schema())
                    self.assertEqual(args["tool_choice"], {
                        "type": "tool", "name": "estimation_result", "disable_parallel_tool_use": True,
                    })
                self.assertEqual(self.messages, original)
                call.assert_awaited_once()
                client.__aexit__.assert_awaited_once()

    async def test_invalid_history_never_creates_a_client(self):
        cases = [[], None, self.messages[:-1], self.messages[1:]]
        for index, change in (
            (0, {"role": "user"}), (1, {"role": "system"}),
            (2, {"role": "user"}), (3, {"content": " "}),
            (3, {"content": 123}), (1, {"unexpected": "value"}),
        ):
            case = deepcopy(self.messages)
            case[index].update(change)
            cases.append(case)
        for case in cases:
            with self.subTest(messages=case), self.assertRaises(LLMServiceError) as caught:
                await service.generate_structured_estimation(case)
            self.assertEqual(caught.exception.code, "invalid_input")
        for factory in self.factories.values():
            factory.assert_not_called()

    async def test_invalid_business_result_is_rejected_once_for_each_provider(self):
        for provider in ("openai", "anthropic"):
            for changes in ({"total_cost_eur": 9000}, {"confidence_pct": 15}, {"phases": []}):
                data = {**valid_estimation(), **changes}
                _, call = self.mock_provider(provider, self.response(provider, data))
                with self.subTest(provider=provider, changes=changes), self.assertRaises(LLMServiceError) as caught:
                    await service.generate_structured_estimation(self.messages)
                self.assertEqual(caught.exception.code, "invalid_response")
                call.assert_awaited_once()

    async def test_openai_rejects_refusal_truncation_and_malformed_json(self):
        cases = []
        for content in ("not json", "```json\n{}\n```", "", "null"):
            response = self.response("openai")
            response.choices[0].message.content = content
            cases.append(response)
        for reason in ("length", "content_filter"):
            response = self.response("openai")
            response.choices[0].finish_reason = reason
            cases.append(response)
        response = self.response("openai")
        response.choices[0].message.refusal = "private-refusal"
        cases.append(response)
        response = self.response("openai")
        response.usage = None
        cases.append(response)
        for response in cases:
            self.mock_provider("openai", response)
            with self.assertRaises(LLMServiceError) as caught:
                await service.generate_structured_estimation(self.messages)
            self.assertEqual(caught.exception.code, "invalid_response")

    async def test_anthropic_rejects_missing_wrong_duplicate_or_truncated_tool(self):
        cases = []
        for content in (
            [], [NS(type="text", text="Sin resultado tipado")],
            [NS(type="tool_use", name="wrong_tool", input=valid_estimation())],
            self.response("anthropic").content * 2,
        ):
            response = self.response("anthropic")
            response.content = content
            cases.append(response)
        for reason in ("end_turn", "max_tokens", "refusal"):
            response = self.response("anthropic")
            response.stop_reason = reason
            cases.append(response)
        response = self.response("anthropic")
        response.usage = None
        cases.append(response)
        for response in cases:
            self.mock_provider("anthropic", response)
            with self.assertRaises(LLMServiceError) as caught:
                await service.generate_structured_estimation(self.messages)
            self.assertEqual(caught.exception.code, "invalid_response")

    async def test_structured_errors_preserve_sanitized_mapping_and_do_not_retry(self):
        request = httpx.Request("POST", "https://example.invalid")
        for provider, sdk in (("openai", openai), ("anthropic", anthropic)):
            for error, code in (
                (sdk.APITimeoutError(request=request), "provider_timeout"),
                (sdk.APIConnectionError(request=request), "provider_unavailable"),
                (sdk.AuthenticationError("private-key", response=httpx.Response(401, request=request), body=None), "provider_rejected"),
                (RuntimeError("private-project"), "internal_error"),
            ):
                _, call = self.mock_provider(provider, self.response(provider))
                call.side_effect = error
                with self.assertLogs("estimator.llm", level="INFO") as logs:
                    with self.assertRaises(LLMServiceError) as caught:
                        await service.generate_structured_estimation(self.messages)
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn("private-", str(caught.exception))
                rendered = "\n".join(EventFormatter().format(r) for r in logs.records)
                self.assertNotIn("private-", rendered)
                call.assert_awaited_once()
                self.assertEqual(self.factories[provider].call_args.kwargs["max_retries"], 0)

    async def test_validation_errors_are_not_logged_with_provider_content(self):
        data = valid_estimation()
        data["total_cost_eur"] = "private-project-data"
        self.mock_provider("openai", self.response("openai", data))
        with self.assertLogs("estimator.llm", level="INFO") as logs:
            with self.assertRaises(LLMServiceError):
                await service.generate_structured_estimation(self.messages)
        rendered = "\n".join(EventFormatter().format(r) for r in logs.records)
        self.assertNotIn("private-project-data", rendered)
        self.assertIn("invalid_response", rendered)
        self.assertNotIn("estimation_completed", rendered)


if __name__ == "__main__":
    unittest.main()
