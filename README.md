# Work Tracker

A simple CLI tool to track your work sessions and create markers for activities.

## Installation

```bash
# Install locally in development mode
uv tool install -e . 
```

## Usage

By default this will create a start work event:
```bash
wt
```

You can also pass in a message:
```bash
wt -m "message"
```

For the stop event, use the -s flag:
```bash
wt -s
```

You can combine with a message:
```bash
wt -s -m "Worked on this"
```

If we call wt and there is already a start event, a marker event is created instead.
A start event is completed once we call the stop event with wt -s.

This command lists all events in a pretty way using the rich python package:
```bash
wt list
```

## Project Tracking

Work Tracker supports tracking work across multiple projects:

Create or switch to a project:
```bash
wt -p "project-name"
```

List all available projects:
```bash
wt --projects
```

View a summary of all projects with their total work time:
```bash
wt --summary
```

When you use `wt list`, it only shows events for the current project. All events are associated with the active project when they're created.

## Configuration

Set the `WORK_TRACKER_DB_PATH` environment variable to specify where the SQLite database should be stored:

```bash
# Add to your .zshrc
export WORK_TRACKER_DB_PATH="$HOME/.work_tracker/db.sqlite"
``` 