# Virtual Assistant

A command-line Python based virtual assistant. It supports typed commands out of the box and optional microphone input and text-to-speech.

## Features

- Current weather for any city (via the public `wttr.in` endpoint)
- Top news headlines from Google News RSS feeds
- Wikipedia summaries and browser web searches
- Task creation, priorities, due dates, completion, and removal persisted in `data/tasks.json`
- Persistent notes and reminders stored locally in `data/`
- Add, edit, and delete pending reminders from the dashboard or command line
- A local calendar for adding, listing, editing, and deleting events, with a 10-minute alert while the app is running
- A daily briefing of tasks and reminders due today
- A Tkinter dashboard for tasks, notes, reminders, calendar events, current weather, and a daily briefing
- Optional voice commands with `SpeechRecognition` and spoken responses with `pyttsx3`

## Setup

The typed assistant requires Python 3.10+. For microphone input, use Python 3.10–3.13.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python assistant.py
```

To launch the desktop dashboard instead:

```bash
python assistant_gui.py
```

On macOS with Homebrew Python 3.13, install Tkinter once before launching the dashboard:

```bash
brew install python-tk@3.13
```

The core assistant works without installing optional voice packages. On macOS, enable microphone input with:

```bash
pip install SpeechRecognition sounddevice pyttsx3
```

`sounddevice` installs a prebuilt PortAudio library on macOS, so it does not depend on a local compiler or Xcode Command Line Tools.

## Commands

```text
help
weather Chicago
weather Delhi in Celsius
weather Dallas in Fahrenheit
news technology
search Python virtual environments
tell me about Ada Lovelace
add task Submit project report
add task high priority Submit project report by 2026-10-15 17:00
add task Call the mentor by tomorrow at 9 AM
tasks
complete task 1
delete task 1
add event Project review on 2026-10-08 14:30
add event Team check-in on tomorrow at 9 AM
events
edit event 1 to Project review with advisor on 2026-10-08 15:00
delete event 1
take note Include screenshots in the presentation
notes
open https://www.python.org
remind me in 15 minutes to stretch
remind me on 2026-10-01 14:30 to call the project mentor
daily briefing
set city Delhi
set unit Fahrenheit
weather
time
voice on
quit
```

The project reads public web data and does not require API keys. Network failures are reported clearly so the assistant remains usable offline for local tasks.

## Project layout

```text
assistant.py       Command-line application and intent handling
assistant_gui.py   Tkinter dashboard
services.py        Weather, news, knowledge, task, reminder, and calendar services
requirements.txt   Runtime dependencies
tests/             Local task-store tests
```
