"""Prueba de interfaz sin llamadas de pago a proveedores."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

with patch.dict(os.environ, {
    "OPENAI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key",
    "LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-4o-mini",
}):
    from app.services import llm_service as service

from streamlit.testing.v1 import AppTest


class ChatTests(unittest.TestCase):
    def test_switch_preserves_history_and_totals(self):
        calls = []

        def fake(provider):
            async def generate(transcription, requested_model=None):
                calls.append((provider, requested_model))
                yield {"type": "text", "text": "Estimación simulada"}
                yield {"type": "result", "result": {
                    "provider": provider, "model": requested_model,
                    "input_tokens": 100, "output_tokens": 50,
                    "total_tokens": 150, "input_cost_usd": .001,
                    "output_cost_usd": .002, "estimated_cost_usd": .003,
                    "latency_ms": 1200,
                }}
            return generate

        with patch.object(service, "stream_estimation_openai", fake("openai")), \
             patch.object(service, "stream_estimation_anthropic", fake("anthropic")), \
             patch.object(service, "AsyncOpenAI", side_effect=AssertionError("Sin red")), \
             patch.object(service, "AsyncAnthropic", side_effect=AssertionError("Sin red")):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=30).run()
            self.assertFalse(app.exception)
            app.selectbox[0].select("OpenAI · GPT-4o mini").run()
            app.chat_input[0].set_value("Primera transcripción").run()
            self.assertFalse(app.exception)
            app.selectbox[0].select("Anthropic · Claude Haiku 4.5").run()
            self.assertEqual(len(calls), 1)
            app.chat_input[0].set_value("Segunda transcripción").run()
            self.assertFalse(app.exception)
            app.run()
            self.assertEqual(calls, [
                ("openai", "gpt-4o-mini"), ("anthropic", "claude-haiku-4-5"),
            ])
            usages = [m["usage"] for m in app.session_state.messages if "usage" in m]
            self.assertEqual(len(app.session_state.messages), 5)
            self.assertEqual(sum(u["total_tokens"] for u in usages), 300)
            self.assertAlmostEqual(sum(u["estimated_cost_usd"] for u in usages), .006)
            self.assertTrue(any(m.value == "1.20 s" for m in app.metric))
            self.assertTrue(any("System prompt" in e.label for e in app.expander))
            with patch.object(service.settings, "ANTHROPIC_API_KEY", None):
                app.run()
                self.assertTrue(app.chat_input[0].disabled)
