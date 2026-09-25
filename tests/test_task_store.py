from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime
import unittest
from unittest.mock import Mock

from assistant import VirtualAssistant
from services import NoteStore, ReminderStore, Settings, SettingsStore, TaskStore


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.store = TaskStore(Path(self.temp_dir.name) / "tasks.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tasks_persist_and_can_be_completed(self):
        self.store.add("Write documentation")
        reloaded = TaskStore(self.store.path)

        completed = reloaded.complete(1)

        self.assertEqual(completed.title, "Write documentation")
        self.assertTrue(TaskStore(self.store.path).list()[0].done)

    def test_delete_returns_the_removed_task(self):
        self.store.add("First")
        self.store.add("Second")

        deleted = self.store.delete(1)

        self.assertEqual(deleted.title, "First")
        self.assertEqual([task.title for task in self.store.list()], ["Second"])

    def test_task_metadata_persists(self):
        task = self.store.add("Finish dashboard", "2026-10-01T14:30", "high")

        reloaded = TaskStore(self.store.path).list()[0]

        self.assertEqual(task.priority, "high")
        self.assertEqual(reloaded.due_at, "2026-10-01T14:30")

    def test_notes_and_reminders_persist(self):
        notes = NoteStore(Path(self.temp_dir.name) / "notes.json")
        reminders = ReminderStore(Path(self.temp_dir.name) / "reminders.json")
        notes.add("Review testing notes")
        reminders.add("Submit report", __import__("datetime").datetime(2026, 10, 1, 14, 30))

        self.assertEqual(NoteStore(notes.path).list()[0].content, "Review testing notes")
        self.assertEqual(ReminderStore(reminders.path).pending()[0].message, "Submit report")

    def test_settings_persist(self):
        store = SettingsStore(Path(self.temp_dir.name) / "settings.json")
        store.save(Settings(city="Delhi", temperature_unit="celsius"))

        self.assertEqual(SettingsStore(store.path).load().city, "Delhi")

    def test_task_parser_understands_tomorrow_at_a_time(self):
        title, due_at, priority = VirtualAssistant._parse_task("high priority Call mentor by tomorrow at 9 AM")

        self.assertEqual(title, "Call mentor")
        self.assertEqual(priority, "high")
        self.assertEqual(datetime.fromisoformat(due_at).hour, 9)

    def test_weather_request_accepts_celsius_and_common_misspelling(self):
        assistant = VirtualAssistant()
        assistant.respond = Mock()
        assistant.web.weather = Mock(return_value="Delhi: clear sky")

        assistant.handle("weather delhi in celcius")

        assistant.web.weather.assert_called_once_with("delhi", "celsius")

    def test_weather_request_accepts_fahrenheit(self):
        assistant = VirtualAssistant()
        assistant.respond = Mock()
        assistant.web.weather = Mock(return_value="Dallas: clear sky")

        assistant.handle("weather Dallas Fahrenheit")

        assistant.web.weather.assert_called_once_with("Dallas", "fahrenheit")


if __name__ == "__main__":
    unittest.main()
