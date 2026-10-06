"""Services used by the command-line virtual assistant."""

from __future__ import annotations

import json
import subprocess
import threading
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


@dataclass
class Task:
    title: str
    done: bool = False
    created_at: str = ""
    due_at: str = ""
    priority: str = "normal"


@dataclass
class Note:
    content: str
    created_at: str = ""


@dataclass
class Reminder:
    message: str
    due_at: str
    delivered: bool = False
    created_at: str = ""


@dataclass
class Settings:
    name: str = ""
    city: str = ""
    temperature_unit: str = "celsius"


@dataclass
class CalendarEvent:
    title: str
    starts_at: str
    created_at: str = ""
    notified: bool = False


class TaskStore:
    """A small JSON-backed task store."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[Task]:
        try:
            records = json.loads(self.path.read_text(encoding="utf-8"))
            tasks = [Task(**record) for record in records]
            priority_order = {"high": 0, "normal": 1, "low": 2}
            return sorted(
                tasks,
                key=lambda task: (
                    task.done,
                    priority_order.get(task.priority, 1),
                    task.due_at or "9999-12-31T23:59",
                    task.created_at,
                ),
            )
        except (json.JSONDecodeError, OSError, TypeError):
            return []

    def _write(self, tasks: list[Task]) -> None:
        self.path.write_text(
            json.dumps([asdict(task) for task in tasks], indent=2) + "\n",
            encoding="utf-8",
        )

    def add(self, title: str, due_at: str = "", priority: str = "normal") -> Task:
        task = Task(
            title=title.strip(),
            due_at=due_at,
            priority=priority,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        tasks = self._read()
        tasks.append(task)
        self._write(tasks)
        return task

    def list(self) -> list[Task]:
        return self._read()

    def complete(self, number: int) -> Task | None:
        tasks = self._read()
        if not 1 <= number <= len(tasks):
            return None
        tasks[number - 1].done = True
        self._write(tasks)
        return tasks[number - 1]

    def delete(self, number: int) -> Task | None:
        tasks = self._read()
        if not 1 <= number <= len(tasks):
            return None
        task = tasks.pop(number - 1)
        self._write(tasks)
        return task


class NoteStore:
    """A small JSON-backed notebook."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[Note]:
        try:
            return [Note(**record) for record in json.loads(self.path.read_text(encoding="utf-8"))]
        except (json.JSONDecodeError, OSError, TypeError):
            return []

    def _write(self, notes: list[Note]) -> None:
        self.path.write_text(json.dumps([asdict(note) for note in notes], indent=2) + "\n", encoding="utf-8")

    def add(self, content: str) -> Note:
        note = Note(content=content.strip(), created_at=datetime.now().isoformat(timespec="seconds"))
        notes = self._read()
        notes.append(note)
        self._write(notes)
        return note

    def list(self) -> list[Note]:
        return self._read()

    def update(self, number: int, content: str) -> Note | None:
        notes = self._read()
        if not 1 <= number <= len(notes):
            return None
        notes[number - 1].content = content.strip()
        self._write(notes)
        return notes[number - 1]

    def delete(self, number: int) -> Note | None:
        notes = self._read()
        if not 1 <= number <= len(notes):
            return None
        note = notes.pop(number - 1)
        self._write(notes)
        return note


class SettingsStore:
    """User preferences persisted as a small JSON object."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save(Settings())

    def load(self) -> Settings:
        try:
            return Settings(**json.loads(self.path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, TypeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        self.path.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")


class CalendarStore:
    """Local calendar events stored in chronological order."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[CalendarEvent]:
        try:
            events = [CalendarEvent(**record) for record in json.loads(self.path.read_text(encoding="utf-8"))]
            return sorted(events, key=lambda event: event.starts_at)
        except (json.JSONDecodeError, OSError, TypeError):
            return []

    def _write(self, events: list[CalendarEvent]) -> None:
        self.path.write_text(json.dumps([asdict(event) for event in events], indent=2) + "\n", encoding="utf-8")

    def add(self, title: str, starts_at: datetime) -> CalendarEvent:
        event = CalendarEvent(
            title=title.strip(),
            starts_at=starts_at.isoformat(timespec="minutes"),
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        events = self._read()
        events.append(event)
        self._write(events)
        return event

    def update(self, number: int, title: str, starts_at: datetime) -> CalendarEvent | None:
        events = self._read()
        if not 1 <= number <= len(events):
            return None
        event = events[number - 1]
        event.title = title.strip()
        event.starts_at = starts_at.isoformat(timespec="minutes")
        event.notified = False
        self._write(events)
        return event

    def list(self) -> list[CalendarEvent]:
        return self._read()

    def delete(self, number: int) -> CalendarEvent | None:
        events = self._read()
        if not 1 <= number <= len(events):
            return None
        event = events.pop(number - 1)
        self._write(events)
        return event

    def due_soon(self, now: datetime | None = None, lead_minutes: int = 10) -> list[CalendarEvent]:
        now = now or datetime.now()
        events = self._read()
        upcoming = []
        changed = False
        for event in events:
            starts_at = datetime.fromisoformat(event.starts_at)
            if event.notified or starts_at <= now:
                if not event.notified and starts_at <= now:
                    event.notified = True
                    changed = True
                continue
            if starts_at - timedelta(minutes=lead_minutes) <= now:
                event.notified = True
                upcoming.append(event)
                changed = True
        if changed:
            self._write(events)
        return upcoming


class WebService:
    """Public web data sources with short timeouts and readable failures."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "UndergradVirtualAssistant/1.0"})

    def weather(self, city: str, unit: str = "celsius") -> str:
        """Return current conditions for a city in Celsius or Fahrenheit."""
        try:
            location_response = self.session.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "en", "format": "json"},
                timeout=8,
            )
            location_response.raise_for_status()
            locations = location_response.json().get("results", [])
            if not locations:
                return f"I could not find a location named {city}."

            location = locations[0]
            forecast_response = self.session.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "temperature_unit": unit,
                    "wind_speed_unit": "kmh",
                    "timezone": "auto",
                },
                timeout=8,
            )
            forecast_response.raise_for_status()
            forecast = forecast_response.json()
            current = forecast["current"]
            units = forecast.get("current_units", {})
            condition = self._weather_description(current.get("weather_code"))
            city_name = location.get("name", city)
            country = location.get("country", "")
            place = f"{city_name}, {country}" if country else city_name
            return (
                f"{place}: {condition}, {current['temperature_2m']}{units.get('temperature_2m', '')}. "
                f"Feels like {current['apparent_temperature']}{units.get('apparent_temperature', '')}; "
                f"wind {current['wind_speed_10m']}{units.get('wind_speed_10m', ' km/h')}."
            )
        except requests.RequestException:
            return "I could not retrieve the weather right now. Check your connection and try again."

    @staticmethod
    def _weather_description(code: int | None) -> str:
        descriptions = {
            0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "rime fog", 51: "light drizzle", 53: "drizzle",
            55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
            71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
            81: "heavy rain showers", 82: "violent rain showers", 95: "thunderstorm",
        }
        return descriptions.get(code, "current conditions unavailable")

    def news(self, topic: str = "") -> list[str]:
        query = quote_plus(topic) if topic else "top+stories"
        try:
            response = self.session.get(
                f"https://news.google.com/rss/search?q={query}", timeout=8
            )
            response.raise_for_status()
            feed = BeautifulSoup(response.content, "xml")
            return [item.title.get_text(strip=True) for item in feed.find_all("item")[:5]]
        except requests.RequestException:
            return []

    def summary(self, topic: str) -> str:
        try:
            response = self.session.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote_plus(topic)}",
                timeout=8,
            )
            if response.status_code == 404:
                return f"I could not find a Wikipedia entry for {topic}."
            response.raise_for_status()
            extract = response.json().get("extract")
            return extract or f"I could not find a concise summary for {topic}."
        except requests.RequestException:
            return "I could not retrieve that information right now."

    @staticmethod
    def search(query: str) -> None:
        webbrowser.open_new_tab(f"https://www.google.com/search?q={quote_plus(query)}")

    @staticmethod
    def open_url(url: str) -> bool:
        if not url.startswith(("https://", "http://")):
            url = f"https://{url}"
        return webbrowser.open_new_tab(url)


class ReminderStore:
    """Persistent reminders that survive an application restart."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[Reminder]:
        try:
            return [Reminder(**record) for record in json.loads(self.path.read_text(encoding="utf-8"))]
        except (json.JSONDecodeError, OSError, TypeError):
            return []

    def _write(self, reminders: list[Reminder]) -> None:
        self.path.write_text(json.dumps([asdict(item) for item in reminders], indent=2) + "\n", encoding="utf-8")

    def add(self, message: str, due: datetime) -> Reminder:
        reminder = Reminder(
            message=message.strip(), due_at=due.isoformat(timespec="seconds"),
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        reminders = self._read()
        reminders.append(reminder)
        self._write(reminders)
        return reminder

    def due(self, now: datetime | None = None) -> list[Reminder]:
        now = now or datetime.now()
        reminders = self._read()
        due = [item for item in reminders if not item.delivered and datetime.fromisoformat(item.due_at) <= now]
        for item in due:
            item.delivered = True
        if due:
            self._write(reminders)
        return due

    def pending(self) -> list[Reminder]:
        return [item for item in self._read() if not item.delivered]

    def update(self, number: int, message: str, due: datetime) -> Reminder | None:
        reminders = self._read()
        pending = [item for item in reminders if not item.delivered]
        if not 1 <= number <= len(pending):
            return None
        reminder = pending[number - 1]
        reminder.message = message.strip()
        reminder.due_at = due.isoformat(timespec="seconds")
        self._write(reminders)
        return reminder

    def delete(self, number: int) -> Reminder | None:
        reminders = self._read()
        pending = [item for item in reminders if not item.delivered]
        if not 1 <= number <= len(pending):
            return None
        reminder = pending[number - 1]
        reminders.remove(reminder)
        self._write(reminders)
        return reminder


class ReminderService:
    """Checks persistent reminders and calendar alerts while the app runs."""

    def __init__(self, store: ReminderStore, callback: Callable[[str], None], calendar: CalendarStore | None = None) -> None:
        self.store = store
        self.callback = callback
        self.calendar = calendar
        self._thread: threading.Thread | None = None

    def schedule(self, minutes: int, message: str) -> datetime:
        due = datetime.now() + timedelta(minutes=minutes)
        self.store.add(message, due)
        return due

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def check_loop() -> None:
            while True:
                for reminder in self.store.due():
                    self.callback(f"Reminder: {reminder.message}")
                    self._notify_macos(reminder.message)
                if self.calendar:
                    for event in self.calendar.due_soon():
                        message = f"Upcoming event in 10 minutes: {event.title}"
                        self.callback(message)
                        self._notify_macos(message)
                threading.Event().wait(15)

        self._thread = threading.Thread(target=check_loop, daemon=True)
        self._thread.start()

    @staticmethod
    def _notify_macos(message: str) -> None:
        script = 'on run argv\ndisplay notification (item 1 of argv) with title "Personal Assistant"\nend run'
        try:
            subprocess.run(["osascript", "-e", script, message], check=False, capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
