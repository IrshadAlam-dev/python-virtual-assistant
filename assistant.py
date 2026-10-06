"""A practical command-line virtual assistant."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from services import CalendarStore, NoteStore, ReminderService, ReminderStore, SettingsStore, TaskStore, WebService


HELP = """Commands:
  weather <city> [in Celsius/Fahrenheit]  Get current weather
  news [topic]                      Read five recent headlines
  search <query>                    Open a browser search
  tell me about <topic>             Read a Wikipedia summary
  add task <title> [by YYYY-MM-DD HH:MM]  Save a task with an optional due date
  tasks                             List saved tasks
  complete task <number>            Mark a task complete
  delete task <number>              Delete a task
  open <website>                    Open a website in your browser
  take note <text>                  Save a note
  notes                             Read saved notes
  edit note <number> <text>         Update a note
  delete note <number>              Delete a note
  remind me in <minutes> minutes to <message>
  remind me on YYYY-MM-DD HH:MM to <message>
  reminders                         List pending reminders
  delete reminder <number>          Delete a reminder
  add event <title> on <date/time>  Add a local calendar event
  events                            List upcoming calendar events
  delete event <number>             Delete a calendar event
  daily briefing                    Show today's tasks and reminders
  set city <city>                   Set your briefing location
  set unit Celsius/Fahrenheit       Set your preferred temperature unit
  settings                          Show saved preferences
  time                              Show the current local time
  voice on | voice off              Toggle microphone input
  quit                              Exit the assistant"""


class VirtualAssistant:
    def __init__(self) -> None:
        self.tasks = TaskStore(Path("data/tasks.json"))
        self.notes = NoteStore(Path("data/notes.json"))
        self.reminder_store = ReminderStore(Path("data/reminders.json"))
        self.settings_store = SettingsStore(Path("data/settings.json"))
        self.calendar = CalendarStore(Path("data/events.json"))
        self.web = WebService()
        self.reminders = ReminderService(self.reminder_store, self.respond)
        self.voice_enabled = False
        self.speaker = self._build_speaker()

    @staticmethod
    def _build_speaker():
        try:
            import pyttsx3

            return pyttsx3.init()
        except (ImportError, RuntimeError):
            return None

    def respond(self, message: str) -> None:
        print(f"\nAssistant: {message}\n")
        if self.speaker:
            self.speaker.say(message)
            self.speaker.runAndWait()

    def listen(self) -> str | None:
        if not self.voice_enabled:
            return input("You: ").strip()
        try:
            import speech_recognition as sr
            import sounddevice as sd

            recognizer = sr.Recognizer()
            sample_rate = 16_000
            seconds = 7
            print(f"Listening for {seconds} seconds…")
            with sd.RawInputStream(
                samplerate=sample_rate, channels=1, dtype="int16"
            ) as source:
                recording, overflowed = source.read(sample_rate * seconds)
            if overflowed:
                self.respond("The microphone buffer overflowed. Please try again.")
                return None
            audio = sr.AudioData(bytes(recording), sample_rate, sample_width=2)
            message = recognizer.recognize_google(audio)
            print(f"You: {message}")
            return message
        except ImportError:
            self.respond("Voice support needs SpeechRecognition and sounddevice. Switching to typed input.")
            self.voice_enabled = False
            return input("You: ").strip()
        except Exception as error:
            self.respond(f"I could not understand that ({error}). Please try again.")
            return None

    def handle(self, raw_command: str) -> bool:
        command = raw_command.strip()
        lower = command.lower()
        if not command:
            return True
        if lower in {"quit", "exit", "bye"}:
            self.respond("Goodbye!")
            return False
        if lower in {"help", "commands"}:
            self.respond(HELP)
        elif lower.startswith("weather "):
            city, unit = self._parse_weather_request(command[8:].strip())
            self.respond(self.web.weather(city, unit))
        elif lower == "weather":
            settings = self.settings_store.load()
            if settings.city:
                self.respond(self.web.weather(settings.city, settings.temperature_unit))
            else:
                self.respond("Set a default city first, for example: set city Delhi")
        elif lower == "news" or lower.startswith("news "):
            topic = command[5:].strip()
            headlines = self.web.news(topic)
            self.respond("\n".join(f"{index}. {headline}" for index, headline in enumerate(headlines, 1)) if headlines else "I could not retrieve news right now.")
        elif lower.startswith("search "):
            query = command[7:].strip()
            self.web.search(query)
            self.respond(f"I opened search results for {query}.")
        elif lower.startswith("tell me about "):
            self.respond(self.web.summary(command[14:].strip()))
        elif lower.startswith("add task "):
            title, due_at, priority = self._parse_task(command[9:].strip())
            if title:
                self.tasks.add(title, due_at, priority)
                due_message = f" due {self._display_date(due_at)}" if due_at else ""
                self.respond(f"Added {priority}-priority task: {title}{due_message}.")
            else:
                self.respond("Please give the task a title.")
        elif lower in {"tasks", "list tasks"}:
            tasks = self.tasks.list()
            self.respond("\n".join(self._format_task(i, task) for i, task in enumerate(tasks, 1)) if tasks else "Your task list is empty.")
        elif match := re.fullmatch(r"complete task (\d+)", lower):
            task = self.tasks.complete(int(match.group(1)))
            self.respond(f"Completed: {task.title}" if task else "That task number does not exist.")
        elif match := re.fullmatch(r"delete task (\d+)", lower):
            task = self.tasks.delete(int(match.group(1)))
            self.respond(f"Deleted: {task.title}" if task else "That task number does not exist.")
        elif lower.startswith("open "):
            address = command[5:].strip()
            self.web.open_url(address)
            self.respond(f"Opening {address}.")
        elif match := re.fullmatch(r"remind me in (\d+) minutes? to (.+)", command, re.IGNORECASE):
            minutes, message = int(match.group(1)), match.group(2)
            due = self.reminders.schedule(minutes, message)
            self.respond(f"I will remind you at {due.strftime('%I:%M %p')}.")
        elif match := re.fullmatch(r"remind me on (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) to (.+)", command, re.IGNORECASE):
            try:
                due = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M")
                self.reminder_store.add(match.group(2), due)
                self.respond(f"Reminder saved for {self._display_date(due.isoformat())}.")
            except ValueError:
                self.respond("Use a date like 2026-10-01 14:30.")
        elif lower.startswith("take note "):
            content = command[10:].strip()
            if content:
                self.notes.add(content)
                self.respond("Note saved.")
            else:
                self.respond("Please provide the note text.")
        elif lower in {"notes", "list notes"}:
            notes = self.notes.list()
            self.respond("\n".join(f"{i}. {note.content} ({self._display_date(note.created_at)})" for i, note in enumerate(notes, 1)) if notes else "Your notebook is empty.")
        elif match := re.fullmatch(r"edit note (\d+) (.+)", command, re.IGNORECASE):
            note = self.notes.update(int(match.group(1)), match.group(2))
            self.respond("Note updated." if note else "That note number does not exist.")
        elif match := re.fullmatch(r"delete note (\d+)", lower):
            note = self.notes.delete(int(match.group(1)))
            self.respond("Note deleted." if note else "That note number does not exist.")
        elif lower in {"reminders", "list reminders"}:
            reminders = self.reminder_store.pending()
            self.respond("\n".join(f"{i}. {item.message} — {self._display_date(item.due_at)}" for i, item in enumerate(reminders, 1)) if reminders else "You have no pending reminders.")
        elif match := re.fullmatch(r"delete reminder (\d+)", lower):
            item = self.reminder_store.delete(int(match.group(1)))
            self.respond("Reminder deleted." if item else "That reminder number does not exist.")
        elif match := re.fullmatch(r"add event (.+?) on (.+)", command, re.IGNORECASE):
            starts_at = self._parse_date_phrase(match.group(2))
            if starts_at is None:
                self.respond("Use a date like 2026-10-08 14:30, or say 'tomorrow at 9 AM'.")
            elif starts_at < datetime.now():
                self.respond("That event time has already passed. Please choose a future time.")
            else:
                event = self.calendar.add(match.group(1), starts_at)
                self.respond(f"Added {event.title} for {self._display_date(event.starts_at)}.")
        elif lower in {"events", "calendar", "list events"}:
            events = self.calendar.list()
            self.respond("\n".join(f"{i}. {event.title} — {self._display_date(event.starts_at)}" for i, event in enumerate(events, 1)) if events else "Your calendar is empty.")
        elif match := re.fullmatch(r"delete event (\d+)", lower):
            event = self.calendar.delete(int(match.group(1)))
            self.respond(f"Deleted {event.title}." if event else "That event number does not exist.")
        elif lower == "daily briefing":
            self.respond(self._daily_briefing())
        elif lower.startswith("set city "):
            settings = self.settings_store.load()
            settings.city = command[9:].strip()
            self.settings_store.save(settings)
            self.respond(f"Your default city is now {settings.city}.")
        elif match := re.fullmatch(r"set unit (celsius|celcius|fahrenheit)", lower):
            settings = self.settings_store.load()
            settings.temperature_unit = "fahrenheit" if match.group(1) == "fahrenheit" else "celsius"
            self.settings_store.save(settings)
            self.respond(f"Your preferred unit is now {settings.temperature_unit}.")
        elif lower == "settings":
            settings = self.settings_store.load()
            city = settings.city or "not set"
            self.respond(f"Default city: {city}\nTemperature unit: {settings.temperature_unit}")
        elif lower == "time":
            self.respond(datetime.now().strftime("It is %I:%M %p on %A, %B %d."))
        elif lower == "voice on":
            self.voice_enabled = True
            self.respond("Voice input is on.")
        elif lower == "voice off":
            self.voice_enabled = False
            self.respond("Voice input is off.")
        else:
            self.respond("I don't recognize that command. Type help to see available commands.")
        return True

    @staticmethod
    def _parse_weather_request(request: str) -> tuple[str, str]:
        """Extract a city and requested temperature unit from natural phrasing."""
        match = re.search(r"\s+(?:in\s+)?(celsius|celcius|°c|fahrenheit|°f)\s*$", request, re.IGNORECASE)
        if not match:
            return request, "celsius"
        unit = "fahrenheit" if match.group(1).lower() in {"fahrenheit", "°f"} else "celsius"
        return request[:match.start()].strip(), unit

    @staticmethod
    def _parse_task(request: str) -> tuple[str, str, str]:
        priority = "normal"
        priority_match = re.match(r"(high|medium|low) priority\s+", request, re.IGNORECASE)
        if priority_match:
            priority = priority_match.group(1).lower()
            request = request[priority_match.end():]
        due_match = re.search(r"\s+by\s+(.+)$", request, re.IGNORECASE)
        if not due_match:
            return request.strip(), "", priority
        due = VirtualAssistant._parse_date_phrase(due_match.group(1))
        if due is None:
            return request.strip(), "", priority
        return request[:due_match.start()].strip(), due.isoformat(timespec="minutes"), priority

    @staticmethod
    def _parse_date_phrase(value: str) -> datetime | None:
        value = value.strip().lower()
        for format_string in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, format_string)
            except ValueError:
                pass
        match = re.fullmatch(r"tomorrow(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?", value)
        if match:
            due = datetime.now().replace(second=0, microsecond=0) + timedelta(days=1)
            if match.group(1):
                hour, minute = int(match.group(1)), int(match.group(2) or 0)
                if match.group(3) == "pm" and hour != 12:
                    hour += 12
                if match.group(3) == "am" and hour == 12:
                    hour = 0
                return due.replace(hour=hour, minute=minute)
            return due.replace(hour=9, minute=0)
        return None

    @staticmethod
    def _display_date(value: str) -> str:
        try:
            return datetime.fromisoformat(value).strftime("%b %d, %Y at %I:%M %p")
        except ValueError:
            return value

    def _format_task(self, index, task) -> str:
        due = f" — due {self._display_date(task.due_at)}" if task.due_at else ""
        return f"{index}. [{'x' if task.done else ' '}] [{task.priority}] {task.title}{due}"

    def _daily_briefing(self) -> str:
        today = datetime.now().date()
        unfinished = [task for task in self.tasks.list() if not task.done]
        today_tasks = [task for task in unfinished if task.due_at and datetime.fromisoformat(task.due_at).date() <= today]
        reminders = [item for item in self.reminder_store.pending() if datetime.fromisoformat(item.due_at).date() <= today]
        events = [item for item in self.calendar.list() if datetime.fromisoformat(item.starts_at).date() == today]
        task_text = "\n".join(f"• {task.title}" for task in today_tasks) or "• No tasks due today."
        reminder_text = "\n".join(f"• {item.message} at {self._display_date(item.due_at)}" for item in reminders) or "• No reminders today."
        event_text = "\n".join(f"• {item.starts_at[11:]} — {item.title}" for item in events) or "• No events today."
        settings = self.settings_store.load()
        weather = self.web.weather(settings.city, settings.temperature_unit) if settings.city else "Set a default city to add weather."
        overdue = [task for task in unfinished if task.due_at and datetime.fromisoformat(task.due_at).date() < today]
        overdue_text = "\n".join(f"• {task.title}" for task in overdue) or "• No overdue tasks."
        return f"Daily briefing for {today.strftime('%A, %B %d')}\n\nWeather\n{weather}\n\nToday's calendar\n{event_text}\n\nOverdue\n{overdue_text}\n\nTasks\n{task_text}\n\nReminders\n{reminder_text}"

    def run(self) -> None:
        self.reminders.start()
        self.respond("Hello! I am ready. Type help to see what I can do.")
        running = True
        while running:
            command = self.listen()
            if command is not None:
                running = self.handle(command)


if __name__ == "__main__":
    VirtualAssistant().run()
