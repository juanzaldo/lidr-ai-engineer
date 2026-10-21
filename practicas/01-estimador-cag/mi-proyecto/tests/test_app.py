"""Pruebas locales sin credenciales reales ni llamadas al proveedor."""

import os
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

# La configuración se carga al importar la aplicación. Usamos valores ficticios.
with patch.dict(os.environ, {
    "OPENAI_API_KEY": "test-not-a-real-key",
    "ANTHROPIC_API_KEY": "test-not-a-real-key",
    "LLM_PROVIDER": "openai",
    "LLM_MODEL": "gpt-4o-mini",
    "APP_ENV": "test",
}):
    from app.main import app
    from app.context.examples import ESTIMATION_EXAMPLES
    from app.services.llm_service import build_system_prompt


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        # TestClient usa un transporte interno; las conexiones externas fallan.
        for target in (
            "httpx.HTTPTransport.handle_request",
            "httpx.AsyncHTTPTransport.handle_async_request",
            "socket.create_connection",
        ):
            blocker = patch(target, side_effect=AssertionError("Red externa prohibida en tests"))
            blocker.start()
            self.addCleanup(blocker.stop)

        self.llm = AsyncMock(side_effect=AssertionError("LLM no esperado"))
        replacement = patch("app.routers.estimations.generate_estimation", self.llm)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.client = self.enterContext(TestClient(app))

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.llm.assert_not_called()

    def test_invalid_transcriptions_do_not_call_llm(self):
        for body in ({}, {"transcription": ""}, {"transcription": "   "},
                     {"transcription": None}, {"transcription": 123}):
            with self.subTest(body=body):
                response = self.client.post("/api/v1/estimate", json=body)
                self.assertEqual(response.status_code, 422)
        self.llm.assert_not_called()

    def test_estimate_returns_service_data(self):
        expected = {
            "estimation": "## Estimación de prueba",
            "model": "gpt-4o-mini-test",
            "provider": "openai",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "estimated_cost_usd": 0.000045,
            "timestamp": datetime(2026, 10, 20, tzinfo=timezone.utc),
            "latency_ms": 25,
        }
        self.llm.side_effect = None
        self.llm.return_value = expected
        response = self.client.post(
            "/api/v1/estimate", json={"transcription": "  Necesitamos un blog.  "}
        )
        self.assertEqual(response.status_code, 200)
        actual = response.json()
        self.assertEqual(set(actual), set(expected))
        for field, value in expected.items():
            if field != "timestamp":
                self.assertEqual(actual[field], value)
        self.assertEqual(
            datetime.fromisoformat(actual["timestamp"].replace("Z", "+00:00")),
            expected["timestamp"],
        )
        self.llm.assert_awaited_once_with("Necesitamos un blog.")

    def test_swagger_and_openapi(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/health", schema["paths"])
        self.assertIn("post", schema["paths"]["/api/v1/estimate"])
        self.llm.assert_not_called()

    def test_static_examples_are_in_prompt(self):
        self.assertGreaterEqual(len(ESTIMATION_EXAMPLES), 2)
        prompt = build_system_prompt()
        for example in ESTIMATION_EXAMPLES:
            self.assertTrue(example["meeting_summary"].strip())
            self.assertTrue(example["estimation"].strip())
            self.assertIn(example["meeting_summary"], prompt)
            self.assertIn(example["estimation"], prompt)

    def test_required_structure(self):
        root = Path(__file__).resolve().parents[1]
        required = (
            "app/__init__.py", "app/main.py", "app/config.py",
            "app/routers/__init__.py", "app/routers/estimations.py",
            "app/services/__init__.py", "app/services/llm_service.py",
            "app/context/__init__.py", "app/context/examples.py",
            ".env.example", ".gitignore", "pyproject.toml", "uv.lock", "README.md",
        )
        for relative in required:
            with self.subTest(file=relative):
                self.assertTrue((root / relative).is_file(), f"Falta {relative}")
        self.assertTrue((root.parent / "transcripcion-reunion.txt").is_file())

    def test_env_template_has_no_values(self):
        template = Path(__file__).resolve().parents[1] / ".env.example"
        variables = {}
        for line in template.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                name, value = line.split("=", 1)
                variables[name.strip()] = value.strip()
        self.assertEqual(set(variables), {
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER",
            "LLM_MODEL", "APP_ENV", "LOG_LEVEL",
        })
        self.assertTrue(all(value == "" for value in variables.values()),
                        "La plantilla debe tener las variables sin valores")


if __name__ == "__main__":
    unittest.main()
