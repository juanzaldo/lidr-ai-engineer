"""Pruebas de memoria en proceso; no importan clientes LLM ni usan red."""

import unittest
from uuid import UUID

from pydantic import ValidationError

from app.sessions import (
    ConversationHistory, ProjectMetadata, Session, SessionNotFoundError,
    SessionStore,
)


class ConversationHistoryTests(unittest.TestCase):
    def test_eight_turns_keep_only_latest_six_complete_pairs(self):
        history = ConversationHistory()
        for turn in range(8):
            outgoing = history.to_messages_list(
                system_prompt=f"Metadatos actuales: {turn}",
                current_user=f"Petición {turn}",
            )
            self.assertLessEqual(len(outgoing), 14)
            self.assertEqual(outgoing[0]["role"], "system")
            self.assertEqual(outgoing[-1]["content"], f"Petición {turn}")
            self.assertEqual(
                [m["role"] for m in outgoing[1:]],
                ["user", "assistant"] * min(turn, 6) + ["user"],
            )
            history.append(user=f"Petición {turn}", assistant=f"Respuesta {turn}")

        messages = history.to_messages_list(system_prompt="Metadatos finales")
        self.assertEqual(history.turn_count, 6)
        self.assertEqual([m["content"] for m in messages[1:]], [
            text for turn in range(2, 8)
            for text in (f"Petición {turn}", f"Respuesta {turn}")
        ])

    def test_configurable_window_and_fresh_system_prompt(self):
        history = ConversationHistory(max_turns=1)
        history.append(user="Proyecto inicial", assistant="Primera estimación")
        history.append(user="Alcance refinado", assistant="Nueva estimación")
        for system in ("Nombre: Nimbus", "Nombre: Nimbus, equipo: 3"):
            self.assertEqual(history.to_messages_list(system_prompt=system), [
                {"role": "system", "content": system},
                {"role": "user", "content": "Alcance refinado"},
                {"role": "assistant", "content": "Nueva estimación"},
            ])

    def test_rendering_pending_turn_does_not_commit_or_expose_mutable_history(self):
        history = ConversationHistory()
        history.append(user="Proyecto", assistant="Estimación")
        messages = history.to_messages_list(system_prompt="Actual", current_user="Pendiente")
        messages[1]["content"] = "Alterado fuera del historial"
        messages.clear()
        stored = history.to_messages_list(system_prompt="Actualizado")
        self.assertEqual(history.turn_count, 1)
        self.assertEqual(stored[1]["content"], "Proyecto")
        self.assertEqual(len(stored), 3)

    def test_invalid_turn_is_rejected_atomically(self):
        history = ConversationHistory(max_turns=1)
        history.append(user="Conservar", assistant="Respuesta válida")
        before = history.to_messages_list(system_prompt="Actual")
        for user, assistant in (("Nuevo", "  "), ("", "Respuesta"), (123, "Respuesta")):
            with self.subTest(user=user, assistant=assistant), self.assertRaises(ValueError):
                history.append(user=user, assistant=assistant)
            self.assertEqual(history.to_messages_list(system_prompt="Actual"), before)

    def test_invalid_window_and_empty_prompts_are_rejected(self):
        for value in (0, -1, 1.5, True, "6"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ConversationHistory(max_turns=value)
        history = ConversationHistory()
        with self.assertRaises(ValueError):
            history.to_messages_list(system_prompt=" ")
        with self.assertRaises(ValueError):
            history.to_messages_list(system_prompt="Actual", current_user=" ")


class SessionTests(unittest.TestCase):
    def test_sessions_have_independent_history_metadata_and_uuid(self):
        store = SessionStore(max_turns=2)
        first, second = store.create(), store.create()
        self.assertEqual(UUID(first.session_id).version, 4)
        self.assertNotEqual(first.session_id, second.session_id)
        first.metadata.project_name = "Nimbus"
        first.metadata.mentioned_technologies.append("Python")
        first.history.append(user="Proyecto Nimbus", assistant="Estimación")
        self.assertIs(store.get(first.session_id), first)
        self.assertEqual(first.history.max_turns, 2)
        self.assertTrue(second.metadata.is_empty())
        self.assertEqual(second.history.turn_count, 0)

    def test_metadata_survives_history_eviction(self):
        session = Session(history=ConversationHistory(max_turns=1))
        session.metadata = ProjectMetadata(
            project_name="Nimbus", assumed_team_size=3,
            mentioned_technologies=["Python"], agreed_scope="Reservar salas",
        )
        session.history.append(user="Proyecto Nimbus", assistant="Estimación inicial")
        session.history.append(user="Añadir calendario", assistant="Estimación revisada")
        self.assertEqual(session.metadata.project_name, "Nimbus")
        self.assertEqual(session.metadata.assumed_team_size, 3)
        self.assertEqual(session.history.turn_count, 1)
        self.assertNotIn("Proyecto Nimbus", str(session.history.to_messages_list(system_prompt="Actual")))

    def test_unknown_session_and_new_store_do_not_recreate_old_state(self):
        store = SessionStore()
        session = store.create()
        with self.assertRaises(SessionNotFoundError):
            store.get("desconocida")
        with self.assertRaises(SessionNotFoundError):
            SessionStore().get(session.session_id)

    def test_metadata_validates_initial_values_and_assignments(self):
        self.assertTrue(ProjectMetadata().is_empty())
        for value in (0, 51, True, 2.5):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ProjectMetadata(assumed_team_size=value)
        with self.assertRaises(ValidationError):
            ProjectMetadata(project_name="x" * 121)
        metadata = ProjectMetadata(assumed_team_size=3)
        with self.assertRaises(ValidationError):
            metadata.assumed_team_size = -1
        self.assertEqual(metadata.assumed_team_size, 3)


if __name__ == "__main__":
    unittest.main()
