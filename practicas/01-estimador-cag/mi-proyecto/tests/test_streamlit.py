"""Pruebas del formulario y del contrato HTTP sin llamadas externas."""
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest


class FormTests(unittest.TestCase):
    def setUp(self):
        self.post = self.enterContext(patch("httpx.post"))
        self.enterContext(patch(
            "httpx.HTTPTransport.handle_request",
            side_effect=AssertionError("Sin red en tests"),
        ))
        self.app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "streamlit_app.py"),
            default_timeout=30,
        ).run()
        self.assertFalse(self.app.exception)

    def submit(self, description="Una aplicación para gestionar préstamos de equipo."):
        self.app.text_area[0].set_value(description)
        self.app.button[0].click().run()
        self.assertFalse(self.app.exception)

    def test_form_posts_typed_json_and_preserves_results_on_rerun(self):
        self.post.return_value = httpx.Response(
            200, request=httpx.Request("POST", "http://test/estimate"),
            json={"text": "## Estimación simulada", "prompt_version": "v1"},
        )
        self.app.selectbox[0].select("data_pipeline")
        self.app.selectbox[1].select("detailed")
        self.app.selectbox[2].select("narrative")
        self.submit()
        self.assertTrue(self.post.call_args.args[0].endswith("/estimate"))
        self.assertEqual(self.post.call_args.kwargs["json"], {
            "description": "Una aplicación para gestionar préstamos de equipo.",
            "project_type": "data_pipeline", "detail_level": "detailed",
            "output_format": "narrative",
        })
        self.assertTrue(any("Estimación simulada" in m.value for m in self.app.markdown))
        self.app.run()
        self.post.assert_called_once()
        self.assertEqual(len(self.app.session_state.estimations), 1)
        self.submit("Un portal web para reservar equipos audiovisuales.")
        self.assertEqual(len(self.app.session_state.estimations), 2)

    def test_short_description_never_calls_api(self):
        self.submit("Breve")
        self.post.assert_not_called()
        self.assertTrue(self.app.error)

    def test_connection_failure_displays_error_without_saving_result(self):
        self.post.side_effect = httpx.ConnectError("Sin servicio")
        self.submit()
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.session_state.estimations, [])

    def test_http_error_does_not_display_provider_secrets(self):
        self.post.return_value = httpx.Response(
            502, request=httpx.Request("POST", "http://test/estimate"),
            json={"detail": "private-provider-secret"},
        )
        self.submit()
        self.assertTrue(self.app.error)
        self.assertNotIn("private-provider-secret", self.app.error[0].value)
        self.assertEqual(self.app.session_state.estimations, [])

    def test_invalid_response_is_not_saved(self):
        self.post.return_value = httpx.Response(
            200, request=httpx.Request("POST", "http://test/estimate"),
            json={"unexpected": "value"},
        )
        self.submit()
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.session_state.estimations, [])
