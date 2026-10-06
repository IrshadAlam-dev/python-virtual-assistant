"""Tkinter dashboard for the personal assistant."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from services import CalendarStore, NoteStore, ReminderService, ReminderStore, SettingsStore, TaskStore, WebService


class AssistantDashboard(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Orbit — Personal Assistant")
        self.minsize(900, 760)
        self.tasks = TaskStore(Path("data/tasks.json"))
        self.notes = NoteStore(Path("data/notes.json"))
        self.reminders = ReminderStore(Path("data/reminders.json"))
        self.settings = SettingsStore(Path("data/settings.json"))
        self.calendar = CalendarStore(Path("data/events.json"))
        self.web = WebService()
        self.reminder_service = ReminderService(self.reminders, self._notify_reminder)
        self._configure_theme()
        self._build()
        self.refresh()
        self.reminder_service.start()

    def _configure_theme(self) -> None:
        self.configure(background="#f5f7fb")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#f5f7fb")
        style.configure("Card.TLabelframe", background="#ffffff", borderwidth=0, relief="flat")
        style.configure("Card.TLabelframe.Label", background="#ffffff", foreground="#1f2937", font=("Helvetica", 13, "bold"))
        style.configure("Title.TLabel", background="#f5f7fb", foreground="#111827", font=("Helvetica", 24, "bold"))
        style.configure("Subtitle.TLabel", background="#f5f7fb", foreground="#6b7280", font=("Helvetica", 11))
        style.configure("Section.TLabel", background="#ffffff", foreground="#6b7280", font=("Helvetica", 10, "bold"))
        style.configure("Primary.TButton", background="#2563eb", foreground="#ffffff", padding=(14, 9), font=("Helvetica", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#1d4ed8"), ("disabled", "#bfdbfe")])
        style.configure("Secondary.TButton", background="#e8eefc", foreground="#1d4ed8", padding=(12, 8))
        style.map("Secondary.TButton", background=[("active", "#dbeafe")])
        style.configure("Danger.TButton", background="#fee2e2", foreground="#b91c1c", padding=(12, 8))
        style.map("Danger.TButton", background=[("active", "#fecaca")])
        style.configure("TEntry", padding=8, fieldbackground="#ffffff")
        style.configure("TCombobox", padding=7)

    def _build(self) -> None:
        shell = ttk.Frame(self, padding=(28, 24), style="App.TFrame")
        shell.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        shell.columnconfigure((0, 1), weight=1)
        shell.rowconfigure(2, weight=1)
        shell.rowconfigure(4, weight=1)

        header = ttk.Frame(shell, style="App.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Good day", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Plan your day, capture ideas, and keep the important things moving.", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Button(header, text="↻  Refresh briefing", command=self.refresh, style="Secondary.TButton").grid(row=0, column=1, rowspan=2, sticky="e")

        weather = ttk.LabelFrame(shell, text="Weather", padding=16, style="Card.TLabelframe")
        weather.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        weather.columnconfigure(1, weight=1)
        ttk.Label(weather, text="DEFAULT CITY", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.city = ttk.Entry(weather)
        self.city.insert(0, self.settings.load().city or "Delhi")
        self.city.grid(row=0, column=1, sticky="ew")
        ttk.Button(weather, text="Get weather", command=self.show_weather, style="Primary.TButton").grid(row=0, column=2, padx=(12, 0))
        self.weather_text = ttk.Label(weather, text="Enter a city to get current weather.", background="#ffffff", foreground="#374151", wraplength=760, font=("Helvetica", 11))
        self.weather_text.grid(row=1, column=0, columnspan=3, sticky="w", pady=(12, 0))

        task_frame = ttk.LabelFrame(shell, text="Tasks", padding=16, style="Card.TLabelframe")
        task_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 8), pady=(0, 16))
        task_frame.columnconfigure(0, weight=1)
        task_frame.rowconfigure(6, weight=1)
        ttk.Label(task_frame, text="WHAT NEEDS TO GET DONE?", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.task_title = ttk.Entry(task_frame)
        self.task_title.grid(row=1, column=0, sticky="ew")
        ttk.Label(task_frame, text="DUE DATE  •  Optional", style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(12, 6))
        self.task_due = ttk.Entry(task_frame)
        self.task_due.grid(row=3, column=0, sticky="ew")
        self.task_due.insert(0, "YYYY-MM-DD HH:MM")
        self.task_due.bind("<FocusIn>", self._clear_due_placeholder)
        self.priority = ttk.Combobox(task_frame, values=("high", "normal", "low"), state="readonly")
        self.priority.set("normal")
        self.priority.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(task_frame, text="+  Add task", command=self.add_task, style="Primary.TButton").grid(row=5, column=0, sticky="ew", pady=(10, 14))
        self.task_list = tk.Listbox(task_frame, height=9, activestyle="none", borderwidth=0, highlightthickness=1, highlightbackground="#e5e7eb", selectbackground="#dbeafe", selectforeground="#1e3a8a", background="#f9fafb", foreground="#1f2937", font=("Helvetica", 11))
        self.task_list.grid(row=6, column=0, sticky="nsew")
        self.task_list.bind("<<ListboxSelect>>", self._update_action_states)
        task_actions = ttk.Frame(task_frame, style="Card.TLabelframe")
        task_actions.grid(row=7, column=0, sticky="ew", pady=(10, 0))
        task_actions.columnconfigure(0, weight=1)
        task_actions.columnconfigure(1, weight=1)
        self.complete_button = ttk.Button(task_actions, text="Complete", command=self.complete_task, style="Secondary.TButton", state="disabled")
        self.complete_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.delete_task_button = ttk.Button(task_actions, text="Delete", command=self.delete_task, style="Danger.TButton", state="disabled")
        self.delete_task_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        note_frame = ttk.LabelFrame(shell, text="Notes", padding=16, style="Card.TLabelframe")
        note_frame.grid(row=2, column=1, sticky="nsew", padx=(8, 0), pady=(0, 16))
        note_frame.columnconfigure(0, weight=1)
        note_frame.rowconfigure(3, weight=1)
        ttk.Label(note_frame, text="CAPTURE A THOUGHT", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.note_text = ttk.Entry(note_frame)
        self.note_text.grid(row=1, column=0, sticky="ew")
        ttk.Button(note_frame, text="+  Save note", command=self.add_note, style="Primary.TButton").grid(row=2, column=0, sticky="ew", pady=(10, 14))
        self.note_list = tk.Listbox(note_frame, height=9, activestyle="none", borderwidth=0, highlightthickness=1, highlightbackground="#e5e7eb", selectbackground="#dbeafe", selectforeground="#1e3a8a", background="#f9fafb", foreground="#1f2937", font=("Helvetica", 11))
        self.note_list.grid(row=3, column=0, sticky="nsew")
        self.note_list.bind("<<ListboxSelect>>", self._update_action_states)
        self.delete_note_button = ttk.Button(note_frame, text="Delete selected", command=self.delete_note, style="Danger.TButton", state="disabled")
        self.delete_note_button.grid(row=4, column=0, sticky="ew", pady=(10, 0))

        calendar_frame = ttk.LabelFrame(shell, text="Calendar", padding=16, style="Card.TLabelframe")
        calendar_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        calendar_frame.columnconfigure(0, weight=1)
        calendar_frame.columnconfigure(1, weight=1)
        calendar_frame.columnconfigure(2, weight=0)
        self.event_title = ttk.Entry(calendar_frame)
        self.event_title.insert(0, "Event title")
        self.event_title.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.event_title.bind("<FocusIn>", lambda _event: self._clear_placeholder(self.event_title, "Event title"))
        self.event_time = ttk.Entry(calendar_frame)
        self.event_time.insert(0, "YYYY-MM-DD HH:MM")
        self.event_time.grid(row=0, column=1, sticky="ew", padx=6)
        self.event_time.bind("<FocusIn>", lambda _event: self._clear_placeholder(self.event_time, "YYYY-MM-DD HH:MM"))
        ttk.Button(calendar_frame, text="+  Add event", command=self.add_event, style="Primary.TButton").grid(row=0, column=2, padx=(6, 0))
        self.event_list = tk.Listbox(calendar_frame, height=4, activestyle="none", borderwidth=0, highlightthickness=1, highlightbackground="#e5e7eb", selectbackground="#dbeafe", selectforeground="#1e3a8a", background="#f9fafb", foreground="#1f2937", font=("Helvetica", 11))
        self.event_list.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.event_list.bind("<<ListboxSelect>>", self._update_action_states)
        self.delete_event_button = ttk.Button(calendar_frame, text="Delete selected event", command=self.delete_event, style="Danger.TButton", state="disabled")
        self.delete_event_button.grid(row=2, column=0, columnspan=3, sticky="e", pady=(8, 0))

        briefing = ttk.LabelFrame(shell, text="Today at a glance", padding=16, style="Card.TLabelframe")
        briefing.grid(row=4, column=0, columnspan=2, sticky="nsew")
        briefing.columnconfigure(0, weight=1)
        briefing.rowconfigure(0, weight=1)
        self.briefing_text = tk.Text(briefing, height=8, wrap="word", state="disabled", borderwidth=0, highlightthickness=0, background="#ffffff", foreground="#374151", font=("Helvetica", 11), padx=2, pady=2)
        self.briefing_text.grid(row=0, column=0, sticky="nsew")

    def add_task(self) -> None:
        title = self.task_title.get().strip()
        due = self.task_due.get().strip()
        if due == "YYYY-MM-DD HH:MM":
            due = ""
        if not title:
            messagebox.showerror("Task", "Enter a task title.")
            return
        if due:
            try:
                due = datetime.strptime(due, "%Y-%m-%d %H:%M").isoformat(timespec="minutes")
            except ValueError:
                messagebox.showerror("Task", "Use YYYY-MM-DD HH:MM for the due date.")
                return
        self.tasks.add(title, due, self.priority.get())
        self.task_title.delete(0, tk.END)
        self.refresh()

    def add_note(self) -> None:
        content = self.note_text.get().strip()
        if content:
            self.notes.add(content)
            self.note_text.delete(0, tk.END)
            self.refresh()

    def complete_task(self) -> None:
        selected = self.task_list.curselection()
        if selected:
            self.tasks.complete(selected[0] + 1)
            self.refresh()

    def delete_task(self) -> None:
        selected = self.task_list.curselection()
        if selected:
            self.tasks.delete(selected[0] + 1)
            self.refresh()

    def delete_note(self) -> None:
        selected = self.note_list.curselection()
        if selected:
            self.notes.delete(selected[0] + 1)
            self.refresh()

    def add_event(self) -> None:
        title = self.event_title.get().strip()
        time_text = self.event_time.get().strip()
        if not title or title == "Event title":
            messagebox.showerror("Calendar", "Enter an event title.")
            return
        try:
            starts_at = datetime.strptime(time_text, "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("Calendar", "Use YYYY-MM-DD HH:MM for the event date and time.")
            return
        if starts_at < datetime.now():
            messagebox.showerror("Calendar", "Choose a future date and time.")
            return
        self.calendar.add(title, starts_at)
        self.event_title.delete(0, tk.END)
        self.event_time.delete(0, tk.END)
        self.event_time.insert(0, "YYYY-MM-DD HH:MM")
        self.refresh()

    def delete_event(self) -> None:
        selected = self.event_list.curselection()
        if selected:
            self.calendar.delete(selected[0] + 1)
            self.refresh()

    def _clear_due_placeholder(self, _event=None) -> None:
        if self.task_due.get() == "YYYY-MM-DD HH:MM":
            self.task_due.delete(0, tk.END)

    @staticmethod
    def _clear_placeholder(entry, placeholder: str) -> None:
        if entry.get() == placeholder:
            entry.delete(0, tk.END)

    def _update_action_states(self, _event=None) -> None:
        task_state = "normal" if self.task_list.curselection() else "disabled"
        note_state = "normal" if self.note_list.curselection() else "disabled"
        event_state = "normal" if self.event_list.curselection() else "disabled"
        self.complete_button.config(state=task_state)
        self.delete_task_button.config(state=task_state)
        self.delete_note_button.config(state=note_state)
        self.delete_event_button.config(state=event_state)

    def show_weather(self) -> None:
        settings = self.settings.load()
        settings.city = self.city.get().strip()
        self.settings.save(settings)
        self.weather_text.config(text=self.web.weather(settings.city, settings.temperature_unit))

    def _notify_reminder(self, message: str) -> None:
        self.after(0, lambda: messagebox.showinfo("Personal Assistant", message))

    def show_briefing(self) -> None:
        today = datetime.now().date()
        due_tasks = [task for task in self.tasks.list() if not task.done and task.due_at and datetime.fromisoformat(task.due_at).date() <= today]
        reminders = [item for item in self.reminders.pending() if datetime.fromisoformat(item.due_at).date() <= today]
        events = [item for item in self.calendar.list() if datetime.fromisoformat(item.starts_at).date() == today]
        lines = [f"{today:%A, %B %d}", "", "Today's calendar:"]
        lines += [f"• {datetime.fromisoformat(event.starts_at):%I:%M %p} — {event.title}" for event in events] or ["• No events today."]
        lines += ["", "Tasks due today:"]
        lines += [f"• [{task.priority}] {task.title}" for task in due_tasks] or ["• None"]
        lines += ["", "Reminders today:"]
        lines += [f"• {item.message} at {datetime.fromisoformat(item.due_at):%I:%M %p}" for item in reminders] or ["• None"]
        self.briefing_text.config(state="normal")
        self.briefing_text.delete("1.0", tk.END)
        self.briefing_text.insert("1.0", "\n".join(lines))
        self.briefing_text.config(state="disabled")

    def refresh(self) -> None:
        self.task_list.delete(0, tk.END)
        for task in self.tasks.list():
            due = f" — {task.due_at.replace('T', ' ')}" if task.due_at else ""
            self.task_list.insert(tk.END, f"[{'✓' if task.done else ' '}] [{task.priority}] {task.title}{due}")
        self.note_list.delete(0, tk.END)
        for note in self.notes.list():
            self.note_list.insert(tk.END, note.content)
        self.event_list.delete(0, tk.END)
        for event in self.calendar.list():
            self.event_list.insert(tk.END, f"{datetime.fromisoformat(event.starts_at):%b %d, %I:%M %p}  ·  {event.title}")
        self.show_briefing()
        self._update_action_states()


if __name__ == "__main__":
    AssistantDashboard().mainloop()
