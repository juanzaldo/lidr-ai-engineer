from itertools import product
import unittest

from jinja2 import TemplateNotFound, UndefinedError

from app.prompts.loader import environment, render_estimation_prompt
from app.schemas.estimation import (
    DetailLevel, EstimationRequest, OutputFormat, ProjectType,
)


class PromptTests(unittest.TestCase):
    def request(self, **changes):
        return EstimationRequest(**{
            "description": "  Gestión de préstamos <equipo> y {{ datos }} & reservas.\n  ",
            "project_type": "internal_tool",
            "detail_level": "medium",
            "output_format": "phases_table",
            **changes,
        })

    def test_description_is_literal_inside_project_block(self):
        request = self.request()
        system, user = render_estimation_prompt(request)
        self.assertIn(f"<project_description>\n{request.description}\n</project_description>", user)
        self.assertNotIn(request.description, system)

    def test_output_format_changes_instructions_and_examples(self):
        table, _ = render_estimation_prompt(self.request())
        narrative, _ = render_estimation_prompt(self.request(output_format="narrative"))
        self.assertIn("phases_table", table)
        self.assertIn("| Fase |", table)
        self.assertNotIn("phases_table", narrative)
        self.assertNotIn("| Fase |", narrative)
        self.assertIn("párrafos narrativos", narrative)

    def test_detailed_requires_assumptions_per_phase(self):
        detailed, _ = render_estimation_prompt(self.request(detail_level="detailed"))
        summary, _ = render_estimation_prompt(self.request(detail_level="summary"))
        self.assertIn("Lista supuestos por fase", detailed)
        self.assertNotIn("supuestos por fase", summary.lower())

    def test_every_supported_combination_renders_with_two_examples(self):
        for project, detail, output in product(ProjectType, DetailLevel, OutputFormat):
            with self.subTest(project=project, detail=detail, output=output):
                system, user = render_estimation_prompt(self.request(
                    project_type=project, detail_level=detail, output_format=output,
                ))
                self.assertIn(project.value, system)
                self.assertIn("Ejemplo 1", system)
                self.assertIn("Ejemplo 2", system)
                self.assertIn(self.request().description, user)

    def test_missing_variable_fails_loudly(self):
        template = environment.get_template("estimation/v1/system.j2")
        with self.assertRaises(UndefinedError):
            template.render(project_type="web_saas")

    def test_unknown_version_does_not_silently_use_v1(self):
        with self.assertRaises(TemplateNotFound):
            render_estimation_prompt(self.request(), version="v999")
        with self.assertRaises(ValueError):
            render_estimation_prompt(self.request(), version="../legacy")
