from typing import Literal, Optional
import argparse
import os
import sqlite3
import time
import sys
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime
from rich.console import Console
from rich.table import Table

class Event(BaseModel):
    message: str
    type: Literal["start", "stop", "marker"]
    time: int  # unix timestamp
    project_id: int = 1  # Default to project 1

class Project(BaseModel):
    id: Optional[int] = None
    name: str
    is_default: bool = False

def get_db_path():
    db_path = os.environ.get("WORK_TRACKER_DB_PATH")
    if not db_path:
        print("WORK_TRACKER_DB_PATH environment variable not set.")
        print("Please add it to your .zshrc and reload.")
        sys.exit(1)
    return db_path

def init_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
        
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        type TEXT NOT NULL,
        time INTEGER NOT NULL,
        project_id INTEGER DEFAULT 1
    )
    ''')
    
    # Create projects table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        is_default BOOLEAN NOT NULL DEFAULT 0
    )
    ''')
    
    # Check if we need to add the default project
    cursor.execute("SELECT COUNT(*) FROM projects")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO projects (name, is_default) VALUES (?, ?)",
            ("default", 1)
        )
    
    conn.commit()
    conn.close()

def get_current_project(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name FROM projects WHERE is_default = 1")
    result = cursor.fetchone()
    
    conn.close()
    
    if result:
        return {"id": result[0], "name": result[1]}
    else:
        return {"id": 1, "name": "default"}

def set_project(project_name, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if project exists
    cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
    result = cursor.fetchone()
    
    if result:
        # Project exists, set it as default
        project_id = result[0]
    else:
        # Create new project
        cursor.execute(
            "INSERT INTO projects (name, is_default) VALUES (?, ?)",
            (project_name, 0)
        )
        project_id = cursor.lastrowid
    
    # Reset all projects to non-default
    cursor.execute("UPDATE projects SET is_default = 0")
    
    # Set the selected project as default
    cursor.execute("UPDATE projects SET is_default = 1 WHERE id = ?", (project_id,))
    
    conn.commit()
    conn.close()
    
    return {"id": project_id, "name": project_name}

def insert_event(event_type, message, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    current_time = int(time.time())
    current_project = get_current_project(db_path)
    
    cursor.execute(
        "INSERT INTO events (message, type, time, project_id) VALUES (?, ?, ?, ?)",
        (message, event_type, current_time, current_project["id"])
    )
    
    conn.commit()
    conn.close()
    
    return {
        "message": message, 
        "type": event_type, 
        "time": current_time,
        "project": current_project["name"]
    }

def calculate_work_duration(events):
    """Calculate total work time from start/stop events."""
    total_seconds = 0
    current_start = None
    
    for event in events:
        message, event_type, timestamp = event
        
        if event_type == "start":
            current_start = timestamp
        elif event_type == "stop" and current_start is not None:
            duration = timestamp - current_start
            total_seconds += duration
            current_start = None
    
    # If there's an unclosed start event, count time until now
    if current_start is not None:
        current_time = int(time.time())
        duration = current_time - current_start
        total_seconds += duration
    
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return {
        "formatted": f"{hours}h {minutes}m {seconds}s"
    }

def list_events(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    current_project = get_current_project(db_path)
    
    cursor.execute(
        "SELECT message, type, time FROM events WHERE project_id = ? ORDER BY time",
        (current_project["id"],)
    )
    events = cursor.fetchall()
    
    conn.close()
    
    console = Console()
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Type")
    table.add_column("Time")
    table.add_column("Message")
    
    for event in events:
        message, event_type, timestamp = event
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        
        if event_type == "start":
            color = "green"
        elif event_type == "stop":
            color = "red"
        else:
            color = "yellow"
            
        table.add_row(
            f"[{color}]{event_type}[/{color}]",
            time_str,
            message
        )
    
    console.print(f"[bold]Project:[/bold] {current_project['name']}")
    console.print(table)
    
    # Add summary of work time
    duration = calculate_work_duration(events)
    console.print(f"\n[bold]Total time worked:[/bold] {duration['formatted']}")
    
    # Show if there's ongoing work
    if events:
        last_event = events[-1]
        event_type = last_event[1]
        
        if event_type == "start":
            start_time = datetime.fromtimestamp(last_event[2])
            current_time = datetime.now()
            elapsed = current_time - start_time
            hours, remainder = divmod(elapsed.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            elapsed_str = f"{hours}h {minutes}m {seconds}s"
            console.print(f"[bold green]Current session:[/bold green] {elapsed_str} (since {start_time.strftime('%Y-%m-%d %H:%M:%S')})")

def list_projects(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, is_default FROM projects ORDER BY id")
    projects = cursor.fetchall()
    
    conn.close()
    
    console = Console()
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Status")
    
    for project in projects:
        project_id, name, is_default = project
        status = "[green]current[/green]" if is_default else ""
        
        table.add_row(
            str(project_id),
            name,
            status
        )
    
    console.print(table)

def calculate_project_work_duration(db_path, project_id):
    """Calculate total work time for a specific project."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT message, type, time FROM events WHERE project_id = ? ORDER BY time",
        (project_id,)
    )
    events = cursor.fetchall()
    
    conn.close()
    
    total_seconds = 0
    current_start = None
    
    for event in events:
        message, event_type, timestamp = event
        
        if event_type == "start":
            current_start = timestamp
        elif event_type == "stop" and current_start is not None:
            duration = timestamp - current_start
            total_seconds += duration
            current_start = None
    
    # If there's an unclosed start event, count time until now
    if current_start is not None:
        current_time = int(time.time())
        duration = current_time - current_start
        total_seconds += duration
    
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return {
        "total_seconds": total_seconds,
        "formatted": f"{hours}h {minutes}m {seconds}s"
    }

def list_projects_summary(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, is_default FROM projects ORDER BY id")
    projects = cursor.fetchall()
    
    conn.close()
    
    console = Console()
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Total Work Time")
    
    for project in projects:
        project_id, name, is_default = project
        status = "[green]current[/green]" if is_default else ""
        
        duration = calculate_project_work_duration(db_path, project_id)
        
        table.add_row(
            str(project_id),
            name,
            status,
            duration["formatted"]
        )
    
    console.print(table)

def main():
    parser = argparse.ArgumentParser(description="Work Tracker CLI")
    parser.add_argument("-m", "--message", type=str, help="Message for the event", default="")
    parser.add_argument("-s", "--stop", action="store_true", help="Create a stop event")
    parser.add_argument("-p", "--project", type=str, help="Set active project")
    parser.add_argument("list", nargs="?", help="List all events")
    parser.add_argument("--projects", action="store_true", help="List all projects")
    parser.add_argument("--summary", action="store_true", help="Show summary of all projects")
    
    args = parser.parse_args()
    
    db_path = get_db_path()
    init_db(db_path)
    
    if args.summary:
        list_projects_summary(db_path)
        return
    
    if args.projects:
        list_projects(db_path)
        return
    
    if args.project:
        project = set_project(args.project, db_path)
        print(f"Set active project to: {project['name']}")
        return
    
    if args.list == "list":
        list_events(db_path)
        return
    
    if args.stop:
        # Create a stop event
        event = insert_event("stop", args.message, db_path)
        print(f"Stopped work: {event['message']} (Project: {event['project']})")
    else:
        # Check if there's an active start event without a stop
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        current_project = get_current_project(db_path)
        
        cursor.execute("""
            SELECT id FROM events 
            WHERE type = 'start' 
            AND project_id = ?
            AND id > COALESCE(
                (SELECT MAX(id) FROM events WHERE type = 'stop' AND project_id = ?), 0
            ) LIMIT 1
        """, (current_project["id"], current_project["id"]))
        
        has_active_start = cursor.fetchone() is not None
        conn.close()
        
        if has_active_start:
            # If there's an active start event, create a marker
            event = insert_event("marker", args.message, db_path)
            print(f"Created marker: {event['message']} (Project: {event['project']})")
        else:
            # Otherwise create a start event
            event = insert_event("start", args.message, db_path)
            print(f"Started work: {event['message']} (Project: {event['project']})")

if __name__ == "__main__":
    main()
